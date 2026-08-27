import ast

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicFinancePosition(models.Model):
    """Company liquidity/exposure snapshot across Finance, AR, AP and Wallet."""

    _name = "clinic.finance.position"
    _description = "Clinic Finance Treasury Position"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "as_of_date desc, id desc"
    _check_company_auto = True

    _company_date_unique = models.Constraint(
        "UNIQUE(company_id, as_of_date)",
        "Only one Treasury Position is allowed per company and date.",
    )

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    as_of_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    state = fields.Selection(
        [("draft", "Draft"), ("refreshed", "Refreshed"), ("locked", "Locked")],
        default="draft", required=True, tracking=True, index=True,
    )
    line_ids = fields.One2many(
        "clinic.finance.position.line", "position_id", string="Position Breakdown", copy=False
    )

    total_liquidity = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True
    )
    ar_outstanding = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True
    )
    ap_outstanding = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True
    )
    wallet_liability = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True
    )
    net_after_payables = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True
    )
    net_after_wallet = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True
    )

    cashflow_id = fields.Many2one(
        "clinic.cashflow", readonly=True, copy=False, check_company=True
    )
    forecast_ending_balance = fields.Monetary(
        currency_field="currency_id", compute="_compute_forecast_balance"
    )
    last_refreshed_at = fields.Datetime(readonly=True)
    note = fields.Text()

    @api.depends("line_ids.amount", "line_ids.line_type")
    def _compute_totals(self):
        for record in self:
            liquidity = sum(record.line_ids.filtered(lambda l: l.line_type == "liquidity").mapped("amount"))
            ar = sum(record.line_ids.filtered(lambda l: l.line_type == "ar").mapped("amount"))
            ap = sum(record.line_ids.filtered(lambda l: l.line_type == "ap").mapped("amount"))
            wallet = sum(record.line_ids.filtered(lambda l: l.line_type == "wallet").mapped("amount"))
            record.total_liquidity = liquidity
            record.ar_outstanding = ar
            record.ap_outstanding = ap
            record.wallet_liability = wallet
            record.net_after_payables = liquidity + ar - ap
            record.net_after_wallet = liquidity + ar - ap - wallet

    @api.depends("cashflow_id.ending_balance", "cashflow_id.currency_id", "as_of_date", "company_id")
    def _compute_forecast_balance(self):
        for record in self:
            if record.cashflow_id:
                record.forecast_ending_balance = record.cashflow_id.currency_id._convert(
                    record.cashflow_id.ending_balance,
                    record.currency_id,
                    record.company_id,
                    record.as_of_date,
                )
            else:
                record.forecast_ending_balance = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"].with_company(company)
                    .next_by_code("clinic.finance.position") or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        system_fields = {"state", "cashflow_id", "last_refreshed_at"}
        if system_fields.intersection(vals) and not self.env.context.get("finance_transition"):
            raise AccessError(_("Treasury workflow and source snapshot fields are controlled by Finance actions."))
        if {"company_id", "as_of_date"}.intersection(vals):
            for record in self:
                if record.state == "locked":
                    raise UserError(_("Locked Treasury Positions are immutable."))
        return super().write(vals)

    def _require_finance_user(self):
        if self.env.su:
            return
        if not self.env.user.has_group("clinic_finance.group_clinic_finance_user"):
            raise AccessError(_("You do not have permission to refresh Finance positions."))

    def _convert_to_company(self, amount, currency):
        self.ensure_one()
        if not currency or currency == self.currency_id:
            return amount
        return currency._convert(amount, self.currency_id, self.company_id, self.as_of_date)

    # Snapshot lines are regenerated from source systems; users cannot maintain treasury numbers manually.
    def action_refresh(self):
        self._require_finance_user()
        PositionLine = self.env["clinic.finance.position.line"]
        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked positions are historical snapshots. Create a new position instead."))
            record.line_ids.sudo().unlink()
            values = record._prepare_liquidity_lines()
            if record.company_id.finance_position_include_ar:
                values.append(record._prepare_ar_line())
            if record.company_id.finance_position_include_ap:
                values.append(record._prepare_ap_line())
            if record.company_id.finance_position_include_wallet:
                values.append(record._prepare_wallet_line())
            PositionLine.sudo().create([vals for vals in values if vals])

            cashflow = self.env["clinic.cashflow"].search([
                ("company_id", "=", record.company_id.id),
                ("state", "=", "generated"),
            ], order="is_pinned desc, as_of_date desc, id desc", limit=1)

            record.with_context(finance_transition=True).write({
                "state": "refreshed",
                "cashflow_id": cashflow.id or False,
                "last_refreshed_at": fields.Datetime.now(),
            })
        return True

    def _prepare_liquidity_lines(self):
        self.ensure_one()
        result = []
        accounts = self.env["clinic.finance.account"].search([
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("active", "suspended")),
        ], order="sequence, code, id")
        for account in accounts:
            result.append({
                "position_id": self.id,
                "line_type": "liquidity",
                "name": account.display_name,
                "finance_account_id": account.id,
                "amount": account._book_balance_at(self.as_of_date),
                "record_count": 1,
                "source_model": "clinic.finance.account",
                "source_domain": repr([("id", "=", account.id)]),
            })
        return result

    # AR exposure is read from the authoritative AR residual, then converted into company currency.
    def _prepare_ar_line(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date", "<=", self.as_of_date),
        ]
        invoices = self.env["clinic.ar.invoice"].search(domain)
        total = sum(
            self._convert_to_company(invoice.amount_residual, invoice.currency_id)
            for invoice in invoices
        )
        return {
            "position_id": self.id,
            "line_type": "ar",
            "name": _("Accounts Receivable Outstanding"),
            "amount": total,
            "record_count": len(invoices),
            "source_model": "clinic.ar.invoice",
            "source_domain": repr(domain),
        }

    # AP exposure remains owned by clinic_ap; Finance aggregates only posted/partial residual obligations.
    def _prepare_ap_line(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("posted", "partial")),
            ("amount_residual", ">", 0),
            ("invoice_date", "<=", self.as_of_date),
        ]
        documents = self.env["clinic.ap"].search(domain)
        total = sum(
            self._convert_to_company(document.amount_residual, document.currency_id)
            for document in documents
        )
        return {
            "position_id": self.id,
            "line_type": "ap",
            "name": _("Accounts Payable Outstanding"),
            "amount": total,
            "record_count": len(documents),
            "source_model": "clinic.ap",
            "source_domain": repr(domain),
        }

    # Wallet balance is treated as a patient liability in treasury visibility, not as free clinic cash.
    def _prepare_wallet_line(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("open", "suspended")),
        ]
        wallets = self.env["clinic.wallet"].search(domain)
        total = sum(
            self._convert_to_company(wallet.balance, wallet.currency_id)
            for wallet in wallets
        )
        return {
            "position_id": self.id,
            "line_type": "wallet",
            "name": _("Patient Wallet Liability"),
            "amount": total,
            "record_count": len(wallets),
            "source_model": "clinic.wallet",
            "source_domain": repr(domain),
        }

    def action_lock(self):
        if not self.env.user.has_group("clinic_finance.group_clinic_finance_manager"):
            raise AccessError(_("Only Finance Managers can lock Treasury Positions."))
        for record in self:
            if record.state != "refreshed":
                raise UserError(_("Refresh the Treasury Position before locking it."))
            record.with_context(finance_transition=True).write({"state": "locked"})
        return True

    def action_view_liquidity_accounts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Finance Accounts"),
            "res_model": "clinic.finance.account", "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id)],
        }

    def action_view_ar(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("AR Outstanding"),
            "res_model": "clinic.ar.invoice", "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "posted"),
                ("amount_residual", ">", 0),
            ],
        }

    def action_view_ap(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("AP Outstanding"),
            "res_model": "clinic.ap", "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("state", "in", ("posted", "partial")),
                ("amount_residual", ">", 0),
            ],
        }

    def action_view_wallets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Wallet Liability"),
            "res_model": "clinic.wallet", "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("state", "in", ("open", "suspended")),
            ],
        }

    def action_open_cashflow(self):
        self.ensure_one()
        if not self.cashflow_id:
            raise UserError(_("No AP Cashflow Forecast is linked."))
        return {
            "type": "ir.actions.act_window", "name": _("Cashflow Forecast"),
            "res_model": "clinic.cashflow", "view_mode": "form", "res_id": self.cashflow_id.id,
        }

    def action_print_position(self):
        self.ensure_one()
        return self.env.ref("clinic_finance.action_report_treasury_position").report_action(self)

    @api.model
    def _cron_daily_position(self):
        companies = self.env["res.company"].sudo().search([
            ("finance_auto_daily_position", "=", True)
        ])
        today = fields.Date.context_today(self)
        for company in companies:
            position = self.sudo().search([
                ("company_id", "=", company.id),
                ("as_of_date", "=", today),
            ], limit=1)
            if not position:
                position = self.sudo().create({
                    "company_id": company.id,
                    "as_of_date": today,
                })
            if position.state != "locked":
                position.sudo().action_refresh()


