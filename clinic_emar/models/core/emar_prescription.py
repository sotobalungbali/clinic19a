# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Core Model: Prescription
Model: clinic.emar.prescription

Highlights
----------
- Core eMAR Prescription entity linked to Patient/Doctor and can generate eMAR Orders.
- Integrated with:
  * Audit mixin (create/write/unlink audit logging with chatter fallback).
  * Billing mixin (prepare/create/append to draft invoices).
- Soft-coupled with external apps (Accounting) with graceful fallback.
- Compatible with Odoo 19 CE and the ClinicOne ecosystem.

Design Principles
-----------------
- One-file-per-core-model: there is NO other file in this addon that _inherit
  clinic.emar.prescription (avoids multi-inheritance conflicts).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Utilities (local)
# =============================================================================
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


def _filter_vals_for_model(model, vals):
    """Return a copy of vals containing only keys that exist in model's fields."""
    if not model or not hasattr(model, "_fields"):
        return {}
    return {k: v for k, v in vals.items() if k in model._fields}


# =============================================================================
# Core Model
# =============================================================================
class ClinicEmarPrescription(models.Model):
    _name = "clinic.emar.prescription"
    _description = "ClinicOne eMAR Prescription"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.emar.mixin.audit",    # abstract mixin (safe)
        "clinic.emar.mixin.billing",  # abstract mixin (safe)
    ]
    _rec_name = "name"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Technical & Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Prescription Number",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Unique identifier for this eMAR Prescription."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this prescription."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Clinical Context
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        index=True,
        tracking=True,
        help="Patient for whom this prescription is issued."
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        tracking=True,
        help="Prescribing doctor."
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        index=True,
        help="Clinical encounter associated with this prescription."
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="Clinic booking associated with this prescription."
    )

    diagnosis = fields.Char(
        string="Diagnosis",
        help="Short diagnosis or indication that motivated this prescription."
    )
    rx_type = fields.Selection(
        [
            ("medication", "Medication"),
            ("procedure", "Procedure"),
            ("skincare", "Skin Care"),
            ("other", "Other"),
        ],
        string="Prescription Type",
        default="medication",
        help="Type/category of this prescription."
    )
    priority = fields.Selection(
        [
            ("normal", "Normal"),
            ("urgent", "Urgent"),
            ("stat", "STAT"),
        ],
        string="Priority",
        default="normal",
        help="Clinical urgency level."
    )

    # -------------------------------------------------------------------------
    # Commercial / Payer / Pricing
    # -------------------------------------------------------------------------
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient Partner",
        help="Commercial partner representing the patient (usually auto-derived)."
    )
    payer_partner_id = fields.Many2one(
        "res.partner",
        string="Payer",
        help="Responsible party for payment (insurance/company/patient)."
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        help="Pricelist used for billing and planned amount calculation."
    )

    # -------------------------------------------------------------------------
    # Timeline & Validity
    # -------------------------------------------------------------------------
    date_prescribed = fields.Datetime(
        string="Prescribed On",
        default=fields.Datetime.now,
        help="Date the prescription was created."
    )
    date_start = fields.Datetime(
        string="Start Date",
        help="Requested start date for prescription execution."
    )
    date_end = fields.Datetime(
        string="End Date",
        help="Requested end date for prescription execution."
    )
    valid_days = fields.Integer(
        string="Validity (days)",
        default=30,
        help="Number of days this prescription remains valid."
    )
    expires_on = fields.Date(
        string="Expires On",
        compute="_compute_expires_on",
        store=True,
        help="Date after which this prescription is no longer valid."
    )

    # Refills
    repeat_allowed = fields.Boolean(
        string="Refill Allowed",
        default=False,
        help="If enabled, this prescription can be refilled (generate new orders)."
    )
    repeat_total = fields.Integer(
        string="Total Refills",
        default=0,
        help="Total number of refills allowed for this prescription."
    )
    repeat_used = fields.Integer(
        string="Refills Used",
        default=0,
        help="Number of refills already used."
    )
    refill_interval_days = fields.Integer(
        string="Refill Interval (days)",
        default=0,
        help="Minimum days between refills (0 = no restriction)."
    )

    # -------------------------------------------------------------------------
    # Lines & Orders
    # -------------------------------------------------------------------------
    line_ids = fields.One2many(
        "clinic.emar.medication.line",
        "prescription_id",
        string="Prescription Lines",
        help="Medication/procedure lines defined by this prescription."
    )
    order_ids = fields.One2many(
        "clinic.emar.order",
        "prescription_id",
        string="Orders",
        help="Orders generated from this prescription."
    )

    line_count = fields.Integer(
        string="Line Count",
        compute="_compute_counts"
    )
    order_count = fields.Integer(
        string="Order Count",
        compute="_compute_counts"
    )

    # -------------------------------------------------------------------------
    # Billing Integration
    # -------------------------------------------------------------------------
    invoice_ids = fields.One2many(
        "account.move",
        "emar_prescription_id",
        string="Invoices",
        help="Invoices generated from this prescription."
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_counts"
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    notes = fields.Text(
        string="Notes",
        help="Internal notes for clinical/operational context."
    )

    # =========================================================================
    # COMPUTE
    # =========================================================================
    @api.depends("date_prescribed", "valid_days")
    def _compute_expires_on(self):
        for rec in self:
            if rec.date_prescribed and rec.valid_days and rec.valid_days > 0:
                rec.expires_on = (fields.Datetime.from_string(rec.date_prescribed) + fields.Date.timedelta(days=rec.valid_days)).date()
            else:
                rec.expires_on = False

    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.order_count = len(rec.order_ids)
            rec.invoice_count = len(rec.invoice_ids)

    # =========================================================================
    # CONSTRAINTS & ONCHANGE
    # =========================================================================
    @api.constrains("company_id", "patient_id", "doctor_id")
    def _check_company_consistency(self):
        for rec in self:
            # Keep company consistent if related models expose company_id
            for ref in (rec.patient_id, rec.doctor_id):
                if ref and _has_field(ref, "company_id") and ref.company_id and ref.company_id != rec.company_id:
                    raise ValidationError(_("Company mismatch between prescription and related record."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End Date cannot be earlier than Start Date."))

    @api.onchange("patient_id")
    def _onchange_patient(self):
        for rec in self:
            if rec.patient_id:
                if _has_field(rec.patient_id, "partner_id") and rec.patient_id.partner_id:
                    rec.partner_id = rec.patient_id.partner_id
                if _has_field(rec.patient_id, "pricelist_id") and rec.patient_id.pricelist_id:
                    rec.pricelist_id = rec.patient_id.pricelist_id
                if not rec.payer_partner_id and rec.partner_id:
                    rec.payer_partner_id = rec.partner_id

    # =========================================================================
    # ORM BASICS
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        Seq = _get_model(self.env, "ir.sequence")
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("name") or vals.get("name") == "New":
                if Seq:
                    vals["name"] = Seq.next_by_code("clinic.emar.prescription") or _("New")
                else:
                    vals["name"] = _("New")
        recs = super().create(vals_list)

        # Derive partner/payer/pricelist if missing
        for rec in recs:
            if rec.patient_id and not rec.partner_id and _has_field(rec.patient_id, "partner_id") and rec.patient_id.partner_id:
                rec.partner_id = rec.patient_id.partner_id
            if not rec.payer_partner_id and rec.partner_id:
                rec.payer_partner_id = rec.partner_id
            if not rec.pricelist_id and rec.patient_id and _has_field(rec.patient_id, "pricelist_id") and rec.patient_id.pricelist_id:
                rec.pricelist_id = rec.patient_id.pricelist_id
        return recs

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _ensure_has_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("This prescription has no lines."))

    def _prepare_order_vals_from_prescription(self):
        """
        Prepare values to create a clinic.emar.order from this prescription.
        """
        self.ensure_one()
        Order = _get_model(self.env, "clinic.emar.order")
        if not Order:
            raise UserError(_("eMAR Order model is not available."))

        vals = {
            "company_id": self.company_id.id,
            "patient_id": self.patient_id.id,
            "doctor_id": self.doctor_id.id if self.doctor_id else False,
            "prescription_id": self.id,
            "booking_id": self.booking_id.id if self.booking_id else False,
            "encounter_id": self.encounter_id.id if self.encounter_id else False,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "payer_partner_id": self.payer_partner_id.id if self.payer_partner_id else False,
            "pricelist_id": self.pricelist_id.id if self.pricelist_id else False,
            "date_start": self.date_start,
            "date_end": self.date_end,
            # Optional: initial state; let order workflow handle transitions
            "state": "draft",
        }
        return _filter_vals_for_model(Order, vals)

    def _prepare_order_line_vals_from_rx_line(self, rx_line):
        """Copy the complete clinical/commercial medication intent into an Order line."""
        self.ensure_one()
        LineModel = _get_model(self.env, "clinic.emar.medication.line")
        candidate = {
            "product_id": rx_line.product_id.id if rx_line.product_id else False,
            "product_uom_id": rx_line.product_uom_id.id if rx_line.product_uom_id else False,
            "quantity": float(rx_line.quantity or 1.0),
            "dose": float(getattr(rx_line, "dose", 0.0) or 0.0),
            "dose_uom_id": getattr(rx_line, "dose_uom_id", False).id if getattr(rx_line, "dose_uom_id", False) else False,
            "dosage": getattr(rx_line, "dosage", False),
            "frequency": getattr(rx_line, "frequency", False),
            "route": getattr(rx_line, "route", False),
            "duration_count": getattr(rx_line, "duration_count", 1),
            "duration_unit": getattr(rx_line, "duration_unit", "day"),
            "instructions": getattr(rx_line, "instructions", False),
            "notes": getattr(rx_line, "notes", False),
            "is_prn": bool(getattr(rx_line, "is_prn", False)),
            "is_substitutable": bool(getattr(rx_line, "is_substitutable", True)),
            "profile_id": getattr(rx_line, "profile_id", False).id if getattr(rx_line, "profile_id", False) else False,
            "is_billable": bool(getattr(rx_line, "is_billable", True)),
            "price_unit": float(getattr(rx_line, "price_unit", 0.0) or 0.0),
            "discount_percent": float(getattr(rx_line, "discount_percent", 0.0) or 0.0),
            "source_prescription_line_id": rx_line.id,
        }
        vals = _filter_vals_for_model(LineModel, candidate)
        if not vals.get("product_id"):
            return None
        vals["quantity"] = vals.get("quantity") or 1.0
        return vals

    # =========================================================================
    # ACTIONS: Workflow
    # =========================================================================
    def action_validate(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec._ensure_has_lines()
            # ORM hard gates: UI visibility is never treated as a safety control.
            rec._run_prescription_safety_gate()
            rec._run_prescriber_gate()
            rec._emar_guarded_write({
                "state": "validated",
                "date_approved": fields.Datetime.now(),
            })
            rec._audit_log(
                "state_change",
                message=_("Prescription validated after safety and prescriber checks."),
                changes=[{"field": "state", "old": "draft", "new": "validated"}],
            )
        return True

    def action_activate(self):
        for rec in self:
            if rec.state not in ("validated",):
                continue
            # Basic validity check
            if rec.expires_on and fields.Date.context_today(self) > rec.expires_on:
                raise UserError(_("Cannot activate an expired prescription."))
            rec._emar_guarded_write({"state": "active"})
            rec._audit_log(
                "state_change",
                message=_("Prescription activated."),
                changes=[{"field": "state", "old": "validated", "new": "active"}],
            )
        return True

    def action_mark_expired(self):
        for rec in self:
            if rec.state in ("cancelled", "expired"):
                continue
            old = rec.state
            rec._emar_guarded_write({"state": "expired"})
            rec._audit_log(
                "state_change",
                message=_("Prescription expired."),
                changes=[{"field": "state", "old": old, "new": "expired"}],
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancelled":
                continue
            old = rec.state
            rec._emar_guarded_write({"state": "cancelled"})
            rec._audit_log(
                "state_change",
                message=_("Prescription cancelled."),
                changes=[{"field": "state", "old": old, "new": "cancelled"}],
            )
        return True

    # =========================================================================
    # ACTIONS: Generate Order(s)
    # =========================================================================
    def action_generate_order(self):
        """
        Generate a single eMAR Order from this prescription and copy its lines.
        """
        Order = _get_model(self.env, "clinic.emar.order")
        if not Order:
            raise UserError(_("eMAR Order model is not available."))

        created_orders = self.env[self._name].browse()
        for rec in self:
            rec._ensure_has_lines()

            # Prepare order header vals
            order_vals = rec._prepare_order_vals_from_prescription()

            # Prepare line commands
            line_cmds = []
            for rx_ln in rec.line_ids:
                ln_vals = rec._prepare_order_line_vals_from_rx_line(rx_ln)
                if ln_vals:
                    line_cmds.append((0, 0, ln_vals))
            if not line_cmds:
                raise UserError(_("No valid lines to transfer into an order."))

            order_vals["line_ids"] = line_cmds

            # Create order
            order = Order.create(order_vals)
            created_orders |= order

            # Chatter linking
            try:
                rec.message_post(body=_("Order generated from prescription: %s") % (order.display_name,))
                order.message_post(body=_("Order created from prescription: %s") % (rec.display_name,))
            except Exception:
                pass

            # Keep the prescription active if already active/validated; no auto state change here.

        # Open created order(s)
        if len(created_orders) == 1:
            return {
                "name": _("eMAR Order"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.order",
                "view_mode": "form",
                "res_id": created_orders.id,
            }
        elif created_orders:
            return {
                "name": _("eMAR Orders"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.order",
                "view_mode": "list,form",
                "domain": [("id", "in", created_orders.ids)],
            }
        return True

    # =========================================================================
    # ACTIONS: Billing
    # =========================================================================
    def _billing_collect_default_lines(self):
        """
        Override mixin default: use prescription lines.
        """
        return self.line_ids

    def action_create_invoice(self):
        """
        Create/append a draft invoice for this prescription via billing mixin.
        """
        for rec in self:
            partner = rec._billing_get_partner(rec)
            if not partner:
                raise UserError(_("No billing partner resolved. Please set Payer or Patient Partner."))
            items = rec._billing_collect_default_items()
            rec.billing_append_or_create(origin_obj=rec, partner=partner, items=items)
        return True

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "name": _("Invoices"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("emar_prescription_id", "=", self.id)],
            "context": {"default_move_type": "out_invoice"},
        }

    def action_view_orders(self):
        self.ensure_one()
        return {
            "name": _("Orders"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.emar.order",
            "view_mode": "list,form",
            "domain": [("prescription_id", "=", self.id)],
            "context": {"default_prescription_id": self.id},
        }

    # =========================================================================
    # ACTIONS: Refills (optional utility)
    # =========================================================================
    def action_use_refill(self):
        """
        Consume one refill allowance and generate a new eMAR Order (if allowed).
        """
        for rec in self:
            if not rec.repeat_allowed:
                raise UserError(_("Refill is not allowed for this prescription."))
            if rec.repeat_total <= rec.repeat_used:
                raise UserError(_("No refill remaining for this prescription."))
            # Optional: enforce interval if previous order exists
            # (kept simple; projects can extend with actual date checks)
            order_action = rec.action_generate_order()
            rec.repeat_used += 1
            rec._audit_log(
                "update",
                message=_("Refill used. Total used: %s") % rec.repeat_used,
                changes=[{"field": "repeat_used", "old": rec.repeat_used - 1, "new": rec.repeat_used}],
            )
        return True
