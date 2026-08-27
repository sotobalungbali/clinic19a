from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


class ClinicFinanceCashSession(models.Model):
    """Controlled opening/counting/closing workflow for physical cash."""

    _name = "clinic.finance.cash.session"
    _description = "Clinic Finance Cash Session"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.finance.company.mixin"]
    _order = "opened_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    finance_account_id = fields.Many2one(
        "clinic.finance.account", required=True, check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id), ('journal_type', '=', 'cash'), ('state', '=', 'active')]",
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    state = fields.Selection(
        [
            ("draft", "Draft"), ("open", "Open"), ("closing", "Closing Review"),
            ("closed", "Closed"), ("cancelled", "Cancelled"),
        ],
        default="draft", required=True, tracking=True, index=True,
    )
    opened_by_id = fields.Many2one("res.users", readonly=True)
    opened_at = fields.Datetime(readonly=True)
    opening_book_balance = fields.Monetary(currency_field="currency_id", readonly=True)
    closing_requested_by_id = fields.Many2one("res.users", readonly=True)
    closing_requested_at = fields.Datetime(readonly=True)
    # Expected closing balance is snapshotted from posted GL liquidity before physical cash is compared.
    expected_closing_balance = fields.Monetary(currency_field="currency_id", readonly=True)
    count_line_ids = fields.One2many(
        "clinic.finance.cash.count.line", "session_id", string="Cash Count", copy=True
    )
    counted_total = fields.Monetary(
        currency_field="currency_id", compute="_compute_counted_total", store=True
    )
    variance = fields.Monetary(
        currency_field="currency_id", compute="_compute_variance", store=True
    )
    tolerance = fields.Monetary(
        currency_field="currency_id",
        related="company_id.finance_cash_variance_tolerance", readonly=True,
    )
    closed_by_id = fields.Many2one("res.users", readonly=True)
    closed_at = fields.Datetime(readonly=True)
    variance_transaction_id = fields.Many2one(
        "clinic.finance.transaction", readonly=True, copy=False, check_company=True
    )
    note = fields.Text()
    transaction_count = fields.Integer(compute="_compute_transaction_count")

    @api.depends("count_line_ids.subtotal")
    def _compute_counted_total(self):
        for record in self:
            record.counted_total = sum(record.count_line_ids.mapped("subtotal"))

    @api.depends("counted_total", "expected_closing_balance")
    def _compute_variance(self):
        for record in self:
            record.variance = record.counted_total - record.expected_closing_balance

    def _compute_transaction_count(self):
        Transaction = self.env["clinic.finance.transaction"]
        for record in self:
            record.transaction_count = Transaction.search_count([("cash_session_id", "=", record.id)])

    @api.onchange("finance_account_id")
    def _onchange_finance_account(self):
        for record in self:
            if record.finance_account_id:
                record.company_id = record.finance_account_id.company_id
                record.branch_id = record.finance_account_id.branch_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            account = self.env["clinic.finance.account"].browse(vals.get("finance_account_id"))
            company = account.company_id if account.exists() else self.env.company
            vals.setdefault("company_id", company.id)
            if account.exists():
                vals.setdefault("branch_id", account.branch_id.id)
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"].with_company(company)
                    .next_by_code("clinic.finance.cash.session") or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        system_fields = {
            "state", "opened_by_id", "opened_at", "opening_book_balance",
            "closing_requested_by_id", "closing_requested_at",
            "expected_closing_balance", "closed_by_id", "closed_at",
            "variance_transaction_id",
        }
        if system_fields.intersection(vals) and not self.env.context.get("finance_transition"):
            raise AccessError(_("Cash Session workflow, snapshot and audit fields are controlled by Finance actions."))
        if {"finance_account_id", "company_id", "branch_id"}.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("Cash Session scope can only be edited in Draft."))
        return super().write(vals)

    @api.constrains("finance_account_id")
    def _check_cash_journal(self):
        for record in self:
            if record.finance_account_id and record.finance_account_id.journal_type != "cash":
                raise ValidationError(_("Cash Sessions require a Finance account mapped to a Cash journal."))

    def action_open_session(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_cashier")
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft Cash Sessions can be opened."))
            other = self.search_count([
                ("id", "!=", record.id), ("finance_account_id", "=", record.finance_account_id.id),
                ("state", "in", ("open", "closing")),
            ])
            if other:
                raise UserError(_("This cash account already has an open/closing session."))
            record.with_context(finance_transition=True).write({
                "state": "open", "opened_by_id": self.env.user.id,
                "opened_at": fields.Datetime.now(),
                "opening_book_balance": record.finance_account_id.book_balance,
            })
        return True

    def action_request_close(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_cashier")
        for record in self:
            if record.state != "open":
                raise UserError(_("Only Open Cash Sessions can enter closing review."))
            record.with_context(finance_transition=True).write({
                "state": "closing", "closing_requested_by_id": self.env.user.id,
                "closing_requested_at": fields.Datetime.now(),
                "expected_closing_balance": record.finance_account_id.book_balance,
            })
        return True

    # Variance above tolerance escalates to an Approver even when the Cashier can normally close sessions.
    def action_close_session(self):
        for record in self:
            if record.state != "closing":
                raise UserError(_("Only sessions in Closing Review can be closed."))
            excessive = abs(record.variance) > record.tolerance + record.currency_id.rounding
            if excessive:
                record._finance_require_group(
                    "clinic_finance.group_clinic_finance_approver",
                    _("Variance exceeds tolerance; a Finance Approver must close this session."),
                )
            else:
                record._finance_require_group("clinic_finance.group_clinic_finance_cashier")
            record.with_context(finance_transition=True).write({
                "state": "closed", "closed_by_id": self.env.user.id,
                "closed_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state == "closed":
                raise UserError(_("A Closed Cash Session cannot be cancelled."))
            record.with_context(finance_transition=True).write({"state": "cancelled"})
        return True

    def action_create_variance_adjustment(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state != "closed":
                raise UserError(_("Close the Cash Session before creating a variance adjustment."))
            if record.variance_transaction_id:
                raise UserError(_("A variance adjustment already exists."))
            if float_is_zero(record.variance, precision_rounding=record.currency_id.rounding):
                raise UserError(_("There is no cash variance to adjust."))
            positive = record.variance > 0
            counterpart = (
                record.company_id.finance_variance_gain_account_id
                if positive else record.company_id.finance_variance_loss_account_id
            )
            if not counterpart:
                raise UserError(_("Configure Finance cash variance gain/loss accounts first."))
            tx = self.env["clinic.finance.transaction"].create({
                "finance_account_id": record.finance_account_id.id,
                "company_id": record.company_id.id,
                "branch_id": record.branch_id.id,
                "direction": "in" if positive else "out",
                "operation_type": "cash_variance",
                "amount": abs(record.variance),
                "counterpart_account_id": counterpart.id,
                "posting_policy": "create_move",
                "cash_session_id": record.id,
                "origin_ref": f"clinic.finance.cash.session,{record.id}",
                "reference": record.name,
                "note": _("Cash count variance adjustment."),
            })
            tx.action_submit()
            if tx.state == "submitted":
                tx.action_approve()
            record.with_context(finance_transition=True).write({"variance_transaction_id": tx.id})
        return self.action_open_variance_transaction()

    def action_open_variance_transaction(self):
        self.ensure_one()
        if not self.variance_transaction_id:
            raise UserError(_("No variance adjustment has been created."))
        return {
            "type": "ir.actions.act_window", "name": _("Cash Variance Transaction"),
            "res_model": "clinic.finance.transaction", "view_mode": "form",
            "res_id": self.variance_transaction_id.id,
        }

    def action_new_transaction(self):
        self.ensure_one()
        if self.state != "open":
            raise UserError(_("Cash Session transactions can only be created while Open."))
        return {
            "type": "ir.actions.act_window", "name": _("New Cash Transaction"),
            "res_model": "clinic.finance.transaction", "view_mode": "form",
            "context": {
                "default_finance_account_id": self.finance_account_id.id,
                "default_cash_session_id": self.id,
                "default_company_id": self.company_id.id,
                "default_branch_id": self.branch_id.id,
            },
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Cash Session Transactions"),
            "res_model": "clinic.finance.transaction", "view_mode": "list,form",
            "domain": [("cash_session_id", "=", self.id)],
        }


class ClinicFinanceCashCountLine(models.Model):
    """Denomination line used during a controlled cash count."""

    _name = "clinic.finance.cash.count.line"
    _description = "Clinic Finance Cash Count Line"
    _order = "denomination desc, id"

    _denomination_positive = models.Constraint(
        "CHECK(denomination > 0)", "Cash denomination must be greater than zero."
    )
    _quantity_nonnegative = models.Constraint(
        "CHECK(quantity >= 0)", "Cash-count quantity cannot be negative."
    )

    session_id = fields.Many2one(
        "clinic.finance.cash.session", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="session_id.company_id", store=True, readonly=True, index=True)
    branch_id = fields.Many2one(related="session_id.branch_id", store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related="session_id.currency_id", store=True, readonly=True)
    denomination = fields.Monetary(currency_field="currency_id", required=True)
    quantity = fields.Integer(default=0, required=True)
    subtotal = fields.Monetary(
        currency_field="currency_id", compute="_compute_subtotal", store=True
    )
    note = fields.Char()

    @api.depends("denomination", "quantity")
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.denomination * record.quantity

    # Denomination lines remain mutable only while their parent session is operationally editable.
    @api.model_create_multi
    def create(self, vals_list):
        sessions = self.env["clinic.finance.cash.session"].browse(
            [vals.get("session_id") for vals in vals_list if vals.get("session_id")]
        )
        if sessions.filtered(lambda session: session.state not in ("draft", "open", "closing")):
            raise AccessError(_("Cash Count lines can only be created while the session is editable."))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda line: line.session_id.state not in ("draft", "open", "closing")):
            raise AccessError(_("Closed or cancelled Cash Count lines are immutable."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda line: line.session_id.state not in ("draft", "open", "closing")):
            raise AccessError(_("Closed or cancelled Cash Count lines cannot be deleted."))
        return super().unlink()

    def action_zero_quantity(self):
        for record in self:
            if record.session_id.state not in ("draft", "open", "closing"):
                raise UserError(_("Closed Cash Count lines cannot be changed."))
            record.quantity = 0
        return True

    def action_open_session(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Cash Session"),
            "res_model": "clinic.finance.cash.session", "view_mode": "form",
            "res_id": self.session_id.id,
        }