class ClinicFinancePositionLine(models.Model):
    """Breakdown line for a Treasury Position snapshot."""

    _name = "clinic.finance.position.line"
    _description = "Clinic Finance Treasury Position Line"
    _order = "line_type, id"

    position_id = fields.Many2one(
        "clinic.finance.position", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="position_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        related="position_id.currency_id", store=True, readonly=True
    )
    as_of_date = fields.Date(
        related="position_id.as_of_date", store=True, readonly=True, index=True
    )
    line_type = fields.Selection(
        [
            ("liquidity", "Cash / Bank Liquidity"), ("ar", "Accounts Receivable"),
            ("ap", "Accounts Payable"), ("wallet", "Wallet Liability"),
        ],
        required=True, index=True,
    )
    name = fields.Char(required=True)
    finance_account_id = fields.Many2one(
        "clinic.finance.account", check_company=True, ondelete="set null"
    )
    amount = fields.Monetary(currency_field="currency_id")
    record_count = fields.Integer(default=0)
    source_model = fields.Char()
    source_domain = fields.Char()
    note = fields.Char()

    # Source domains are parsed with literal_eval; never execute stored domain text as Python code.
    def action_open_source(self):
        self.ensure_one()
        if self.finance_account_id:
            return {
                "type": "ir.actions.act_window", "name": _("Finance Account"),
                "res_model": "clinic.finance.account", "view_mode": "form",
                "res_id": self.finance_account_id.id,
            }
        if not self.source_model:
            raise UserError(_("This Treasury Position line has no source model."))
        domain = []
        if self.source_domain:
            try:
                parsed = ast.literal_eval(self.source_domain)
                domain = parsed if isinstance(parsed, list) else []
            except (ValueError, SyntaxError):
                domain = []
        return {
            "type": "ir.actions.act_window", "name": self.name,
            "res_model": self.source_model, "view_mode": "list,form", "domain": domain,
        }

    def action_open_position(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Treasury Position"),
            "res_model": "clinic.finance.position", "view_mode": "form",
            "res_id": self.position_id.id,
        }
