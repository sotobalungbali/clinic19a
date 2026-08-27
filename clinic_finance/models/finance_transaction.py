from odoo import api, Command, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFinanceTransaction(models.Model):
    """Governed internal receipt/disbursement with optional standard Odoo posting."""

    _name = "clinic.finance.transaction"
    _description = "Clinic Finance Internal Transaction"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.finance.company.mixin"]
    _order = "transaction_date desc, id desc"
    _check_company_auto = True

    _amount_positive = models.Constraint(
        "CHECK(amount > 0)",
        "Finance transaction amount must be greater than zero.",
    )
    _company_state_date_idx = models.Index("(company_id, state, transaction_date)")

    name = fields.Char(default="/", copy=False, readonly=True, index=True, tracking=True)
    transaction_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True, index=True)
    finance_account_id = fields.Many2one(
        "clinic.finance.account", required=True, check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]", tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    category_id = fields.Many2one(
        "clinic.finance.category", check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id), ('active', '=', True)]", tracking=True,
    )
    direction = fields.Selection(
        [("in", "Receipt"), ("out", "Disbursement")],
        required=True, default="out", tracking=True, index=True,
    )
    operation_type = fields.Selection(
        [
            ("receipt", "Internal Receipt"),
            ("disbursement", "Internal Disbursement"),
            ("reimbursement", "Reimbursement"),
            ("fund_advance", "Fund Advance"),
            ("cash_variance", "Cash Variance"),
            ("adjustment", "Adjustment"),
            ("other", "Other Internal Operation"),
        ],
        required=True, default="disbursement", tracking=True, index=True,
    )
    amount = fields.Monetary(currency_field="currency_id", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", check_company=True, tracking=True)
    counterpart_account_id = fields.Many2one(
        "account.account", check_company=True, ondelete="restrict", tracking=True,
        help="Counterpart used when Finance creates the standard Odoo journal entry.",
    )
    analytic_account_id = fields.Many2one("account.analytic.account", ondelete="restrict")
    # Upstream records already accounted by AR/AP/Wallet can be traced without double-posting.
    posting_policy = fields.Selection(
        [
            ("create_move", "Create Odoo Journal Entry"),
            ("operational_only", "Operational Traceability Only"),
        ],
        default="create_move", required=True, tracking=True,
        help="Use operational-only for upstream AR/AP/Wallet records already accounted.",
    )
    origin_ref = fields.Reference(selection="_selection_origin_ref", string="Operational Origin", tracking=True)
    fund_request_id = fields.Many2one(
        "clinic.finance.fund.request", readonly=True, copy=False, check_company=True
    )
    cash_session_id = fields.Many2one(
        "clinic.finance.cash.session", readonly=True, copy=False, check_company=True
    )

    state = fields.Selection(
        [
            ("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
            ("posted", "Posted"), ("cancelled", "Cancelled"),
        ],
        default="draft", required=True, tracking=True, index=True,
    )
    approval_required = fields.Boolean(compute="_compute_approval_required", store=True)
    submitted_by_id = fields.Many2one("res.users", readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    approved_by_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    posted_by_id = fields.Many2one("res.users", readonly=True)
    posted_at = fields.Datetime(readonly=True)

    move_id = fields.Many2one(
        "account.move", readonly=True, copy=False, check_company=True,
        ondelete="restrict", string="Journal Entry",
    )
    move_state = fields.Selection(related="move_id.state", readonly=True)
    reference = fields.Char(tracking=True)
    note = fields.Text()

    @api.model
    def _selection_origin_ref(self):
        return [
            ("clinic.billing.invoice", _("Clinic Billing")),
            ("clinic.billing.payment", _("Clinic Billing Payment")),
            ("clinic.ar.invoice", _("AR Invoice")),
            ("clinic.ar.payment", _("AR Receipt")),
            ("clinic.ap", _("AP Document")),
            ("clinic.wallet.transaction", _("Wallet Transaction")),
            ("account.payment", _("Odoo Payment")),
            ("account.move", _("Odoo Journal Entry")),
            ("clinic.finance.fund.request", _("Finance Fund Request")),
            ("clinic.finance.cash.session", _("Finance Cash Session")),
        ]

    @api.depends(
        "amount", "category_id.approval_required", "category_id.approval_limit",
        "company_id.finance_approval_threshold", "fund_request_id.state",
    )
    def _compute_approval_required(self):
        for record in self:
            if record.fund_request_id and record.fund_request_id.state in ("approved", "disbursed"):
                record.approval_required = False
                continue
            threshold = record.company_id.finance_approval_threshold or 0.0
            category_limit = record.category_id.approval_limit or 0.0
            record.approval_required = bool(
                record.category_id.approval_required
                or (threshold and record.amount >= threshold)
                or (category_limit and record.amount >= category_limit)
            )

    @api.onchange("finance_account_id")
    def _onchange_finance_account(self):
        for record in self:
            if record.finance_account_id:
                record.company_id = record.finance_account_id.company_id
                record.branch_id = record.finance_account_id.branch_id

    @api.onchange("category_id")
    def _onchange_category(self):
        for record in self:
            if record.category_id:
                record.counterpart_account_id = record.category_id.counterpart_account_id
                if record.category_id.direction in ("in", "out"):
                    record.direction = record.category_id.direction

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            account = self.env["clinic.finance.account"].browse(vals.get("finance_account_id"))
            if account.exists():
                vals.setdefault("company_id", account.company_id.id)
                vals.setdefault("branch_id", account.branch_id.id)
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"].with_company(company)
                    .next_by_code("clinic.finance.transaction") or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        protected = {
            "finance_account_id", "company_id", "branch_id", "direction", "operation_type",
            "amount", "category_id", "counterpart_account_id", "posting_policy", "origin_ref",
        }
        system_fields = {
            "state", "move_id", "submitted_by_id", "submitted_at",
            "approved_by_id", "approved_at", "posted_by_id", "posted_at",
        }
        if system_fields.intersection(vals) and not self.env.context.get("finance_transition"):
            raise AccessError(_("Workflow and accounting audit fields can only be changed by Finance actions."))
        if protected.intersection(vals):
            for record in self:
                if record.state == "posted":
                    raise UserError(_("Posted Finance transactions are immutable."))
                if record.state != "draft":
                    raise UserError(_("Financial content can only be edited while Draft."))
        return super().write(vals)

    @api.constrains("finance_account_id", "company_id", "branch_id", "counterpart_account_id")
    def _check_finance_scope(self):
        for record in self:
            account = record.finance_account_id
            if account.company_id != record.company_id:
                raise ValidationError(_("Finance account and transaction company must match."))
            if account.branch_id and record.branch_id and account.branch_id != record.branch_id:
                raise ValidationError(_("Transaction branch must match the Finance account branch."))
            counterpart = record.counterpart_account_id
            if counterpart and record.company_id not in counterpart.company_ids:
                raise ValidationError(_("Counterpart account must be available to this company."))
            if counterpart and counterpart == account.liquidity_account_id:
                raise ValidationError(_("Counterpart account cannot equal the liquidity account."))

    @api.constrains("category_id", "direction")
    def _check_category_direction(self):
        for record in self:
            category = record.category_id
            if category and category.direction in ("in", "out") and category.direction != record.direction:
                raise ValidationError(_("Transaction direction is not allowed by the selected category."))

    def action_submit(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_cashier")
        now = fields.Datetime.now()
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft transactions can be submitted."))
            if record.posting_policy == "create_move" and not record.counterpart_account_id:
                raise UserError(_("Set a counterpart account before submitting."))
            vals = {
                "state": "submitted", "submitted_by_id": self.env.user.id, "submitted_at": now,
            }
            if not record.approval_required:
                vals.update({
                    "state": "approved", "approved_by_id": self.env.user.id, "approved_at": now,
                })
            record.with_context(finance_transition=True).write(vals)
        return True

    def action_approve(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_approver")
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only Submitted transactions can be approved."))
            record.with_context(finance_transition=True).write({
                "state": "approved", "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
        return True

    # Posting creates a balanced standard account.move only after approval gates have passed.
    def action_post(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_cashier")
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only Approved transactions can be posted."))
            if record.finance_account_id.state != "active":
                raise UserError(_("The selected Finance account is not active."))
            move = False
            if record.posting_policy == "create_move":
                move = self.env["account.move"].create(record._prepare_move_vals())
                move.action_post()
            record.with_context(finance_transition=True).write({
                "state": "posted",
                "posted_by_id": self.env.user.id,
                "posted_at": fields.Datetime.now(),
                "move_id": move.id if move else False,
            })
            if record.fund_request_id:
                record.fund_request_id.with_context(finance_transition=True).write({"state": "disbursed"})
        return True

    def action_cancel(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state == "posted":
                raise UserError(_("Posted transactions must be reversed through Accounting."))
            record.with_context(finance_transition=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state == "posted":
                raise UserError(_("Posted transactions cannot be reset."))
            record.with_context(finance_transition=True).write({
                "state": "draft", "submitted_by_id": False, "submitted_at": False,
                "approved_by_id": False, "approved_at": False,
            })
        return True

    # Debit/credit orientation is explicit to keep manual review and future accounting integration readable.
    def _prepare_move_vals(self):
        self.ensure_one()
        liquidity = self.finance_account_id.liquidity_account_id
        counterpart = self.counterpart_account_id
        if not liquidity or not counterpart:
            raise UserError(_("Liquidity and counterpart accounts are required."))
        debit_account = liquidity if self.direction == "in" else counterpart
        credit_account = counterpart if self.direction == "in" else liquidity
        common = {"name": self.reference or self.name}
        if self.branch_id and "branch_id" in self.env["account.move.line"]._fields:
            common["branch_id"] = self.branch_id.id
        vals = {
            "move_type": "entry",
            "date": self.transaction_date,
            "journal_id": self.finance_account_id.journal_id.id,
            "ref": self.reference or self.name,
            "clinic_finance_transaction_id": self.id,
            "line_ids": [
                Command.create({
                    **common, "account_id": debit_account.id,
                    "debit": self.amount, "credit": 0.0, "partner_id": self.partner_id.id or False,
                }),
                Command.create({
                    **common, "account_id": credit_account.id,
                    "debit": 0.0, "credit": self.amount, "partner_id": self.partner_id.id or False,
                }),
            ],
        }
        if self.branch_id and "branch_id" in self.env["account.move"]._fields:
            vals["branch_id"] = self.branch_id.id
        return vals

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("This transaction has no accounting journal entry."))
        return {
            "type": "ir.actions.act_window", "name": _("Journal Entry"),
            "res_model": "account.move", "view_mode": "form", "res_id": self.move_id.id,
        }

    def action_open_origin(self):
        self.ensure_one()
        if not self.origin_ref:
            raise UserError(_("No operational origin is linked."))
        return {
            "type": "ir.actions.act_window", "name": _("Operational Origin"),
            "res_model": self.origin_ref._name, "view_mode": "form", "res_id": self.origin_ref.id,
        }

    def action_open_finance_account(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Finance Account"),
            "res_model": "clinic.finance.account", "view_mode": "form",
            "res_id": self.finance_account_id.id,
        }
