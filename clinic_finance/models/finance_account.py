from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicFinanceAccount(models.Model):
    """Operational wrapper around an Odoo liquidity journal."""

    _name = "clinic.finance.account"
    _description = "Clinic Finance Operating Account"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.finance.company.mixin"]
    _order = "company_id, sequence, code, name"
    _check_company_auto = True

    _journal_unique = models.Constraint(
        "UNIQUE(journal_id)",
        "An Odoo journal can only be mapped to one Clinic Finance account.",
    )
    _minimum_balance_nonnegative = models.Constraint(
        "CHECK(minimum_balance >= 0)",
        "Minimum balance cannot be negative.",
    )
    _maximum_cash_nonnegative = models.Constraint(
        "CHECK(maximum_cash_balance >= 0)",
        "Maximum cash balance cannot be negative.",
    )

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    # Standard Odoo journal remains the liquidity/accounting backbone; Finance only wraps operations.
    journal_id = fields.Many2one(
        "account.journal", required=True, check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id), ('type', 'in', ('cash', 'bank', 'credit'))]",
        tracking=True,
    )
    journal_type = fields.Selection(related="journal_id.type", store=True, readonly=True)
    journal_currency_id = fields.Many2one(related="journal_id.currency_id", readonly=True)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True,
        string="Company Currency",
    )
    liquidity_account_id = fields.Many2one(
        "account.account", related="journal_id.default_account_id", readonly=True,
        string="Liquidity Account",
    )
    custodian_user_id = fields.Many2one(
        "res.users", string="Custodian", domain="[('share', '=', False)]", tracking=True
    )
    state = fields.Selection(
        [("active", "Active"), ("suspended", "Suspended"), ("closed", "Closed")],
        default="active", required=True, tracking=True, index=True,
    )
    minimum_balance = fields.Monetary(currency_field="currency_id", default=0.0)
    maximum_cash_balance = fields.Monetary(currency_field="currency_id", default=0.0)
    book_balance = fields.Monetary(
        currency_field="currency_id", compute="_compute_book_balance", string="Book Balance"
    )
    low_balance = fields.Boolean(
        compute="_compute_book_balance",
        search="_search_low_balance",
    )
    cash_ceiling_exceeded = fields.Boolean(compute="_compute_book_balance")
    notes = fields.Text()
    transaction_count = fields.Integer(compute="_compute_counts")
    open_session_count = fields.Integer(compute="_compute_counts")

    @api.depends(
        "journal_id", "liquidity_account_id", "company_id", "branch_id",
        "minimum_balance", "maximum_cash_balance",
    )
    def _compute_book_balance(self):
        today = fields.Date.context_today(self)
        for record in self:
            balance = record._book_balance_at(today)
            record.book_balance = balance
            record.low_balance = bool(record.minimum_balance and balance < record.minimum_balance)
            record.cash_ceiling_exceeded = bool(
                record.journal_type == "cash"
                and record.maximum_cash_balance
                and balance > record.maximum_cash_balance
            )

    # Read posted move-line balances instead of maintaining a second proprietary cash ledger.
    def _book_balance_at(self, as_of_date):
        self.ensure_one()
        if not self.liquidity_account_id:
            return 0.0
        domain = [
            ("account_id", "=", self.liquidity_account_id.id),
            ("company_id", "=", self.company_id.id),
            ("move_id.state", "=", "posted"),
            ("date", "<=", as_of_date),
        ]
        if self.branch_id and "branch_id" in self.env["account.move.line"]._fields:
            domain.append(("branch_id", "=", self.branch_id.id))
        return sum(self.env["account.move.line"].sudo().search(domain).mapped("balance"))

    @api.model
    def _search_low_balance(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Low Balance can only be searched with a boolean equality condition."))
        candidates = self.search([("minimum_balance", ">", 0)])
        low_ids = candidates.filtered(lambda account: account.book_balance < account.minimum_balance).ids
        wants_low = value if operator == "=" else not value
        return [("id", "in" if wants_low else "not in", low_ids)]

    def _compute_counts(self):
        Transaction = self.env["clinic.finance.transaction"]
        Session = self.env["clinic.finance.cash.session"]
        for record in self:
            record.transaction_count = Transaction.search_count([("finance_account_id", "=", record.id)])
            record.open_session_count = Session.search_count([
                ("finance_account_id", "=", record.id),
                ("state", "in", ("open", "closing")),
            ])

    @api.onchange("journal_id")
    def _onchange_journal(self):
        for record in self:
            if record.journal_id:
                record.company_id = record.journal_id.company_id

    @api.constrains("journal_id", "company_id")
    def _check_journal_company_and_account(self):
        for record in self:
            if record.journal_id.company_id != record.company_id:
                raise ValidationError(_("Finance account and journal must belong to the same company."))
            if not record.journal_id.default_account_id:
                raise ValidationError(_("The selected journal must have a default liquidity account."))

    def action_activate(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        self.with_context(finance_transition=True).write({"state": "active", "active": True})

    def action_suspend(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        self.with_context(finance_transition=True).write({"state": "suspended"})

    def action_close(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        if self.filtered(lambda r: r.open_session_count):
            raise UserError(_("Close all cash sessions before closing a Finance account."))
        self.with_context(finance_transition=True).write({"state": "closed", "active": False})

    def action_new_receipt(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("New Internal Receipt"),
            "res_model": "clinic.finance.transaction", "view_mode": "form",
            "context": {
                "default_finance_account_id": self.id, "default_company_id": self.company_id.id,
                "default_branch_id": self.branch_id.id, "default_direction": "in",
                "default_operation_type": "receipt",
            },
        }

    def action_new_disbursement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("New Internal Disbursement"),
            "res_model": "clinic.finance.transaction", "view_mode": "form",
            "context": {
                "default_finance_account_id": self.id, "default_company_id": self.company_id.id,
                "default_branch_id": self.branch_id.id, "default_direction": "out",
                "default_operation_type": "disbursement",
            },
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Finance Transactions"),
            "res_model": "clinic.finance.transaction", "view_mode": "list,form,pivot,graph",
            "domain": [("finance_account_id", "=", self.id)],
        }

    def action_view_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Cash Sessions"),
            "res_model": "clinic.finance.cash.session", "view_mode": "list,form",
            "domain": [("finance_account_id", "=", self.id)],
        }

    def action_open_journal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Accounting Journal"),
            "res_model": "account.journal", "view_mode": "form", "res_id": self.journal_id.id,
        }

    def action_view_journal_entries(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Journal Entries"),
            "res_model": "account.move", "view_mode": "list,form",
            "domain": [("journal_id", "=", self.journal_id.id)],
        }

    # Status changes must pass workflow methods so direct RPC writes cannot bypass governance.
    def write(self, vals):
        if "state" in vals and not self.env.context.get("finance_transition"):
            raise UserError(_("Use the Finance Account workflow buttons to change status."))
        return super().write(vals)
