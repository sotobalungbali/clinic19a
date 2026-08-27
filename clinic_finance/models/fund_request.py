from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFinanceFundRequest(models.Model):
    """Internal operational funding/reimbursement request with approval traceability."""

    _name = "clinic.finance.fund.request"
    _description = "Clinic Finance Fund Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.finance.company.mixin"]
    _order = "request_date desc, id desc"
    _check_company_auto = True

    _requested_amount_positive = models.Constraint(
        "CHECK(requested_amount > 0)",
        "Requested amount must be greater than zero.",
    )
    _approved_amount_nonnegative = models.Constraint(
        "CHECK(approved_amount >= 0)",
        "Approved amount cannot be negative.",
    )

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    request_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    required_date = fields.Date(tracking=True)
    request_type = fields.Selection(
        [
            ("petty_cash", "Petty Cash"), ("reimbursement", "Reimbursement"),
            ("advance", "Operational Advance"), ("operational", "Operational Funding"),
        ],
        default="operational", required=True, tracking=True, index=True,
    )
    requested_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    employee_id = fields.Many2one("hr.employee", tracking=True)
    category_id = fields.Many2one(
        "clinic.finance.category", required=True, check_company=True,
        domain="[('company_id', '=', company_id), ('direction', 'in', ('both', 'out'))]", tracking=True,
    )
    finance_account_id = fields.Many2one(
        "clinic.finance.account", check_company=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]", tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    requested_amount = fields.Monetary(currency_field="currency_id", required=True, tracking=True)
    approved_amount = fields.Monetary(currency_field="currency_id", default=0.0, tracking=True)
    purpose = fields.Text(required=True, tracking=True)
    approver_note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
            ("rejected", "Rejected"), ("disbursed", "Disbursed"), ("cancelled", "Cancelled"),
        ],
        default="draft", required=True, tracking=True, index=True,
    )
    submitted_at = fields.Datetime(readonly=True)
    approved_by_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    rejected_by_id = fields.Many2one("res.users", readonly=True)
    rejected_at = fields.Datetime(readonly=True)
    transaction_id = fields.Many2one(
        "clinic.finance.transaction", readonly=True, copy=False, check_company=True, ondelete="restrict"
    )
    transaction_state = fields.Selection(related="transaction_id.state", readonly=True)

    @api.model
    def _default_employee(self):
        return self.env["hr.employee"].search([
            ("user_id", "=", self.env.user.id), ("company_id", "=", self.env.company.id),
        ], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            vals.setdefault("employee_id", self._default_employee().id)
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"].with_company(company)
                    .next_by_code("clinic.finance.fund.request") or "/"
                )
        return super().create(vals_list)

    # Requester fields and approver fields have different backend mutability rules; UI readonly is not security.
    def write(self, vals):
        request_fields = {
            "company_id", "branch_id", "request_type", "requested_by_id",
            "employee_id", "category_id", "requested_amount", "purpose",
        }
        approval_fields = {"finance_account_id", "approved_amount", "approver_note"}

        system_fields = {
            "state", "transaction_id", "submitted_at", "approved_by_id", "approved_at",
            "rejected_by_id", "rejected_at",
        }
        if system_fields.intersection(vals) and not self.env.context.get("finance_transition"):
            raise AccessError(_("Fund Request workflow and audit fields can only be changed by workflow actions."))

        if request_fields.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("Request content can only be edited in Draft."))

        if approval_fields.intersection(vals):
            for record in self:
                if record.state == "draft":
                    continue
                if record.state == "submitted" and self.env.user.has_group(
                    "clinic_finance.group_clinic_finance_approver"
                ):
                    continue
                raise AccessError(
                    _("Approval and disbursement fields can only be changed by a Finance Approver while Submitted.")
                )
        return super().write(vals)

    @api.constrains("approved_amount", "requested_amount")
    def _check_approved_amount(self):
        for record in self:
            if record.approved_amount > record.requested_amount:
                raise ValidationError(_("Approved amount cannot exceed requested amount."))

    def action_submit(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft fund requests can be submitted."))
            record.with_context(finance_transition=True).write({
                "state": "submitted", "submitted_at": fields.Datetime.now(),
            })
        return True

    def action_approve(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_approver")
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only Submitted fund requests can be approved."))
            amount = record.approved_amount or record.requested_amount
            if amount <= 0:
                raise UserError(_("Approved amount must be greater than zero."))
            if not record.finance_account_id:
                raise UserError(_("Select the disbursement Finance account before approval."))
            record.with_context(finance_transition=True).write({
                "state": "approved", "approved_amount": amount,
                "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now(),
            })
        return True

    def action_reject(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_approver")
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only Submitted fund requests can be rejected."))
            record.with_context(finance_transition=True).write({
                "state": "rejected", "rejected_by_id": self.env.user.id,
                "rejected_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        for record in self:
            if record.state == "disbursed":
                raise UserError(_("A disbursed Fund Request cannot be cancelled."))
            if (
                record.requested_by_id != self.env.user
                and not self.env.user.has_group("clinic_finance.group_clinic_finance_manager")
            ):
                raise AccessError(_("Only the requester or Finance Manager can cancel this request."))
            record.with_context(finance_transition=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state == "disbursed":
                raise UserError(_("A disbursed Fund Request cannot be reset."))
            record.with_context(finance_transition=True).write({
                "state": "draft", "approved_by_id": False, "approved_at": False,
                "rejected_by_id": False, "rejected_at": False,
            })
        return True

    # Approved requests create the Finance transaction; they never bypass the transaction posting workflow.
    def action_create_disbursement(self):
        self._finance_require_group("clinic_finance.group_clinic_finance_cashier")
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only Approved fund requests can create a disbursement."))
            if record.transaction_id:
                raise UserError(_("This Fund Request already has a Finance transaction."))
            category = record.category_id
            if not category.counterpart_account_id:
                raise UserError(_("The category needs a default counterpart account."))
            tx = self.env["clinic.finance.transaction"].create({
                "finance_account_id": record.finance_account_id.id,
                "company_id": record.company_id.id,
                "branch_id": record.branch_id.id,
                "category_id": category.id,
                "direction": "out",
                "operation_type": "reimbursement" if record.request_type == "reimbursement" else "fund_advance",
                "amount": record.approved_amount,
                "counterpart_account_id": category.counterpart_account_id.id,
                "posting_policy": "create_move",
                "fund_request_id": record.id,
                "origin_ref": f"clinic.finance.fund.request,{record.id}",
                "reference": record.name,
                "note": record.purpose,
            })
            tx.action_submit()
            record.with_context(finance_transition=True).write({"transaction_id": tx.id})
        return self.action_open_transaction()

    def action_open_transaction(self):
        self.ensure_one()
        if not self.transaction_id:
            raise UserError(_("No Finance transaction has been created yet."))
        return {
            "type": "ir.actions.act_window", "name": _("Finance Disbursement"),
            "res_model": "clinic.finance.transaction", "view_mode": "form",
            "res_id": self.transaction_id.id,
        }
