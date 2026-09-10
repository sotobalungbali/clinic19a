# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicARInvoice(models.Model):
    _name = "clinic.ar.invoice"
    _description = "Accounts Receivable Invoice"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "invoice_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="AR Number",
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
        tracking=True,
    )

    patient_id = fields.Many2one(
        "clinic.patient",
        string="Clinic Patient",
        index=True,
        check_company=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Bill To",
        required=True,
        index=True,
        check_company=True,
        tracking=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        check_company=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        index=True,
    )
    treatment_session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Treatment Session",
        index=True,
        check_company=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        check_company=True,
    )
    membership_id = fields.Many2one(
        "membership.contract",
        string="Membership Contract",
        index=True,
        check_company=True,
    )
    billing_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Billing Document",
        index=True,
        check_company=True,
        ondelete="restrict",
    )
    origin_ref = fields.Reference(
        selection=[
            ("clinic.billing.invoice", "Clinic Billing"),
            ("booking.booking", "Booking"),
            ("clinic.treatment.session", "Treatment Session"),
            ("membership.contract", "Membership Contract"),
            ("sale.order", "Sales Order"),
            ("account.move", "Accounting Invoice"),
        ],
        string="Source Document",
    )

    invoice_date = fields.Date(
        string="Invoice Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Payment Terms",
        check_company=True,
    )
    due_date = fields.Date(
        string="Due Date",
        tracking=True,
        index=True,
    )
    aging_date = fields.Date(
        string="Aging As Of",
        required=True,
        default=fields.Date.context_today,
        readonly=True,
        copy=False,
    )

    line_ids = fields.One2many(
        "clinic.ar.invoice.line",
        "invoice_id",
        string="AR Lines",
        copy=True,
    )
    payment_ids = fields.One2many(
        "clinic.ar.payment",
        "invoice_id",
        string="Receipts",
    )
    followup_ids = fields.One2many(
        "clinic.ar.followup",
        "invoice_id",
        string="Follow-ups",
    )
    allocation_line_ids = fields.One2many(
        "clinic.ar.allocation.line",
        "invoice_id",
        string="Allocations",
    )

    move_id = fields.Many2one(
        "account.move",
        string="Accounting Invoice",
        readonly=True,
        copy=False,
        check_company=True,
        index=True,
    )

    amount_untaxed = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_discount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_tax = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_total = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
        tracking=True,
    )
    amount_paid = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_residual = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
        tracking=True,
        index=True,
    )
    manual_discount_amount = fields.Monetary(
        string="Header Discount",
        currency_field="currency_id",
        tracking=True,
    )
    membership_discount_rate = fields.Float(
        string="Membership Discount (%)",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    payment_state = fields.Selection(
        [
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("partial", "Partially Paid"),
            ("paid", "Paid"),
            ("overdue", "Overdue"),
            ("reversed", "Reversed"),
            ("blocked", "Blocked"),
        ],
        compute="_compute_aging",
        store=True,
        index=True,
        tracking=True,
    )
    is_overdue = fields.Boolean(
        compute="_compute_aging",
        store=True,
        index=True,
    )
    days_overdue = fields.Integer(
        compute="_compute_aging",
        store=True,
    )
    aging_bucket = fields.Selection(
        [
            ("current", "Current"),
            ("1_30", "1-30 Days"),
            ("31_60", "31-60 Days"),
            ("61_90", "61-90 Days"),
            ("90_plus", "90+ Days"),
        ],
        compute="_compute_aging",
        store=True,
        index=True,
    )

    payment_count = fields.Integer(compute="_compute_counts")
    followup_count = fields.Integer(compute="_compute_counts")
    allocation_count = fields.Integer(compute="_compute_counts")
    note = fields.Text(string="Internal Notes")

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "AR Number must be unique per company.",
    )
    _billing_company_unique = models.Constraint(
        "UNIQUE (billing_id, company_id)",
        "A Clinic Billing document can only have one AR invoice per company.",
    )

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.price_tax",
        "line_ids.price_total",
        "line_ids.discount_amount",
        "manual_discount_amount",
        "membership_discount_rate",
        "move_id.amount_untaxed",
        "move_id.amount_tax",
        "move_id.amount_total",
        "move_id.amount_residual",
        "move_id.state",
        "currency_id",
    )
    def _compute_amounts(self):
        for rec in self:
            currency = rec.currency_id or rec.company_id.currency_id
            if rec.move_id:
                rec.amount_untaxed = rec.move_id.amount_untaxed
                rec.amount_tax = rec.move_id.amount_tax
                rec.amount_total = rec.move_id.amount_total
                rec.amount_residual = rec.move_id.amount_residual
                rec.amount_paid = currency.round(
                    max(rec.move_id.amount_total - rec.move_id.amount_residual, 0.0)
                )
                rec.amount_discount = sum(rec.line_ids.mapped("discount_amount"))
                continue

            raw_untaxed = sum(rec.line_ids.mapped("price_subtotal"))
            raw_tax = sum(rec.line_ids.mapped("price_tax"))
            line_discount = sum(rec.line_ids.mapped("discount_amount"))
            membership_discount = raw_untaxed * max(rec.membership_discount_rate, 0.0) / 100.0
            header_discount = max(rec.manual_discount_amount, 0.0) + membership_discount
            header_discount = min(header_discount, raw_untaxed)
            adjusted_untaxed = raw_untaxed - header_discount
            tax_ratio = adjusted_untaxed / raw_untaxed if raw_untaxed else 1.0
            adjusted_tax = raw_tax * tax_ratio
            total = adjusted_untaxed + adjusted_tax
            rec.amount_untaxed = currency.round(adjusted_untaxed)
            rec.amount_discount = currency.round(line_discount + header_discount)
            rec.amount_tax = currency.round(adjusted_tax)
            rec.amount_total = currency.round(total)
            posted_payments = rec.payment_ids.filtered(lambda p: p.state == "posted")
            paid = sum(posted_payments.mapped("applied_amount"))
            rec.amount_paid = currency.round(paid)
            rec.amount_residual = currency.round(max(total - paid, 0.0))

    @api.depends(
        "state",
        "amount_residual",
        "amount_total",
        "due_date",
        "aging_date",
        "move_id.payment_state",
        "move_id.state",
    )
    def _compute_aging(self):
        for rec in self:
            as_of = rec.aging_date or fields.Date.context_today(rec)
            residual = rec.amount_residual or 0.0
            if rec.state == "cancelled":
                rec.payment_state = "reversed"
                rec.is_overdue = False
                rec.days_overdue = 0
                rec.aging_bucket = "current"
                continue

            move_state = rec.move_id.payment_state if rec.move_id else False
            if residual <= 0:
                payment_state = "paid"
            elif move_state in {"in_payment", "partial", "blocked", "reversed"}:
                payment_state = move_state
            elif rec.amount_total and residual < rec.amount_total:
                payment_state = "partial"
            else:
                payment_state = "not_paid"

            days = 0
            if rec.due_date and rec.due_date < as_of and residual > 0 and rec.state == "posted":
                days = (as_of - rec.due_date).days
                payment_state = "overdue"

            rec.payment_state = payment_state
            rec.is_overdue = bool(days)
            rec.days_overdue = days
            if days <= 0:
                rec.aging_bucket = "current"
            elif days <= 30:
                rec.aging_bucket = "1_30"
            elif days <= 60:
                rec.aging_bucket = "31_60"
            elif days <= 90:
                rec.aging_bucket = "61_90"
            else:
                rec.aging_bucket = "90_plus"

    def _compute_counts(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)
            rec.followup_count = len(rec.followup_ids)
            rec.allocation_count = len(rec.allocation_line_ids)

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        for rec in self:
            if rec.patient_id and rec.patient_id.partner_id:
                rec.partner_id = rec.patient_id.partner_id.commercial_partner_id
            if rec.patient_id and rec.patient_id.membership_active_contract_id:
                rec.membership_id = rec.patient_id.membership_active_contract_id

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for rec in self:
            if rec.partner_id:
                rec.payment_term_id = rec.partner_id.property_payment_term_id

    @api.onchange("payment_term_id", "invoice_date")
    def _onchange_payment_term_id(self):
        for rec in self:
            rec.due_date = rec._compute_due_date_fallback()

    def _compute_due_date_fallback(self):
        self.ensure_one()
        if self.payment_term_id and self.invoice_date:
            try:
                # Odoo accounting will be authoritative once account.move exists.
                term_dates = self.payment_term_id._compute_terms(
                    date_ref=self.invoice_date,
                    currency=self.currency_id,
                    company=self.company_id,
                    tax_amount=0.0,
                    tax_amount_currency=0.0,
                    sign=1,
                    untaxed_amount=1.0,
                    untaxed_amount_currency=1.0,
                )
                dates = [line.get("date") for line in term_dates.get("line_ids", []) if line.get("date")]
                if dates:
                    return max(dates)
            except Exception:
                pass
        return (self.invoice_date or fields.Date.context_today(self)) + timedelta(days=30)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "/") in (False, "/", "New"):
                # A bounded dataset may supply a stable business identity through
                # context.  Normal production callers keep the owner sequence.
                # The value is deliberately not a generic ``default_name`` so a
                # UI context cannot accidentally replace production numbering.
                vals["name"] = (
                    self.env.context.get("clinic_demo_ar_name")
                    or sequence.next_by_code("clinic.ar.invoice")
                    or "/"
                )
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            vals.setdefault("company_id", company.id)
            vals.setdefault("currency_id", company.currency_id.id)
        records = super().create(vals_list)
        for rec in records:
            if not rec.due_date:
                rec.due_date = rec._compute_due_date_fallback()
            rec._emit_event("invoice.created")
        return records

    def write(self, vals):
        protected = {
            "company_id", "currency_id", "partner_id", "patient_id", "billing_id",
            "invoice_date", "payment_term_id", "line_ids", "manual_discount_amount",
            "membership_discount_rate",
        }
        if protected.intersection(vals) and not self.env.context.get("clinic_ar_accounting_sync"):
            for rec in self:
                if rec.state != "draft":
                    raise UserError(_("Posted or cancelled AR invoices are financially immutable."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(_("Only draft AR invoices can be deleted."))
        return super().unlink()

    @api.constrains("due_date", "invoice_date")
    def _check_dates(self):
        for rec in self:
            if rec.due_date and rec.invoice_date and rec.due_date < rec.invoice_date:
                raise ValidationError(_("Due Date cannot be earlier than Invoice Date."))

    @api.constrains("membership_discount_rate")
    def _check_membership_discount(self):
        for rec in self:
            if rec.membership_discount_rate < 0 or rec.membership_discount_rate > 100:
                raise ValidationError(_("Membership Discount must be between 0 and 100 percent."))

    @api.constrains("billing_id", "partner_id", "company_id")
    def _check_billing_scope(self):
        for rec in self:
            if not rec.billing_id:
                continue
            if rec.billing_id.company_id != rec.company_id:
                raise ValidationError(_("Billing Document and AR Invoice must belong to the same company."))
            if rec.billing_id.patient_id.commercial_partner_id != rec.partner_id.commercial_partner_id:
                raise ValidationError(_("Billing customer and AR customer must match."))

    @api.model
    def create_from_billing(self, billing):
        billing.ensure_one()
        existing = self.search([
            ("billing_id", "=", billing.id),
            ("company_id", "=", billing.company_id.id),
        ], limit=1)
        if existing:
            return existing

        patient = billing.clinic_patient_id
        membership = patient.membership_active_contract_id if patient else False
        values = {
            "billing_id": billing.id,
            "origin_ref": f"clinic.billing.invoice,{billing.id}",
            "company_id": billing.company_id.id,
            "currency_id": billing.currency_id.id,
            "patient_id": patient.id if patient else False,
            "partner_id": billing.patient_id.commercial_partner_id.id,
            "booking_id": billing.booking_id.id if billing.booking_id else False,
            "doctor_id": billing.clinic_doctor_id.id if billing.clinic_doctor_id else False,
            "membership_id": membership.id if membership else False,
            "invoice_date": billing.invoice_date or fields.Date.context_today(self),
            "payment_term_id": billing.payment_term_id.id if billing.payment_term_id else False,
            "due_date": billing.invoice_date_due or False,
            "move_id": billing.move_id.id if billing.move_id else False,
            "line_ids": [
                Command.create({
                    "name": line.name,
                    "product_id": line.product_id.id if line.product_id else False,
                    "product_uom_id": line.product_uom_id.id if line.product_uom_id else False,
                    "quantity": line.quantity,
                    "price_unit": line.unit_price,
                    "discount": line.discount_percent,
                    "taxes_id": [Command.set(line.tax_ids.ids)],
                    "billing_line_id": line.id,
                })
                for line in billing.line_ids
                if not line.display_type
            ],
        }
        ar_invoice = self.create(values)
        if billing.move_id and billing.move_id.state == "posted":
            ar_invoice.state = "posted"
        ar_invoice._sync_from_accounting()
        ar_invoice._emit_event("invoice.imported_from_billing")
        return ar_invoice

    def _prepare_account_move_vals(self):
        self.ensure_one()
        invoice_lines = []
        for line in self.line_ids:
            if not line.product_id and not line.name:
                continue
            vals = {
                "name": line.name,
                "product_id": line.product_id.id if line.product_id else False,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "tax_ids": [Command.set(line.taxes_id.ids)],
            }
            if line.product_uom_id:
                vals["product_uom_id"] = line.product_uom_id.id
            if line.income_account_id:
                vals["account_id"] = line.income_account_id.id
            invoice_lines.append(Command.create(vals))

        if not invoice_lines:
            raise UserError(_("At least one AR line is required before posting."))

        values = {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.commercial_partner_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "invoice_date": self.invoice_date,
            "invoice_origin": self.name,
            "ref": self.name,
            "invoice_line_ids": invoice_lines,
        }
        if self.payment_term_id:
            values["invoice_payment_term_id"] = self.payment_term_id.id
        elif self.due_date:
            values["invoice_date_due"] = self.due_date
        return values

    def action_post(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft AR invoices can be posted."))
            if rec.amount_total <= 0:
                raise UserError(_("AR Invoice total must be greater than zero."))
            rec.partner_id.ensure_ar_can_post(rec.amount_total)

            if rec.billing_id:
                if not rec.billing_id.move_id:
                    raise UserError(
                        _("The linked Clinic Billing document must create its Accounting Invoice before AR can post.")
                    )
                if rec.billing_id.move_id.state != "posted":
                    raise UserError(_("The linked Clinic Billing Accounting Invoice must be posted first."))
                rec.move_id = rec.billing_id.move_id
            else:
                move = self.env["account.move"].with_company(rec.company_id).create(
                    rec._prepare_account_move_vals()
                )
                move.action_post()
                rec.move_id = move

            rec.state = "posted"
            rec._sync_from_accounting()
            rec._emit_event("invoice.posted")
            rec.message_post(body=_("AR Invoice posted and linked to accounting."))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancelled":
                continue
            if rec.billing_id:
                raise UserError(
                    _("Billing-owned AR invoices must be cancelled from Clinic Billing so accounting ownership remains consistent.")
                )
            if rec.move_id and rec.move_id.state == "posted":
                rec.move_id._reverse_moves(
                    default_values_list=[{
                        "date": fields.Date.context_today(rec),
                        "ref": _("AR reversal of %s") % rec.name,
                    }],
                    cancel=True,
                )
            rec.state = "cancelled"
            rec._emit_event("invoice.cancelled")
            rec.message_post(body=_("AR Invoice cancelled."))
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(_("Only cancelled AR invoices can be reset to draft."))
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(_("Accounting cleanup is required before resetting this AR Invoice."))
            rec.write({"state": "draft", "move_id": False})
        return True

    def _sync_from_accounting(self):
        for rec in self:
            if not rec.move_id:
                continue
            values = {
                "invoice_date": rec.move_id.invoice_date or rec.invoice_date,
                "due_date": rec.move_id.invoice_date_due or rec.due_date,
                "currency_id": rec.move_id.currency_id.id,
                "aging_date": fields.Date.context_today(rec),
            }
            # Accounting is authoritative after posting; use a narrow internal context
            # instead of bypassing the model method through an unusual super() call.
            rec.with_context(clinic_ar_accounting_sync=True).write(values)
            rec._compute_amounts()
            rec._compute_aging()
        return True

    def action_sync_from_accounting(self):
        self._sync_from_accounting()
        return True

    def action_create_payment(self):
        self.ensure_one()
        if self.state != "posted":
            raise UserError(_("Post the AR Invoice before creating a receipt."))
        return {
            "type": "ir.actions.act_window",
            "name": _("New AR Receipt"),
            "res_model": "clinic.ar.payment",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_invoice_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_patient_id": self.patient_id.id if self.patient_id else False,
                "default_company_id": self.company_id.id,
                "default_currency_id": self.currency_id.id,
                "default_amount": self.amount_residual,
            },
        }

    def action_schedule_followup(self):
        self.ensure_one()
        level = self.env["clinic.ar.followup.level"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ], order="sequence, id", limit=1)
        if not level:
            raise UserError(_("Configure at least one AR Follow-up Level first."))
        followup = self.env["clinic.ar.followup"].create({
            "invoice_id": self.id,
            "level_id": level.id,
            "scheduled_date": fields.Date.context_today(self),
        })
        followup.action_schedule()
        return followup._get_records_action(name=_("AR Follow-up"))

    def action_open_account_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No Accounting Invoice is linked."))
        return self.move_id._get_records_action(name=_("Accounting Invoice"))

    def action_view_payments(self):
        self.ensure_one()
        return self.payment_ids._get_records_action(name=_("AR Receipts"))

    def action_view_followups(self):
        self.ensure_one()
        return self.followup_ids._get_records_action(name=_("AR Follow-ups"))

    def action_view_allocations(self):
        self.ensure_one()
        allocations = self.allocation_line_ids.mapped("allocation_id")
        return allocations._get_records_action(name=_("AR Allocations"))

    def action_recompute_totals(self):
        self._compute_amounts()
        self._compute_aging()
        return True

    def _emit_event(self, event_type):
        Event = self.env["clinic.ar.integration.event"].sudo()
        for rec in self:
            Event.enqueue(
                event_type=event_type,
                record=rec,
                company=rec.company_id,
                payload={
                    "ar_invoice_id": rec.id,
                    "name": rec.name,
                    "partner_id": rec.partner_id.id,
                    "billing_id": rec.billing_id.id if rec.billing_id else False,
                    "move_id": rec.move_id.id if rec.move_id else False,
                    "amount_total": rec.amount_total,
                    "amount_residual": rec.amount_residual,
                    "state": rec.state,
                },
            )

    @api.model
    def _cron_refresh_aging(self):
        invoices = self.search([
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
        ])
        today = fields.Date.context_today(self)
        invoices.write({"aging_date": today})
        return True



