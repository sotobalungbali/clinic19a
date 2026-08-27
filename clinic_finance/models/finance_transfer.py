from odoo import api, Command, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFinanceTransfer(models.Model):
    """Governed transfer between two Clinic Finance liquidity accounts."""

    _name = "clinic.finance.transfer"
    _description = "Clinic Finance Internal Transfer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transfer_date desc, id desc"
    _check_company_auto = True

    _amount_positive = models.Constraint(
        "CHECK(amount > 0)",
        "Transfer amount must be greater than zero.",
    )

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    transfer_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    source_account_id = fields.Many2one(
        "clinic.finance.account", required=True, check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]", tracking=True,
    )
    destination_account_id = fields.Many2one(
        "clinic.finance.account", required=True, check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]", tracking=True,
    )
    source_branch_id = fields.Many2one(related="source_account_id.branch_id", store=True, readonly=True)
    destination_branch_id = fields.Many2one(related="destination_account_id.branch_id", store=True, readonly=True)
    amount = fields.Monetary(currency_field="currency_id", required=True, tracking=True)
    # Internal liquidity transfers use a General journal so source/destination bank journals are not duplicated.
    general_journal_id = fields.Many2one(
        "account.journal", string="Transfer Journal", check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        default=lambda self: self.env.company.finance_general_journal_id, tracking=True,
    )
    reference = fields.Char(tracking=True)
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
            ("posted", "Posted"), ("cancelled", "Cancelled"),
        ],
        default="draft", required=True, tracking=True, index=True,
    )
    approval_required = fields.Boolean(compute="_compute_approval_required", store=True)
    submitted_by_id = fields.Many2one("res.users", readonly=True)
    approved_by_id = fields.Many2one("res.users", readonly=True)
    posted_by_id = fields.Many2one("res.users", readonly=True)
    move_id = fields.Many2one("account.move", readonly=True, copy=False, check_company=True, ondelete="restrict")

    @api.depends("amount", "company_id.finance_approval_threshold")
    def _compute_approval_required(self):
        for record in self:
            threshold = record.company_id.finance_approval_threshold or 0.0
            record.approval_required = bool(threshold and record.amount >= threshold)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            vals.setdefault("general_journal_id", company.finance_general_journal_id.id)
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"].with_company(company)
                    .next_by_code("clinic.finance.transfer") or "/"
                )
        return super().create(vals_list)

    def _require_group(self, xmlid):
        if not self.env.user.has_group(xmlid):
            raise AccessError(_("You do not have permission for this transfer operation."))

    def write(self, vals):
        critical = {
            "company_id", "transfer_date", "source_account_id",
            "destination_account_id", "amount", "general_journal_id",
        }
        system_fields = {"state", "move_id", "submitted_by_id", "approved_by_id", "posted_by_id"}
        if system_fields.intersection(vals) and not self.env.context.get("finance_transition"):
            raise AccessError(_("Transfer workflow and accounting audit fields can only be changed by Finance actions."))
        if critical.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("Transfer financial content can only be edited in Draft."))
        return super().write(vals)

    @api.constrains("source_account_id", "destination_account_id", "company_id", "general_journal_id")
    def _check_transfer_scope(self):
        for record in self:
            if record.source_account_id == record.destination_account_id:
                raise ValidationError(_("Source and destination Finance accounts must be different."))
            if record.source_account_id.company_id != record.company_id:
                raise ValidationError(_("Source Finance account company mismatch."))
            if record.destination_account_id.company_id != record.company_id:
                raise ValidationError(_("Destination Finance account company mismatch."))
            if record.general_journal_id and (
                record.general_journal_id.company_id != record.company_id
                or record.general_journal_id.type != "general"
            ):
                raise ValidationError(_("Transfer journal must be a General journal of the same company."))

    def action_submit(self):
        self._require_group("clinic_finance.group_clinic_finance_cashier")
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft transfers can be submitted."))
            if not record.general_journal_id:
                raise UserError(_("Configure the Finance General Journal before submitting."))
            vals = {"state": "submitted", "submitted_by_id": self.env.user.id}
            if not record.approval_required:
                vals.update({"state": "approved", "approved_by_id": self.env.user.id})
            record.with_context(finance_transition=True).write(vals)
        return True

    def action_approve(self):
        self._require_group("clinic_finance.group_clinic_finance_approver")
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only Submitted transfers can be approved."))
            record.with_context(finance_transition=True).write({
                "state": "approved", "approved_by_id": self.env.user.id,
            })
        return True

    def action_post(self):
        self._require_group("clinic_finance.group_clinic_finance_cashier")
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only Approved transfers can be posted."))
            if not record.source_account_id.liquidity_account_id or not record.destination_account_id.liquidity_account_id:
                raise UserError(_("Both Finance accounts must have liquidity accounts."))
            move = self.env["account.move"].create(record._prepare_move_vals())
            move.action_post()
            record.with_context(finance_transition=True).write({
                "state": "posted", "posted_by_id": self.env.user.id, "move_id": move.id,
            })
        return True

    def action_cancel(self):
        self._require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state == "posted":
                raise UserError(_("Posted transfers must be reversed through Accounting."))
            record.with_context(finance_transition=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._require_group("clinic_finance.group_clinic_finance_manager")
        for record in self:
            if record.state == "posted":
                raise UserError(_("Posted transfers cannot be reset."))
            record.with_context(finance_transition=True).write({
                "state": "draft", "submitted_by_id": False, "approved_by_id": False,
            })
        return True

    # One balanced entry moves value between two liquidity accounts and preserves branch attribution per line.
    def _prepare_move_vals(self):
        self.ensure_one()
        src = self.source_account_id.liquidity_account_id
        dst = self.destination_account_id.liquidity_account_id
        ref = self.reference or self.name
        debit_vals = {"name": ref, "account_id": dst.id, "debit": self.amount, "credit": 0.0}
        credit_vals = {"name": ref, "account_id": src.id, "debit": 0.0, "credit": self.amount}
        if "branch_id" in self.env["account.move.line"]._fields:
            debit_vals["branch_id"] = self.destination_branch_id.id or False
            credit_vals["branch_id"] = self.source_branch_id.id or False
        vals = {
            "move_type": "entry", "date": self.transfer_date,
            "journal_id": self.general_journal_id.id, "ref": ref,
            "clinic_finance_transfer_id": self.id,
            "line_ids": [Command.create(debit_vals), Command.create(credit_vals)],
        }
        if self.source_branch_id and "branch_id" in self.env["account.move"]._fields:
            vals["branch_id"] = self.source_branch_id.id
        return vals

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("This transfer has no accounting journal entry."))
        return {
            "type": "ir.actions.act_window", "name": _("Transfer Journal Entry"),
            "res_model": "account.move", "view_mode": "form", "res_id": self.move_id.id,
        }

    def action_open_source_account(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Source Finance Account"),
            "res_model": "clinic.finance.account", "view_mode": "form",
            "res_id": self.source_account_id.id,
        }

    def action_open_destination_account(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Destination Finance Account"),
            "res_model": "clinic.finance.account", "view_mode": "form",
            "res_id": self.destination_account_id.id,
        }
