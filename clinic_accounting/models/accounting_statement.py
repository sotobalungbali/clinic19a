from collections import defaultdict
from datetime import date, timedelta
from calendar import monthrange

from odoo import api, Command, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


SOURCE_SELECTION = [
    ("finance", "Clinic Finance"),
    ("billing", "Clinic Billing"),
    ("ar", "Accounts Receivable"),
    ("ap", "Accounts Payable"),
    ("wallet", "Patient Wallet"),
    ("adjustment", "Accounting Adjustment"),
    ("mixed", "Mixed Clinic Sources"),
    ("other", "Other / Native Odoo"),
]


class ClinicAccountingStatement(models.Model):
    """Persistent accounting statement snapshot generated from account.move.line."""

    _name = "clinic.accounting.statement"
    _description = "Clinic Accounting Statement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, id desc"
    _check_company_auto = True

    _date_range_check = models.Constraint(
        "CHECK(date_from <= date_to)",
        "Accounting Statement start date must be before or equal to end date.",
    )
    _company_type_date_idx = models.Index("(company_id, statement_type, date_to)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    statement_type = fields.Selection(
        [
            ("trial_balance", "Trial Balance"),
            ("general_ledger", "General Ledger"),
            ("profit_loss", "Profit & Loss"),
            ("balance_sheet", "Balance Sheet"),
            ("journal_audit", "Journal Audit"),
            ("source_summary", "Clinic Source Summary"),
            ("result_summary", "Current Period Earnings"),
        ],
        default="trial_balance",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    ledger_id = fields.Many2one(
        "clinic.accounting.ledger",
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        tracking=True,
    )
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)

    journal_ids = fields.Many2many(
        "account.journal",
        "clinic_accounting_statement_journal_rel",
        "statement_id",
        "journal_id",
        string="Journals",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    account_ids = fields.Many2many(
        "account.account",
        "clinic_accounting_statement_account_rel",
        "statement_id",
        "account_id",
        string="Accounts",
    )
    branch_ids = fields.Many2many(
        "clinic.branch",
        "clinic_accounting_statement_branch_rel",
        "statement_id",
        "branch_id",
        string="Branches",
        domain="[('company_id', '=', company_id)]",
    )
    source_scope = fields.Selection(
        [
            ("all", "All Accounting Entries"),
            ("clinic_only", "ClinicOne-Sourced Entries"),
            ("finance", "Clinic Finance"),
            ("billing", "Clinic Billing"),
            ("ar", "Accounts Receivable"),
            ("ap", "Accounts Payable"),
            ("wallet", "Patient Wallet"),
            ("adjustment", "Accounting Adjustments"),
            ("mixed", "Mixed Clinic Sources"),
            ("other", "Other / Native Odoo"),
        ],
        default="all",
        required=True,
    )
    posted_only = fields.Boolean(default=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("generated", "Generated"),
            ("locked", "Locked"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "clinic.accounting.statement.line",
        "statement_id",
        string="Statement Lines",
        copy=False,
    )
    line_count = fields.Integer(compute="_compute_totals", store=True)
    total_opening = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    total_debit = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    total_credit = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    total_balance = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    net_result = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        help="Profit & Loss result: income less expenses. Zero for other statement types.",
    )
    generated_at = fields.Datetime(readonly=True)
    generated_by_id = fields.Many2one("res.users", readonly=True)
    auto_generated = fields.Boolean(default=False, readonly=True, copy=False)
    notes = fields.Text()

    @api.depends(
        "line_ids.opening_balance",
        "line_ids.debit",
        "line_ids.credit",
        "line_ids.balance",
        "line_ids.account_group",
        "statement_type",
    )
    def _compute_totals(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.total_opening = sum(record.line_ids.mapped("opening_balance"))
            record.total_debit = sum(record.line_ids.mapped("debit"))
            record.total_credit = sum(record.line_ids.mapped("credit"))
            record.total_balance = sum(record.line_ids.mapped("balance"))
            if record.statement_type == "profit_loss":
                income = sum(
                    -line.balance
                    for line in record.line_ids
                    if line.account_group == "income"
                )
                expense = sum(
                    line.balance
                    for line in record.line_ids
                    if line.account_group == "expense"
                )
                record.net_result = income - expense
            else:
                record.net_result = 0.0

    @api.onchange("ledger_id")
    def _onchange_ledger(self):
        for record in self:
            ledger = record.ledger_id
            if not ledger:
                continue
            record.company_id = ledger.company_id
            record.statement_type = ledger.default_statement_type
            record.journal_ids = ledger.journal_ids
            record.account_ids = ledger.account_ids
            record.branch_ids = ledger.branch_ids
            record.source_scope = ledger.source_scope
            record.posted_only = ledger.posted_only

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ledger = self.env["clinic.accounting.ledger"].browse(vals.get("ledger_id"))
            if ledger.exists():
                # Onchange is UI convenience only. API/import/cron creation gets
                # the same Ledger contract here so reporting scope cannot silently
                # widen outside the selected Ledger.
                vals.setdefault("company_id", ledger.company_id.id)
                vals.setdefault("statement_type", ledger.default_statement_type)
                vals.setdefault("source_scope", ledger.source_scope)
                vals.setdefault("posted_only", ledger.posted_only)
                vals.setdefault("journal_ids", [Command.set(ledger.journal_ids.ids)])
                vals.setdefault("account_ids", [Command.set(ledger.account_ids.ids)])
                vals.setdefault("branch_ids", [Command.set(ledger.branch_ids.ids)])

            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.accounting.statement")
                    or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        filter_fields = {
            "company_id",
            "ledger_id",
            "statement_type",
            "date_from",
            "date_to",
            "journal_ids",
            "account_ids",
            "branch_ids",
            "source_scope",
            "posted_only",
        }
        system_fields = {"state", "generated_at", "generated_by_id", "auto_generated"}
        if system_fields.intersection(vals) and not self.env.context.get("accounting_transition"):
            raise AccessError(
                _("Statement workflow and generation audit fields are controlled by Accounting actions.")
            )
        if filter_fields.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("Statement filters can only be changed while Draft."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda statement: statement.state == "locked"):
            raise UserError(_("Locked Accounting Statements cannot be deleted."))
        return super().unlink()

    @api.constrains("company_id", "ledger_id", "journal_ids", "account_ids", "branch_ids")
    def _check_statement_company_scope(self):
        for record in self:
            if record.ledger_id and record.ledger_id.company_id != record.company_id:
                raise ValidationError(_("Statement Ledger must belong to the Statement company."))
            if record.journal_ids.filtered(lambda journal: journal.company_id != record.company_id):
                raise ValidationError(_("Every selected journal must belong to the Statement company."))
            if record.account_ids.filtered(lambda account: record.company_id not in account.company_ids):
                raise ValidationError(_("Every selected account must be available to the Statement company."))
            if record.branch_ids.filtered(lambda branch: branch.company_id != record.company_id):
                raise ValidationError(_("Every selected branch must belong to the Statement company."))

    def _base_line_domain(self):
        self.ensure_one()
        domain = [("company_id", "=", self.company_id.id)]
        if self.posted_only:
            domain.append(("move_id.state", "=", "posted"))
        if self.journal_ids:
            domain.append(("move_id.journal_id", "in", self.journal_ids.ids))
        if self.account_ids:
            domain.append(("account_id", "in", self.account_ids.ids))
        if self.branch_ids and "branch_id" in self.env["account.move.line"]._fields:
            domain.append(("branch_id", "in", self.branch_ids.ids))
        if self.source_scope == "clinic_only":
            domain.append(("clinic_accounting_source", "!=", "other"))
        elif self.source_scope != "all":
            domain.append(("clinic_accounting_source", "=", self.source_scope))
        return domain

    def _period_domain(self):
        self.ensure_one()
        return self._base_line_domain() + [
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ]

    def _opening_domain(self):
        self.ensure_one()
        return self._base_line_domain() + [("date", "<", self.date_from)]

    def action_generate(self):
        self._require_statement_role()
        Line = self.env["clinic.accounting.statement.line"].sudo()
        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked Accounting Statements cannot be regenerated."))

            record.line_ids.sudo().unlink()

            generators = {
                "trial_balance": record._generate_trial_balance,
                "general_ledger": record._generate_general_ledger,
                "profit_loss": record._generate_profit_loss,
                "balance_sheet": record._generate_balance_sheet,
                "journal_audit": record._generate_journal_audit,
                "source_summary": record._generate_source_summary,
            }
            values = generators[record.statement_type]()
            if values:
                Line.create(values)

            record.with_context(accounting_transition=True).write({
                "state": "generated",
                "generated_at": fields.Datetime.now(),
                "generated_by_id": self.env.user.id,
            })
        return True

    def _require_statement_role(self):
        if not (
            self.env.su
            or self.env.user.has_group("clinic_accounting.group_clinic_accounting_user")
        ):
            raise AccessError(_("You do not have permission to generate Accounting Statements."))

    def _aggregate_by_account(self, lines, openings=None):
        openings = openings or {}
        buckets = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "balance": 0.0})
        accounts = {}
        for line in lines:
            accounts[line.account_id.id] = line.account_id
            bucket = buckets[line.account_id.id]
            bucket["debit"] += line.debit
            bucket["credit"] += line.credit
            bucket["balance"] += line.balance
        for account_id in openings:
            if account_id not in accounts:
                accounts[account_id] = self.env["account.account"].browse(account_id)

        result = []
        sequence = 10
        def account_sort_key(account):
            scoped = account.with_company(self.company_id)
            return ((scoped.code or ""), scoped.id)

        for account in sorted(accounts.values(), key=account_sort_key):
            scoped_account = account.with_company(self.company_id)
            opening = openings.get(account.id, 0.0)
            bucket = buckets[account.id]
            result.append({
                "statement_id": self.id,
                "sequence": sequence,
                "line_kind": "account_summary",
                "account_id": account.id,
                "account_group": account.internal_group or "off",
                "label": scoped_account.display_name,
                "opening_balance": opening,
                "debit": bucket["debit"],
                "credit": bucket["credit"],
                "balance": opening + bucket["balance"],
                "record_count": 0,
            })
            sequence += 10
        return result

    def _opening_by_account(self, domain=None):
        self.ensure_one()
        domain = domain or self._opening_domain()
        totals = defaultdict(float)
        for line in self.env["account.move.line"].sudo().search(domain):
            totals[line.account_id.id] += line.balance
        return totals

    def _generate_trial_balance(self):
        self.ensure_one()
        period_lines = self.env["account.move.line"].sudo().search(self._period_domain())
        openings = self._opening_by_account()
        return self._aggregate_by_account(period_lines, openings)

    def _generate_general_ledger(self):
        self.ensure_one()
        opening = self._opening_by_account()
        lines = self.env["account.move.line"].sudo().search(
            self._period_domain(),
            order="account_id, date, move_id, id",
        )
        running = defaultdict(float, opening)
        first_seen = set()
        values = []
        sequence = 10
        for line in lines:
            account_id = line.account_id.id
            running[account_id] += line.balance
            values.append({
                "statement_id": self.id,
                "sequence": sequence,
                "line_kind": "move_line",
                "account_id": account_id,
                "account_group": line.account_id.internal_group or "off",
                "journal_id": line.move_id.journal_id.id,
                "move_id": line.move_id.id,
                "move_line_id": line.id,
                "source_type": line.clinic_accounting_source or "other",
                "date": line.date,
                "partner_id": line.partner_id.id or False,
                "label": line.name or line.move_id.name,
                "opening_balance": opening.get(account_id, 0.0) if account_id not in first_seen else 0.0,
                "debit": line.debit,
                "credit": line.credit,
                "balance": line.balance,
                "running_balance": running[account_id],
                "record_count": 1,
            })
            first_seen.add(account_id)
            sequence += 10
        return values

    def _generate_profit_loss(self):
        self.ensure_one()
        domain = self._period_domain() + [
            ("account_id.internal_group", "in", ("income", "expense")),
        ]
        lines = self.env["account.move.line"].sudo().search(domain)
        return self._aggregate_by_account(lines, {})

    def _fiscal_year_start(self):
        self.ensure_one()
        last_month = int(self.company_id.fiscalyear_last_month or "12")
        last_day = int(self.company_id.fiscalyear_last_day or 31)

        def fiscal_end(year):
            safe_day = min(last_day, monthrange(year, last_month)[1])
            return date(year, last_month, safe_day)

        current_candidate = fiscal_end(self.date_to.year)
        previous_end = (
            fiscal_end(self.date_to.year - 1)
            if self.date_to <= current_candidate
            else current_candidate
        )
        return previous_end + timedelta(days=1)

    def _generate_balance_sheet(self):
        self.ensure_one()
        domain = self._base_line_domain() + [
            ("date", "<=", self.date_to),
            ("account_id.internal_group", "in", ("asset", "liability", "equity")),
        ]
        lines = self.env["account.move.line"].sudo().search(domain)
        values = self._aggregate_by_account(lines, {})

        # Before a fiscal-year closing entry exists, current income/expense has
        # not yet been transferred into equity. Add one synthetic equity line so
        # an as-of Balance Sheet reflects current-period earnings without
        # creating any accounting entry.
        fiscal_start = self._fiscal_year_start()
        result_domain = self._base_line_domain() + [
            ("date", ">=", fiscal_start),
            ("date", "<=", self.date_to),
            ("account_id.internal_group", "in", ("income", "expense")),
        ]
        result_lines = self.env["account.move.line"].sudo().search(result_domain)
        raw_current_result = sum(result_lines.mapped("balance"))
        if result_lines or raw_current_result:
            values.append({
                "statement_id": self.id,
                "sequence": (len(values) + 1) * 10,
                "line_kind": "result_summary",
                "account_group": "equity",
                "label": _("Current Period Earnings (Unclosed)"),
                "balance": raw_current_result,
                "record_count": len(result_lines),
            })
        return values

    def _generate_journal_audit(self):
        self.ensure_one()
        buckets = defaultdict(lambda: {
            "journal": False,
            "debit": 0.0,
            "credit": 0.0,
            "balance": 0.0,
            "moves": set(),
        })
        for line in self.env["account.move.line"].sudo().search(self._period_domain()):
            journal = line.move_id.journal_id
            bucket = buckets[journal.id]
            bucket["journal"] = journal
            bucket["debit"] += line.debit
            bucket["credit"] += line.credit
            bucket["balance"] += line.balance
            bucket["moves"].add(line.move_id.id)

        values = []
        sequence = 10
        for journal_id in sorted(
            buckets,
            key=lambda key: (buckets[key]["journal"].code or "", key),
        ):
            bucket = buckets[journal_id]
            values.append({
                "statement_id": self.id,
                "sequence": sequence,
                "line_kind": "journal_summary",
                "journal_id": journal_id,
                "label": bucket["journal"].display_name,
                "debit": bucket["debit"],
                "credit": bucket["credit"],
                "balance": bucket["balance"],
                "record_count": len(bucket["moves"]),
            })
            sequence += 10
        return values

    def _generate_source_summary(self):
        self.ensure_one()
        buckets = defaultdict(lambda: {
            "debit": 0.0,
            "credit": 0.0,
            "balance": 0.0,
            "moves": set(),
        })
        for line in self.env["account.move.line"].sudo().search(self._period_domain()):
            source = line.clinic_accounting_source or "other"
            bucket = buckets[source]
            bucket["debit"] += line.debit
            bucket["credit"] += line.credit
            bucket["balance"] += line.balance
            bucket["moves"].add(line.move_id.id)

        labels = dict(SOURCE_SELECTION)
        values = []
        sequence = 10
        for source in [key for key, _label in SOURCE_SELECTION if key in buckets]:
            bucket = buckets[source]
            values.append({
                "statement_id": self.id,
                "sequence": sequence,
                "line_kind": "source_summary",
                "source_type": source,
                "label": labels[source],
                "debit": bucket["debit"],
                "credit": bucket["credit"],
                "balance": bucket["balance"],
                "record_count": len(bucket["moves"]),
            })
            sequence += 10
        return values

    def action_lock(self):
        if not self.env.user.has_group("clinic_accounting.group_clinic_accounting_manager"):
            raise AccessError(_("Only an Accounting Manager can lock statement snapshots."))
        for record in self:
            if record.state != "generated":
                raise UserError(_("Generate the Accounting Statement before locking it."))
            record.with_context(accounting_transition=True).write({"state": "locked"})
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group("clinic_accounting.group_clinic_accounting_accountant"):
            raise AccessError(_("Only Accounting staff can reset generated statements."))
        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked statements are historical snapshots and cannot be reset."))
            record.line_ids.sudo().unlink()
            record.with_context(accounting_transition=True).write({
                "state": "draft",
                "generated_at": False,
                "generated_by_id": False,
            })
        return True

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Statement Lines"),
            "res_model": "clinic.accounting.statement.line",
            "view_mode": "list,form",
            "domain": [("statement_id", "=", self.id)],
            "context": {"default_statement_id": self.id},
        }

    def action_view_journal_items(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Statement Journal Items"),
            "res_model": "account.move.line",
            "view_mode": "list",
            "domain": self._period_domain(),
        }

    def action_print_statement(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("Generate the Statement before printing it."))
        return self.env.ref(
            "clinic_accounting.action_report_accounting_statement"
        ).report_action(self)

    @api.model
    def _cron_monthly_trial_balance(self):
        today = fields.Date.context_today(self)
        if today.day != 1:
            return

        current_month_start = today.replace(day=1)
        previous_end = current_month_start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)

        companies = self.env["res.company"].sudo().search([
            ("clinic_accounting_auto_monthly_trial_balance", "=", True)
        ])
        for company in companies:
            existing = self.sudo().search([
                ("company_id", "=", company.id),
                ("statement_type", "=", "trial_balance"),
                ("date_from", "=", previous_start),
                ("date_to", "=", previous_end),
                ("auto_generated", "=", True),
            ], limit=1)
            if existing:
                continue

            ledger = company.clinic_accounting_default_ledger_id
            values = {
                "company_id": company.id,
                "ledger_id": ledger.id or False,
                "statement_type": "trial_balance",
                "date_from": previous_start,
                "date_to": previous_end,
                "posted_only": True,
                "auto_generated": True,
            }
            if ledger:
                values.update({
                    "journal_ids": [Command.set(ledger.journal_ids.ids)],
                    "account_ids": [Command.set(ledger.account_ids.ids)],
                    "branch_ids": [Command.set(ledger.branch_ids.ids)],
                    "source_scope": ledger.source_scope,
                })

            statement = self.sudo().create(values)
            statement.sudo().action_generate()


