from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicAP(models.Model):
    _name = "clinic.ap"
    _description = "Clinic Accounts Payable"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "invoice_date desc, id desc"
    _check_company_auto = True

    _reference_vendor_company_unique = models.Constraint(
        "UNIQUE(reference, vendor_id, company_id)",
        "Vendor reference must be unique for the same vendor and company.",
    )

    name = fields.Char(
        string="AP Number",
        required=True,
        default="New",
        copy=False,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    purchase_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        check_company=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    reference = fields.Char(
        string="Vendor Reference",
        tracking=True,
        index=True,
        help="Supplier invoice/reference number. Duplicate references for the same vendor and company are blocked.",
    )
    invoice_date = fields.Date(
        string="Bill Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    invoice_date_due = fields.Date(string="Due Date", tracking=True)
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Payment Terms",
        check_company=True,
        ondelete="restrict",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_approve", "To Approve"),
            ("approved", "Approved"),
            ("posted", "Posted"),
            ("partial", "Partially Paid"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Vendor Bill",
        check_company=True,
        copy=False,
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    move_state = fields.Selection(related="move_id.state", string="Bill State", store=False)
    payment_state = fields.Selection(related="move_id.payment_state", string="Payment State", store=False)

    line_ids = fields.One2many("clinic.ap.line", "ap_id", string="AP Lines", copy=True)
    amount_untaxed = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_tax = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_total = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_residual = fields.Monetary(
        compute="_compute_amount_residual",
        currency_field="currency_id",
        string="Amount Due",
    )
    amount_paid = fields.Monetary(
        compute="_compute_amount_residual",
        currency_field="currency_id",
        string="Amount Paid",
    )

    approval_required = fields.Boolean(compute="_compute_approval_required")
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    submitted_at = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user, tracking=True)
    notes = fields.Text(string="Internal Notes")

    match_state = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("matched", "Matched"),
            ("warning", "Warning"),
            ("blocked", "Blocked"),
        ],
        compute="_compute_match_state",
        search="_search_match_state",
        string="3-Way Match",
    )
    match_issue_count = fields.Integer(compute="_compute_match_state")
    receipt_count = fields.Integer(compute="_compute_counts")
    billing_allocation_count = fields.Integer(compute="_compute_counts")
    payment_count = fields.Integer(compute="_compute_counts")
    integration_event_count = fields.Integer(compute="_compute_counts")

    @api.depends("line_ids.price_subtotal", "line_ids.price_tax", "line_ids.price_total")
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped("price_subtotal"))
            rec.amount_tax = sum(rec.line_ids.mapped("price_tax"))
            rec.amount_total = sum(rec.line_ids.mapped("price_total"))

    @api.depends("amount_total", "move_id.amount_residual", "move_id.state", "move_id.currency_id")
    def _compute_amount_residual(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                residual = rec.move_id.amount_residual
                if rec.move_id.currency_id != rec.currency_id:
                    residual = rec.move_id.currency_id._convert(
                        residual,
                        rec.currency_id,
                        rec.company_id,
                        rec.move_id.invoice_date or rec.invoice_date,
                    )
                rec.amount_residual = rec.currency_id.round(residual)
            else:
                rec.amount_residual = 0.0 if rec.state == "cancelled" else rec.amount_total
            rec.amount_paid = max(rec.amount_total - rec.amount_residual, 0.0)

    @api.depends("amount_total", "company_id.ap_approval_threshold")
    def _compute_approval_required(self):
        for rec in self:
            threshold = rec.company_id.ap_approval_threshold or 0.0
            rec.approval_required = bool(threshold and rec.amount_total >= threshold)

    @api.depends(
        "line_ids.match_state",
        "line_ids.stock_move_id",
        "line_ids.billing_invoice_id",
        "move_id",
    )
    @api.model
    def _search_match_state(self, operator, value):
        """Provide a search contract for the live, non-stored three-way-match state."""
        records = self.search([])
        if operator in ("=", "=="):
            matched = records.filtered(lambda rec: rec.match_state == value)
        elif operator == "!=":
            matched = records.filtered(lambda rec: rec.match_state != value)
        elif operator == "in":
            values = set(value or [])
            matched = records.filtered(lambda rec: rec.match_state in values)
        elif operator == "not in":
            values = set(value or [])
            matched = records.filtered(lambda rec: rec.match_state not in values)
        else:
            raise ValueError(f"Unsupported operator for match state: {operator}")
        return [("id", "in", matched.ids)]

    def _compute_match_state(self):
        for rec in self:
            states = rec.line_ids.mapped("match_state")
            issues = len(rec.line_ids.filtered(lambda l: l.match_state in ("qty_mismatch", "price_mismatch", "receipt_missing")))
            rec.match_issue_count = issues
            if not rec.purchase_id:
                rec.match_state = "not_applicable"
            elif any(state == "receipt_missing" for state in states) and rec.company_id.ap_enforce_receipt_before_post:
                rec.match_state = "blocked"
            elif issues:
                rec.match_state = "warning"
            else:
                rec.match_state = "matched"

    def _compute_counts(self):
        Payment = self.env["account.payment"]
        Event = self.env["clinic.ap.integration.event"]
        for rec in self:
            rec.receipt_count = len(rec.line_ids.mapped("stock_move_id"))
            rec.billing_allocation_count = len(rec.line_ids.filtered(lambda l: l.billing_invoice_id or l.billing_line_id))
            rec.payment_count = (
                Payment.search_count([("reconciled_bill_ids", "in", rec.move_id.id)])
                if rec.move_id
                else 0
            )
            rec.integration_event_count = Event.search_count([("ap_id", "=", rec.id)])

    @api.onchange("vendor_id")
    def _onchange_vendor_id(self):
        for rec in self:
            if rec.vendor_id:
                rec.payment_term_id = rec.vendor_id.property_supplier_payment_term_id
                if rec.vendor_id.ap_preferred_currency_id:
                    rec.currency_id = rec.vendor_id.ap_preferred_currency_id

    @api.onchange("invoice_date", "payment_term_id", "amount_total")
    def _onchange_payment_term(self):
        for rec in self:
            if rec.payment_term_id and rec.invoice_date:
                rec.invoice_date_due = rec.payment_term_id.ap_compute_due_date(
                    rec.amount_total or 1.0,
                    rec.invoice_date,
                    rec.currency_id or rec.company_id.currency_id,
                )

    @api.constrains("line_ids", "state")
    def _check_lines(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled") and not rec.line_ids:
                raise ValidationError(_("At least one AP line is required."))

    @api.constrains("company_id", "purchase_id", "move_id")
    def _check_company_consistency(self):
        for rec in self:
            for linked in (rec.purchase_id, rec.move_id):
                if linked and linked.company_id != rec.company_id:
                    raise ValidationError(_("Linked documents must belong to the same company as the AP."))

    def _check_vendor_governance(self):
        self.ensure_one()
        vendor = self.vendor_id.commercial_partner_id
        if vendor.ap_vendor_on_hold:
            raise UserError(
                _("Vendor %(vendor)s is on AP hold: %(reason)s", vendor=vendor.display_name, reason=vendor.ap_vendor_hold_reason or "-")
            )
        limit = vendor.ap_vendor_credit_limit or 0.0
        if limit and not vendor.ap_allow_over_exposure:
            projected = vendor.ap_payable_outstanding + self.amount_total
            if projected > limit:
                raise UserError(
                    _("Vendor exposure would exceed the AP limit. Projected: %(projected).2f; Limit: %(limit).2f",
                      projected=projected, limit=limit)
                )

    def _check_posting_rights(self):
        if not self.env.user.has_group("clinic_ap.group_clinic_ap_accountant"):
            raise UserError(_("Only an AP Accountant or AP Manager may post AP documents."))

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.line_ids:
                raise UserError(_("Add at least one AP line before submission."))
            rec._check_vendor_governance()
            rec._autolink_stock_moves()
            rec._refresh_line_match_state()
            if rec.match_state == "blocked":
                raise UserError(_("Three-way match is blocked because required receipts are missing."))
            vals = {
                "submitted_by_id": self.env.user.id,
                "submitted_at": fields.Datetime.now(),
            }
            if rec.approval_required:
                vals["state"] = "to_approve"
            else:
                vals.update({
                    "state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                })
            rec.write(vals)
            rec._emit_event("ap.submitted")
        return True

    def action_approve(self):
        if not self.env.user.has_group("clinic_ap.group_clinic_ap_manager"):
            raise UserError(_("Only an AP Manager may approve AP documents."))
        for rec in self:
            if rec.state != "to_approve":
                continue
            rec._check_vendor_governance()
            rec.write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
            rec._emit_event("ap.approved")
        return True

    def _assign_number(self):
        for rec in self:
            if not rec.name or rec.name == "New":
                rec.name = self.env["ir.sequence"].with_company(rec.company_id).next_by_code("clinic.ap") or "New"

    def action_post(self):
        self._check_posting_rights()
        for rec in self:
            if rec.state not in ("approved",):
                raise UserError(_("Only Approved AP documents may be posted."))
            rec._check_vendor_governance()
            rec._autolink_stock_moves()
            rec._refresh_line_match_state()
            if rec.match_state == "blocked":
                raise UserError(_("AP cannot be posted while the receipt match is blocked."))
            rec._assign_number()
            bill = rec._create_or_update_vendor_bill()
            if bill.state == "draft":
                bill.action_post()
            rec._sync_state_from_bill()
            rec._emit_event("ap.posted", {"move_id": bill.id})
        return True

    def action_sync_status(self):
        for rec in self:
            rec._sync_state_from_bill()
        return True

    def _sync_state_from_bill(self):
        self.ensure_one()
        if not self.move_id or self.move_id.state != "posted":
            return
        if self.move_id.payment_state == "paid" or self.currency_id.is_zero(self.amount_residual):
            self.state = "paid"
        elif self.amount_residual < self.amount_total:
            self.state = "partial"
        else:
            self.state = "posted"

    def action_cancel(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(_("Cancel or reverse the posted Vendor Bill before cancelling this AP."))
            rec.state = "cancelled"
            rec._emit_event("ap.cancelled")
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(_("A posted Vendor Bill must be reversed before reset."))
            rec.write({
                "state": "draft",
                "approved_by_id": False,
                "approved_at": False,
                "submitted_by_id": False,
                "submitted_at": False,
            })
        return True

    def _create_or_update_vendor_bill(self):
        self.ensure_one()
        bill = self.move_id
        if bill and bill.state != "draft":
            return bill

        invoice_lines = [(5, 0, 0)]
        invoice_lines += [(0, 0, line._prepare_vendor_bill_line_vals()) for line in self.line_ids]

        vals = {
            "move_type": "in_invoice",
            "company_id": self.company_id.id,
            "partner_id": self.vendor_id.id,
            "invoice_date": self.invoice_date,
            "ref": self.reference,
            "currency_id": self.currency_id.id,
            "invoice_payment_term_id": self.payment_term_id.id or False,
            "invoice_line_ids": invoice_lines,
        }
        if self.invoice_date_due and not self.payment_term_id:
            vals["invoice_date_due"] = self.invoice_date_due

        if bill:
            bill.write(vals)
        else:
            bill = self.env["account.move"].with_company(self.company_id).create(vals)
            self.move_id = bill.id
        return bill

    def action_view_vendor_bill(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No Vendor Bill is linked yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Vendor Bill"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
            "context": {"create": False},
        }

    def action_register_payment(self):
        self.ensure_one()
        if not self.move_id or self.move_id.state != "posted":
            raise UserError(_("Post the Vendor Bill before registering a payment."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Register Payment"),
            "res_model": "account.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": self.move_id.ids,
                "active_id": self.move_id.id,
            },
        }

    def action_view_payments(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Vendor Payments"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("reconciled_bill_ids", "in", self.move_id.id)],
            "context": {"create": False},
        }

    def action_view_purchase(self):
        self.ensure_one()
        if not self.purchase_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.purchase_id.id,
            "context": {"create": False},
        }

    def action_view_receipts(self):
        self.ensure_one()
        move_ids = self.line_ids.mapped("stock_move_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Receipts / Stock Moves"),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", move_ids)],
            "context": {"create": False},
        }

    def action_view_billing(self):
        self.ensure_one()
        billing_ids = self.line_ids.mapped("billing_invoice_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Billing Allocations"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "list,form",
            "domain": [("id", "in", billing_ids)],
            "context": {"create": False},
        }

    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("AP Integration Events"),
            "res_model": "clinic.ap.integration.event",
            "view_mode": "list,form",
            "domain": [("ap_id", "=", self.id)],
            "context": {"default_ap_id": self.id},
        }

    def _emit_event(self, event_type, payload=None):
        for rec in self:
            self.env["clinic.ap.integration.event"].sudo().create_event(
                event_type=event_type,
                ap=rec,
                payload=payload or {},
            )

    @api.model
    def _cron_sync_ap_status(self):
        records = self.search([("state", "in", ("posted", "partial")), ("move_id", "!=", False)])
        for rec in records:
            rec._sync_state_from_bill()
        return True

    def unlink(self):
        if any(rec.state not in ("draft", "cancelled") for rec in self):
            raise UserError(_("Only Draft or Cancelled AP documents may be deleted."))
        if any(rec.move_id for rec in self):
            raise UserError(_("Detach/delete the draft Vendor Bill before deleting the AP document."))
        return super().unlink()
