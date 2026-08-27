import ast
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicAccountingClose(models.Model):
    """Preflight evidence and governed application of Odoo's native fiscal lock date."""

    _name = "clinic.accounting.close"
    _description = "Clinic Accounting Period Close"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, id desc"
    _check_company_auto = True

    _date_range_check = models.Constraint(
        "CHECK(date_from <= date_to)",
        "Accounting close start date must be before or equal to end date.",
    )
    _company_period_unique = models.Constraint(
        "UNIQUE(company_id, date_from, date_to)",
        "An Accounting Close already exists for this company and period.",
    )
    _company_state_idx = models.Index("(company_id, state, date_to)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
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
    period_type = fields.Selection(
        [
            ("month", "Monthly Close"),
            ("quarter", "Quarterly Close"),
            ("year", "Year-End Close"),
            ("custom", "Custom Period"),
        ],
        default="month",
        required=True,
        tracking=True,
        index=True,
    )
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("preflight", "Preflight"),
            ("ready", "Ready to Close"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    check_ids = fields.One2many(
        "clinic.accounting.close.check",
        "close_id",
        string="Close Checks",
        copy=False,
    )
    blocking_count = fields.Integer(compute="_compute_check_counts", store=True)
    warning_count = fields.Integer(compute="_compute_check_counts", store=True)
    clear_count = fields.Integer(compute="_compute_check_counts", store=True)

    last_preflight_at = fields.Datetime(readonly=True)
    last_preflight_by_id = fields.Many2one("res.users", readonly=True)
    native_lock_date_before = fields.Date(readonly=True)
    native_lock_date_after = fields.Date(readonly=True)
    closed_at = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True)
    notes = fields.Text()

    @api.depends("check_ids.status", "check_ids.severity")
    def _compute_check_counts(self):
        for record in self:
            record.blocking_count = len(
                record.check_ids.filtered(
                    lambda check: check.status == "open" and check.severity == "blocking"
                )
            )
            record.warning_count = len(
                record.check_ids.filtered(
                    lambda check: check.status == "open" and check.severity == "warning"
                )
            )
            record.clear_count = len(
                record.check_ids.filtered(lambda check: check.status == "clear")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.accounting.close")
                    or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        editable = {"company_id", "period_type", "date_from", "date_to", "notes"}
        system_fields = {
            "state",
            "last_preflight_at",
            "last_preflight_by_id",
            "native_lock_date_before",
            "native_lock_date_after",
            "closed_at",
            "closed_by_id",
        }
        if system_fields.intersection(vals) and not self.env.context.get("accounting_transition"):
            raise AccessError(
                _("Close workflow, preflight audit, and native-lock evidence are controlled by Accounting actions.")
            )
        if editable.intersection(vals):
            for record in self:
                if record.state not in ("draft", "cancelled"):
                    raise UserError(_("Close-period parameters can only be edited in Draft or Cancelled."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda close: close.state not in ("draft", "cancelled")):
            raise UserError(_("Only Draft or Cancelled Accounting Close records can be deleted."))
        return super().unlink()

    def _preflight_items(self):
        self.ensure_one()

        end_of_day = datetime.combine(self.date_to, time.max)
        next_day = self.date_to + timedelta(days=1)

        items = []

        def add(code, title, severity, model_name, domain, note):
            count = self.env[model_name].sudo().search_count(domain)
            items.append({
                "close_id": self.id,
                "code": code,
                "title": title,
                "severity": severity,
                "model_name": model_name,
                "domain_text": repr(domain),
                "record_count": count,
                "status": "open" if count else "clear",
                "note": note,
            })

        # Core Accounting readiness.
        add(
            "draft_moves",
            _("Draft Journal Entries"),
            "blocking",
            "account.move",
            [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "draft"),
                ("date", "<=", self.date_to),
            ],
            _("Post or remove all draft accounting entries dated on or before the close date."),
        )

        # Finance pipeline must not leave approved economic events unposted.
        add(
            "finance_transactions",
            _("Unfinished Finance Transactions"),
            "blocking",
            "clinic.finance.transaction",
            [
                ("company_id", "=", self.company_id.id),
                ("transaction_date", "<=", self.date_to),
                ("state", "in", ("draft", "submitted", "approved")),
            ],
            _("Finish or cancel Finance transactions before closing the period."),
        )
        add(
            "finance_transfers",
            _("Unfinished Finance Transfers"),
            "blocking",
            "clinic.finance.transfer",
            [
                ("company_id", "=", self.company_id.id),
                ("transfer_date", "<=", self.date_to),
                ("state", "in", ("draft", "submitted", "approved")),
            ],
            _("Finish or cancel Finance transfers before closing the period."),
        )
        add(
            "open_cash_sessions",
            _("Open / Closing Cash Sessions"),
            "blocking",
            "clinic.finance.cash.session",
            [
                ("company_id", "=", self.company_id.id),
                ("opened_at", "<", fields.Datetime.to_string(datetime.combine(next_day, time.min))),
                ("state", "in", ("open", "closing")),
            ],
            _("Physical cash sessions opened in the period must be closed first."),
        )

        # Accounting-owned manual adjustments are part of the close boundary.
        add(
            "accounting_adjustments",
            _("Unposted Accounting Adjustments"),
            "blocking",
            "clinic.accounting.adjustment",
            [
                ("company_id", "=", self.company_id.id),
                ("adjustment_date", "<=", self.date_to),
                ("state", "in", ("draft", "submitted", "approved")),
            ],
            _("Post or cancel Accounting Adjustments before applying the period lock."),
        )

        # Cross-addon traceability checks identify operational records that claim
        # to be posted but have no standard Odoo move.
        add(
            "ap_without_move",
            _("Posted AP Documents Without Journal Entry"),
            "blocking",
            "clinic.ap",
            [
                ("company_id", "=", self.company_id.id),
                ("invoice_date", "<=", self.date_to),
                ("state", "in", ("posted", "partial")),
                ("move_id", "=", False),
            ],
            _("Every posted/partial AP document must be linked to its Odoo journal entry."),
        )
        add(
            "ar_without_move",
            _("Posted AR Invoices Without Journal Entry"),
            "blocking",
            "clinic.ar.invoice",
            [
                ("company_id", "=", self.company_id.id),
                ("invoice_date", "<=", self.date_to),
                ("state", "=", "posted"),
                ("move_id", "=", False),
            ],
            _("Every posted AR invoice must be linked to its Odoo journal entry."),
        )
        add(
            "billing_without_move",
            _("Posted / Paid Billing Records Without Journal Entry"),
            "blocking",
            "clinic.billing.invoice",
            [
                ("company_id", "=", self.company_id.id),
                ("invoice_date", "<=", self.date_to),
                ("state", "in", ("posted", "paid")),
                ("move_id", "=", False),
            ],
            _("Every posted or paid Billing record must be linked to its Odoo journal entry."),
        )
        add(
            "finance_posted_without_move",
            _("Posted Finance Transactions Without Journal Entry"),
            "blocking",
            "clinic.finance.transaction",
            [
                ("company_id", "=", self.company_id.id),
                ("transaction_date", "<=", self.date_to),
                ("state", "=", "posted"),
                ("posting_policy", "=", "create_move"),
                ("move_id", "=", False),
            ],
            _("Finance transactions configured to create accounting must have an Odoo journal entry."),
        )
        add(
            "finance_transfer_without_move",
            _("Posted Finance Transfers Without Journal Entry"),
            "blocking",
            "clinic.finance.transfer",
            [
                ("company_id", "=", self.company_id.id),
                ("transfer_date", "<=", self.date_to),
                ("state", "=", "posted"),
                ("move_id", "=", False),
            ],
            _("Every posted Finance transfer must have an Odoo journal entry."),
        )
        add(
            "wallet_without_move",
            _("Posted Wallet Transactions With Journal But No Entry"),
            "warning",
            "clinic.wallet.transaction",
            [
                ("company_id", "=", self.company_id.id),
                ("date", "<=", self.date_to),
                ("state", "=", "posted"),
                ("journal_id", "!=", False),
                ("move_id", "=", False),
            ],
            _("Review Wallet transactions that identify a journal but have no linked accounting move."),
        )

        # Reconciliation can be configured as a warning or hard blocker.
        receivable_severity = (
            "blocking"
            if self.company_id.clinic_accounting_close_require_reconciled_receivable
            else "warning"
        )
        payable_severity = (
            "blocking"
            if self.company_id.clinic_accounting_close_require_reconciled_payable
            else "warning"
        )
        add(
            "unreconciled_receivable",
            _("Unreconciled Receivable Items"),
            receivable_severity,
            "account.move.line",
            [
                ("company_id", "=", self.company_id.id),
                ("move_id.state", "=", "posted"),
                ("date", "<=", self.date_to),
                ("account_id.account_type", "=", "asset_receivable"),
                ("reconciled", "=", False),
            ],
            _("Review unreconciled receivable items before closing."),
        )
        add(
            "unreconciled_payable",
            _("Unreconciled Payable Items"),
            payable_severity,
            "account.move.line",
            [
                ("company_id", "=", self.company_id.id),
                ("move_id.state", "=", "posted"),
                ("date", "<=", self.date_to),
                ("account_id.account_type", "=", "liability_payable"),
                ("reconciled", "=", False),
            ],
            _("Review unreconciled payable items before closing."),
        )

        return items

    def action_run_preflight(self):
        self._accounting_require_close_role()
        Check = self.env["clinic.accounting.close.check"].sudo()
        for record in self:
            if record.state == "closed":
                raise UserError(_("A Closed period cannot be re-preflighted."))
            record.check_ids.sudo().unlink()
            items = record._preflight_items()
            if items:
                Check.create(items)
            record.invalidate_recordset(["blocking_count", "warning_count", "clear_count"])
            record.with_context(accounting_transition=True).write({
                "state": "preflight",
                "last_preflight_at": fields.Datetime.now(),
                "last_preflight_by_id": self.env.user.id,
            })
        return True

    def _accounting_require_close_role(self):
        if not (
            self.env.user.has_group("clinic_accounting.group_clinic_accounting_accountant")
            or self.env.user.has_group("clinic_accounting.group_clinic_accounting_manager")
        ):
            raise AccessError(_("You do not have permission to run Accounting close preflight."))

    def action_mark_ready(self):
        self._accounting_require_close_role()
        for record in self:
            if not record.last_preflight_at:
                raise UserError(_("Run Preflight before marking the period Ready."))
            if record.blocking_count:
                raise UserError(_("Resolve all blocking close checks first."))
            record.with_context(accounting_transition=True).write({"state": "ready"})
        return True

    def action_close_period(self):
        self._accounting_require_group_manager()
        for record in self:
            if record.state != "ready":
                raise UserError(_("Only a Ready period can be closed."))

            # Re-run immediately so a stale green preflight cannot be used after
            # new entries were created.
            record.action_run_preflight()
            if record.blocking_count:
                raise UserError(_("New blocking issues were found. Resolve them before closing."))

            before = record.company_id.fiscalyear_lock_date
            target = max(
                fields.Date.to_date(before) if before else record.date_to,
                record.date_to,
            )

            # Odoo 19's native company lock-date validation remains authoritative.
            # Clinic Accounting supplies evidence and workflow; it never bypasses
            # the core accounting lock mechanism.
            record.company_id.sudo().write({"fiscalyear_lock_date": target})

            record.with_context(accounting_transition=True).write({
                "state": "closed",
                "native_lock_date_before": before,
                "native_lock_date_after": record.company_id.fiscalyear_lock_date,
                "closed_at": fields.Datetime.now(),
                "closed_by_id": self.env.user.id,
            })
        return True

    def _accounting_require_group_manager(self):
        if not self.env.user.has_group("clinic_accounting.group_clinic_accounting_manager"):
            raise AccessError(_("Only an Accounting Manager can close an accounting period."))

    def action_cancel(self):
        self._accounting_require_close_role()
        for record in self:
            if record.state == "closed":
                raise UserError(_("A Closed period cannot be cancelled."))
            record.with_context(accounting_transition=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._accounting_require_close_role()
        for record in self:
            if record.state == "closed":
                raise UserError(
                    _("Clinic Accounting does not reopen native Odoo lock dates. Use Odoo's accounting lock controls if a formal exception is required.")
                )
            record.check_ids.sudo().unlink()
            record.with_context(accounting_transition=True).write({
                "state": "draft",
                "last_preflight_at": False,
                "last_preflight_by_id": False,
            })
        return True

    def action_open_company(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Company"),
            "res_model": "res.company",
            "view_mode": "form",
            "res_id": self.company_id.id,
        }

    def action_print_close(self):
        self.ensure_one()
        return self.env.ref("clinic_accounting.action_report_accounting_close").report_action(self)


class ClinicAccountingCloseCheck(models.Model):
    """Generated close-preflight evidence with safe source drill-down."""

    _name = "clinic.accounting.close.check"
    _description = "Clinic Accounting Close Check"
    _order = "severity, code, id"

    _record_count_nonnegative = models.Constraint(
        "CHECK(record_count >= 0)",
        "Close Check record count cannot be negative.",
    )

    close_id = fields.Many2one(
        "clinic.accounting.close",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="close_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    code = fields.Char(required=True, index=True)
    title = fields.Char(required=True)
    severity = fields.Selection(
        [
            ("blocking", "Blocking"),
            ("warning", "Warning"),
            ("info", "Information"),
        ],
        required=True,
        index=True,
    )
    status = fields.Selection(
        [("clear", "Clear"), ("open", "Open")],
        required=True,
        index=True,
    )
    record_count = fields.Integer(default=0)
    model_name = fields.Char()
    domain_text = fields.Text()
    note = fields.Text()

    def action_open_records(self):
        self.ensure_one()
        if not self.model_name or not self.record_count:
            raise UserError(_("There are no source records to open."))
        try:
            domain = ast.literal_eval(self.domain_text or "[]")
        except (ValueError, SyntaxError):
            domain = []
        if not isinstance(domain, list):
            domain = []
        return {
            "type": "ir.actions.act_window",
            "name": self.title,
            "res_model": self.model_name,
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_open_close(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Close"),
            "res_model": "clinic.accounting.close",
            "view_mode": "form",
            "res_id": self.close_id.id,
        }
