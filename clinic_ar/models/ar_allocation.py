# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicARAllocation(models.Model):
    _name = "clinic.ar.allocation"
    _description = "Accounts Receivable Credit Allocation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Allocation Number",
        default="/",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
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
        domain="[('active', '=', True)]",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        check_company=True,
        tracking=True,
    )
    payment_id = fields.Many2one(
        "clinic.ar.payment",
        string="Source Receipt",
        required=True,
        check_company=True,
        ondelete="restrict",
        index=True,
    )
    payment_move_id = fields.Many2one(
        "account.move",
        related="payment_id.move_id",
        store=True,
        string="Payment Journal Entry",
    )
    origin_ref = fields.Reference(
        selection=[
            ("clinic.ar.payment", "AR Receipt"),
            ("account.payment", "Accounting Payment"),
            ("clinic.billing.payment", "Billing Payment"),
        ],
        string="Source Document",
    )

    available_credit = fields.Monetary(
        compute="_compute_amounts",
        currency_field="currency_id",
    )
    allocated_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    credit_after_allocation = fields.Monetary(
        compute="_compute_amounts",
        currency_field="currency_id",
    )
    line_ids = fields.One2many(
        "clinic.ar.allocation.line",
        "allocation_id",
        string="Allocation Lines",
        copy=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    note = fields.Text()

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "AR Allocation Number must be unique per company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") in (False, "/", "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic.ar.allocation") or "/"
            if vals.get("payment_id"):
                payment = self.env["clinic.ar.payment"].browse(vals["payment_id"])
                vals.setdefault("partner_id", payment.partner_id.id)
                vals.setdefault("company_id", payment.company_id.id)
                vals.setdefault("currency_id", payment.currency_id.id)
        return super().create(vals_list)

    @api.depends(
        "payment_id.overpay_amount",
        "payment_id.account_payment_id.move_id.line_ids.amount_residual",
        "line_ids.applied_amount",
    )
    def _compute_amounts(self):
        for rec in self:
            credit = rec._compute_open_credit_amount()
            allocated = sum(rec.line_ids.filtered(lambda line: line.status == "applied").mapped("applied_amount"))
            if rec.state in {"draft", "validated"}:
                allocated = sum(rec.line_ids.mapped("apply_amount"))
            rec.available_credit = rec.currency_id.round(credit)
            rec.allocated_amount = rec.currency_id.round(allocated)
            rec.credit_after_allocation = rec.currency_id.round(max(credit - allocated, 0.0))

    def _compute_open_credit_amount(self):
        self.ensure_one()
        if not self.payment_id.account_payment_id:
            return self.payment_id.overpay_amount
        partner = self.partner_id.commercial_partner_id
        receivable_credits = self.payment_id.account_payment_id.move_id.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == "asset_receivable"
                and line.partner_id.commercial_partner_id == partner
                and not line.reconciled
                and line.amount_residual < 0
            )
        )
        return abs(sum(receivable_credits.mapped("amount_residual")))

    def _open_receivable_credit_lines(self):
        self.ensure_one()
        if not self.payment_id.account_payment_id:
            return self.env["account.move.line"]
        partner = self.partner_id.commercial_partner_id
        return self.payment_id.account_payment_id.move_id.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == "asset_receivable"
                and line.partner_id.commercial_partner_id == partner
                and not line.reconciled
                and line.amount_residual < 0
            )
        )

    def action_validate(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft allocations can be validated."))
            if not rec.line_ids:
                raise UserError(_("Add at least one allocation line."))
            if rec.allocated_amount <= 0:
                raise UserError(_("Allocation amount must be greater than zero."))
            if rec.allocated_amount > rec.available_credit + rec.currency_id.rounding:
                raise UserError(_("Allocation total exceeds available customer credit."))
            rec.state = "validated"
        return True

    def action_allocate(self):
        for rec in self:
            if rec.state != "validated":
                raise UserError(_("Validate the allocation before applying it."))
            credit_lines = rec._open_receivable_credit_lines()
            if not credit_lines:
                raise UserError(_("No open receivable credit exists on the source payment."))

            for line in rec.line_ids:
                invoice = line.invoice_id
                if invoice.state != "posted" or not invoice.move_id:
                    line.write({"status": "skipped", "message": _("Target invoice is not posted.")})
                    continue
                debit_lines = invoice.move_id.line_ids.filtered(
                    lambda ml: (
                        ml.account_id.account_type == "asset_receivable"
                        and ml.partner_id.commercial_partner_id == rec.partner_id.commercial_partner_id
                        and not ml.reconciled
                        and ml.amount_residual > 0
                    )
                )
                if not debit_lines:
                    line.write({"status": "skipped", "message": _("Target invoice has no open receivable.")})
                    continue

                before = invoice.amount_residual
                current_credit = rec._compute_open_credit_amount()
                expected = rec.currency_id.round(min(before, current_credit))
                requested = rec.currency_id.round(line.apply_amount)
                if rec.currency_id.compare_amounts(requested, expected):
                    raise UserError(_(
                        "Allocation line %(line)s must apply exactly %(expected)s, the current maximum reconcilable amount. "
                        "Requested amount was %(requested)s. Refresh the line before validating the allocation.",
                        line=line.display_name,
                        expected=expected,
                        requested=requested,
                    ))

                # Odoo's reconcile() consumes the maximum common residual of the selected
                # debit and credit lines. By requiring apply_amount == min(invoice residual,
                # available credit), the requested amount and the accounting result stay exact.
                (debit_lines + credit_lines).reconcile()
                invoice._sync_from_accounting()
                applied = max(before - invoice.amount_residual, 0.0)
                line.write({
                    "applied_amount": rec.currency_id.round(applied),
                    "result_residual": invoice.amount_residual,
                    "status": "applied" if applied > 0 else "skipped",
                    "message": _("Applied through Odoo receivable reconciliation.") if applied > 0 else _("No amount applied."),
                })
                credit_lines = rec._open_receivable_credit_lines()
                if not credit_lines:
                    break

            if not rec.line_ids.filtered(lambda line: line.status == "applied"):
                raise UserError(_("No allocation line could be applied. The transaction has been rolled back."))
            rec.state = "done"
            rec.payment_id.invoice_id._sync_from_accounting()
            rec.payment_id.invoice_id._emit_event("credit.allocated")
            rec.message_post(body=_("Customer open credit allocated."))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(
                    _("Applied allocations are accounting reconciliations and cannot be cancelled here. Unreconcile in Accounting first.")
                )
            rec.state = "cancelled"
        return True

    def action_open_payment(self):
        self.ensure_one()
        return self.payment_id._get_records_action(name=_("Source AR Receipt"))


class ClinicARAllocationLine(models.Model):
    _name = "clinic.ar.allocation.line"
    _description = "Accounts Receivable Allocation Line"
    _order = "sequence, id"
    _check_company_auto = True

    allocation_id = fields.Many2one(
        "clinic.ar.allocation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    invoice_id = fields.Many2one(
        "clinic.ar.invoice",
        string="Target AR Invoice",
        required=True,
        check_company=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="allocation_id.partner_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="allocation_id.company_id",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="allocation_id.currency_id",
        store=True,
    )
    invoice_residual_snapshot = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
    )
    apply_amount = fields.Monetary(
        currency_field="currency_id",
        required=True,
    )
    applied_amount = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
    )
    result_residual = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
    )
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("applied", "Applied"),
            ("skipped", "Skipped"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
    )
    message = fields.Char(readonly=True)

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        for line in self:
            if line.invoice_id:
                line.invoice_residual_snapshot = line.invoice_id.amount_residual
                line.apply_amount = min(
                    line.invoice_id.amount_residual,
                    line.allocation_id.available_credit,
                )

    @api.constrains("apply_amount")
    def _check_apply_amount(self):
        for line in self:
            if line.apply_amount <= 0:
                raise ValidationError(_("Apply Amount must be greater than zero."))

    @api.constrains("invoice_id", "allocation_id")
    def _check_scope(self):
        for line in self:
            if not line.invoice_id or not line.allocation_id:
                continue
            if line.invoice_id.partner_id.commercial_partner_id != line.allocation_id.partner_id.commercial_partner_id:
                raise ValidationError(_("Allocation target must belong to the same customer."))
            if line.invoice_id.company_id != line.allocation_id.company_id:
                raise ValidationError(_("Allocation target must belong to the same company."))
            if line.invoice_id.currency_id != line.allocation_id.currency_id:
                raise ValidationError(_("Allocation target must use the same currency."))

    def write(self, vals):
        if any(line.allocation_id.state != "draft" for line in self):
            protected = {"invoice_id", "apply_amount", "allocation_id"}
            if protected.intersection(vals):
                raise UserError(_("Allocation lines are immutable after the allocation leaves Draft."))
        return super().write(vals)

    def unlink(self):
        if any(line.allocation_id.state != "draft" for line in self):
            raise UserError(_("Allocation lines can only be removed while the allocation is Draft."))
        return super().unlink()

    def action_open_invoice(self):
        self.ensure_one()
        return self.invoice_id._get_records_action(name=_("Target AR Invoice"))