class ClinicAccountingStatementLine(models.Model):
    """Generated Accounting Statement line with source drill-down."""

    _name = "clinic.accounting.statement.line"
    _description = "Clinic Accounting Statement Line"
    _order = "sequence, id"

    _record_count_nonnegative = models.Constraint(
        "CHECK(record_count >= 0)",
        "Statement Line record count cannot be negative.",
    )

    statement_id = fields.Many2one(
        "clinic.accounting.statement",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        related="statement_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="statement_id.currency_id",
        store=True,
        readonly=True,
    )
    line_kind = fields.Selection(
        [
            ("account_summary", "Account Summary"),
            ("move_line", "Journal Item"),
            ("journal_summary", "Journal Summary"),
            ("source_summary", "Clinic Source Summary"),
        ],
        required=True,
        index=True,
    )
    account_id = fields.Many2one("account.account", ondelete="set null", index=True)
    account_group = fields.Selection(
        [
            ("asset", "Asset"),
            ("liability", "Liability"),
            ("equity", "Equity"),
            ("income", "Income"),
            ("expense", "Expense"),
            ("off", "Off Balance"),
        ],
        index=True,
    )
    journal_id = fields.Many2one("account.journal", ondelete="set null", index=True)
    move_id = fields.Many2one("account.move", ondelete="set null", index=True)
    move_line_id = fields.Many2one("account.move.line", ondelete="set null", index=True)
    source_type = fields.Selection(SOURCE_SELECTION, index=True)
    date = fields.Date(index=True)
    partner_id = fields.Many2one("res.partner", ondelete="set null")
    label = fields.Char(required=True)

    opening_balance = fields.Monetary(currency_field="currency_id")
    debit = fields.Monetary(currency_field="currency_id")
    credit = fields.Monetary(currency_field="currency_id")
    balance = fields.Monetary(currency_field="currency_id")
    running_balance = fields.Monetary(currency_field="currency_id")
    natural_balance = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_natural_balance",
        store=True,
    )
    record_count = fields.Integer(default=0)

    @api.depends("balance", "running_balance", "account_group", "line_kind")
    def _compute_natural_balance(self):
        for record in self:
            base = (
                record.running_balance
                if record.line_kind == "move_line"
                else record.balance
            )
            if record.account_group in ("liability", "equity", "income"):
                record.natural_balance = -base
            else:
                record.natural_balance = base

    def action_open_source(self):
        self.ensure_one()
        if self.move_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Journal Entry"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": self.move_id.id,
            }

        domain = [("company_id", "=", self.company_id.id)]
        if self.line_kind == "result_summary":
            domain.extend([
                ("account_id.internal_group", "in", ("income", "expense")),
                ("date", ">=", self.statement_id._fiscal_year_start()),
            ])
        if self.account_id:
            domain.append(("account_id", "=", self.account_id.id))
        if self.journal_id:
            domain.append(("move_id.journal_id", "=", self.journal_id.id))
        if self.source_type:
            domain.append(("clinic_accounting_source", "=", self.source_type))
        if self.statement_id.statement_type == "balance_sheet":
            domain.append(("date", "<=", self.statement_id.date_to))
        else:
            domain.extend([
                ("date", ">=", self.statement_id.date_from),
                ("date", "<=", self.statement_id.date_to),
            ])
        if self.statement_id.posted_only:
            domain.append(("move_id.state", "=", "posted"))

        return {
            "type": "ir.actions.act_window",
            "name": self.label,
            "res_model": "account.move.line",
            "view_mode": "list",
            "domain": domain,
        }

    def action_open_statement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Statement"),
            "res_model": "clinic.accounting.statement",
            "view_mode": "form",
            "res_id": self.statement_id.id,
        }
