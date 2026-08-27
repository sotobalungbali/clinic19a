# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Core Model: Orders
Model: clinic.emar.order

Key features
------------
- Core eMAR Order entity linked to Patient/Doctor/Prescription/Booking/Encounter.
- Integrated with:
  * Audit mixin (create/write/unlink audit, chatter fallback).
  * Inventory mixin (reservation & release of stock).
  * Billing mixin (prepare/create/append to draft customer invoices).
- Soft-coupled with external apps (Accounting/Inventory) with graceful fallback.
- Works with Odoo 19 CE & ClinicOne ecosystem.

Design principles
-----------------
- One-file-per-core-model: there is no other file in this addon that _inherit
  clinic.emar.order to avoid Odoo 19 multi-inheritance conflicts inside one addon.
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


# =============================================================================
# Core Model
# =============================================================================
class ClinicEmarOrder(models.Model):
    _name = "clinic.emar.order"
    _description = "ClinicOne eMAR Order"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.emar.mixin.audit",      # abstract mixin (safe)
        "clinic.emar.mixin.inventory",  # abstract mixin (safe)
        "clinic.emar.mixin.billing",    # abstract mixin (safe)
    ]
    _rec_name = "name"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Technical & Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Order Number",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Unique identifier for this eMAR Order."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this order without deleting it."
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
        help="Patient for whom this eMAR Order is issued."
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        tracking=True,
        help="Responsible doctor who authorized this eMAR Order."
    )
    prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="Prescription",
        index=True,
        help="Linked eMAR Prescription if this order originated from a prescription."
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="Clinic booking reference associated with this order."
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        index=True,
        help="Clinical encounter associated with this order."
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
        help="Party responsible for payment (insurance, company, or patient)."
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        help="Pricelist used to compute billable unit prices."
    )

    # -------------------------------------------------------------------------
    # Timeline
    # -------------------------------------------------------------------------
    date_prescribed = fields.Datetime(
        string="Prescribed On",
        default=fields.Datetime.now,
        help="Date when the order is prescribed/created."
    )
    date_start = fields.Datetime(
        string="Start Date",
        help="Target start date for this order."
    )
    date_end = fields.Datetime(
        string="End Date",
        help="Target end date for this order."
    )

    # -------------------------------------------------------------------------
    # Lines & Schedules
    # -------------------------------------------------------------------------
    line_ids = fields.One2many(
        "clinic.emar.medication.line",
        "order_id",
        string="Medication Lines",
        help="Planned medications/services to be administered under this order."
    )
    schedule_ids = fields.One2many(
        "clinic.emar.schedule",
        "order_id",
        string="Schedules",
        help="Administration schedules generated from this order."
    )

    schedule_count = fields.Integer(
        string="Schedule Count",
        compute="_compute_counts"
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_counts"
    )

    # -------------------------------------------------------------------------
    # Inventory Integration (reservation)
    # -------------------------------------------------------------------------
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        help="Preferred warehouse for stock operations related to this order."
    )
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Internal Picking Type",
        help="Preferred internal picking type for reservations/consumptions."
    )
    reservation_picking_id = fields.Many2one(
        "stock.picking",
        string="Reservation Picking",
        help="Internal picking used to reserve stock for this order."
    )

    # -------------------------------------------------------------------------
    # Billing Integration
    # -------------------------------------------------------------------------
    invoice_ids = fields.One2many(
        "account.move",
        "emar_order_id",
        string="Invoices",
        help="Customer invoices generated from this order."
    )
    billing_state = fields.Selection(
        [
            ("none", "None"),
            ("draft", "Draft"),
            ("invoiced", "Invoiced"),
            ("paid", "Paid"),
        ],
        string="Billing State",
        compute="_compute_billing_state",
        store=False,
    )
    amount_planned = fields.Monetary(
        string="Planned Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        help="Planned billable amount based on lines and pricelist."
    )
    amount_invoiced = fields.Monetary(
        string="Invoiced Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        help="Total amount already invoiced from this order."
    )
    amount_to_invoice = fields.Monetary(
        string="Amount to Invoice",
        compute="_compute_amounts",
        currency_field="currency_id",
        help="Remaining amount to be invoiced (residual)."
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("approved", "Approved"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True
    )
    notes = fields.Text(
        string="Notes",
        help="Internal note for clinical/operational context."
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    def _compute_counts(self):
        for rec in self:
            rec.schedule_count = len(rec.schedule_ids)
            rec.invoice_count = len(rec.invoice_ids)

    def _sum_invoice_totals(self, invoices):
        total = residual = 0.0
        for inv in invoices:
            total += inv.amount_total
            residual += inv.amount_residual
        return total, residual

    @api.depends("invoice_ids", "invoice_ids.state", "invoice_ids.amount_total", "invoice_ids.amount_residual")
    def _compute_billing_state(self):
        for rec in self:
            if not rec.invoice_ids:
                rec.billing_state = "none"
                continue
            has_draft = any(inv.state == "draft" for inv in rec.invoice_ids)
            has_posted = any(inv.state == "posted" for inv in rec.invoice_ids)
            paid = any(inv.payment_state in ("paid", "in_payment") for inv in rec.invoice_ids if inv.state == "posted")
            if paid:
                rec.billing_state = "paid"
            elif has_draft or has_posted:
                rec.billing_state = "invoiced"
            else:
                rec.billing_state = "none"

    def _compute_amounts(self):
        """
        amount_planned: recomputed from order lines using billing pricelist rules.
        amount_invoiced / amount_to_invoice: aggregated from linked invoices.
        """
        for rec in self:
            # Planned using mixin pricing
            planned = 0.0
            partner = rec.payer_partner_id or rec.partner_id
            pricelist = rec._billing_get_pricelist(rec, partner) if partner else None
            for ln in rec.line_ids:
                prod = getattr(ln, "product_id", False)
                qty = float(getattr(ln, "quantity", 0.0) or 0.0)
                if not prod or qty <= 0:
                    continue
                price_unit = rec._billing_get_price_unit(pricelist, prod, qty, partner) if partner else (getattr(prod, "list_price", 0.0) or 0.0)
                planned += (price_unit or 0.0) * qty
            rec.amount_planned = planned

            total, residual = rec._sum_invoice_totals(rec.invoice_ids)
            rec.amount_invoiced = total
            rec.amount_to_invoice = residual

    # =========================================================================
    # CONSTRAINTS & ONCHANGE
    # =========================================================================
    @api.constrains("company_id", "patient_id", "doctor_id")
    def _check_company_consistency(self):
        for rec in self:
            # If related models expose company_id, keep in same company
            for ref in (rec.patient_id, rec.doctor_id):
                if ref and _has_field(ref, "company_id") and ref.company_id and ref.company_id != rec.company_id:
                    raise ValidationError(_("Company mismatch between order and related record."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End Date cannot be earlier than Start Date."))

    @api.onchange("patient_id")
    def _onchange_patient(self):
        for rec in self:
            # Set patient partner & default payer/pricelist from patient when available
            if rec.patient_id:
                if _has_field(rec.patient_id, "partner_id") and rec.patient_id.partner_id:
                    rec.partner_id = rec.patient_id.partner_id
                if _has_field(rec.patient_id, "pricelist_id") and rec.patient_id.pricelist_id:
                    rec.pricelist_id = rec.patient_id.pricelist_id
                # Default payer to patient partner if not set
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
                    vals["name"] = Seq.next_by_code("clinic.emar.order") or _("New")
                else:
                    vals["name"] = _("New")
        recs = super().create(vals_list)
        # Auto-derive partner/payer/pricelist on create if still empty
        for rec in recs:
            if rec.patient_id and not rec.partner_id and _has_field(rec.patient_id, "partner_id") and rec.patient_id.partner_id:
                rec.partner_id = rec.patient_id.partner_id
            if not rec.payer_partner_id and rec.partner_id:
                rec.payer_partner_id = rec.partner_id
            if not rec.pricelist_id and rec.patient_id and _has_field(rec.patient_id, "pricelist_id") and rec.patient_id.pricelist_id:
                rec.pricelist_id = rec.patient_id.pricelist_id
        return recs

    # =========================================================================
    # ACTIONS: State transitions
    # =========================================================================
    def _ensure_has_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("This order has no medication lines."))

    def action_confirm(self):
        """Confirm a complete order and optionally generate administration schedules."""
        for rec in self:
            if rec.state != "draft":
                continue
            rec._ensure_has_lines()
            if rec.company_id.emar_auto_generate_schedules:
                Sched = _get_model(self.env, "clinic.emar.schedule")
                if Sched and hasattr(Sched, "generate_from_order"):
                    Sched.generate_from_order(rec)
            rec._emar_guarded_write({"state": "confirmed"})
            rec._audit_log(
                "state_change",
                message=_("Order confirmed."),
                changes=[{"field": "state", "old": "draft", "new": "confirmed"}],
            )
        return True

    def action_approve(self):
        """Approve only after patient-safety and prescriber-governance hard gates."""
        for rec in self:
            if rec.state != "confirmed":
                continue
            rec._run_order_safety_gate()
            rec._run_prescriber_gate()
            rec._emar_guarded_write({"state": "approved", "date_approved": fields.Datetime.now()})
            rec._audit_log(
                "state_change",
                message=_("Order approved after safety and prescriber checks."),
                changes=[{"field": "state", "old": "confirmed", "new": "approved"}],
            )
        return True

    def action_activate(self):
        """Activate an approved/suspended order; stock reservation remains explicit."""
        for rec in self:
            if rec.state not in ("approved", "suspended"):
                continue
            old = rec.state
            rec._emar_guarded_write({"state": "active"})
            rec._audit_log(
                "state_change",
                message=_("Order activated."),
                changes=[{"field": "state", "old": old, "new": "active"}],
            )
        return True

    def action_suspend(self):
        for rec in self:
            if rec.state not in ("active",):
                continue
            rec._emar_guarded_write({"state": "suspended"})
            rec._audit_log("state_change", message=_("Order suspended."), changes=[{"field": "state", "old": "active", "new": "suspended"}])
        return True

    def action_done(self):
        """Close the order only when all generated schedules are terminal."""
        for rec in self:
            if rec.state not in ("active", "suspended", "approved"):
                continue
            outstanding = rec.schedule_ids.filtered(
                lambda sch: sch.state not in ("administered", "missed", "cancelled")
            )
            if outstanding:
                raise UserError(
                    _("Cannot complete this order while %s administration schedule(s) are still open.")
                    % len(outstanding)
                )
            old = rec.state
            rec._emar_guarded_write({"state": "done", "date_completed": fields.Datetime.now()})
            rec._audit_log(
                "state_change",
                message=_("Order completed."),
                changes=[{"field": "state", "old": old, "new": "done"}],
            )
        return True

    def action_cancel(self):
        """
        Cancel: attempt to release inventory reservations and keep traceability.
        """
        for rec in self:
            if rec.state == "cancelled":
                continue
            # Release reservation first.  If stock cannot be released, keep
            # the order unchanged so inventory and clinical state cannot diverge.
            rec.inventory_release_reservation(picking=rec.reservation_picking_id)
            old = rec.state
            rec._emar_guarded_write({"state": "cancelled"})
            rec._audit_log("state_change", message=_("Order cancelled."), changes=[{"field": "state", "old": old, "new": "cancelled"}])
        return True

    # =========================================================================
    # ACTIONS: Inventory (explicit)
    # =========================================================================
    def action_reserve_inventory(self):
        """
        Explicit user action to (re)build reservation for this order.
        """
        Picking = _get_model(self.env, "stock.picking")
        for rec in self:
            picking, moves = rec.inventory_build_reservation(
                warehouse=rec.warehouse_id or None,
                picking_type=rec.picking_type_id or None,
                picking_name=_("EMAR Reservation - %s") % (rec.name,),
            )
            if Picking and picking:
                rec.reservation_picking_id = picking.id
        return True

    def action_release_inventory(self):
        for rec in self:
            rec.inventory_release_reservation(picking=rec.reservation_picking_id)
        return True

    def action_view_reservation(self):
        """
        Open reservation picking if available.
        """
        self.ensure_one()
        if not self.reservation_picking_id:
            raise UserError(_("No reservation picking available."))
        return {
            "name": _("Reservation Picking"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.reservation_picking_id.id,
        }

    # =========================================================================
    # ACTIONS: Billing (explicit)
    # =========================================================================
    def _billing_collect_default_lines(self):
        """
        Override mixin default: use order lines; skip non-billable/service if flagged.
        """
        return self.line_ids

    def action_create_invoice(self):
        """
        Create/append a draft invoice for this order using billing mixin.
        """
        for rec in self:
            partner = rec._billing_get_partner(rec)
            if not partner:
                raise UserError(_("No billing partner resolved. Please set Payer or Patient Partner."))
            # Build items from order lines (mixin will price via pricelist/FP)
            items = rec._billing_collect_default_items()
            inv = rec.billing_append_or_create(origin_obj=rec, partner=partner, items=items)
            # No return action; simply notify via chatter (already done in mixin)
        return True

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "name": _("Invoices"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("emar_order_id", "=", self.id)],
            "context": {"default_move_type": "out_invoice"},
        }

    # =========================================================================
    # UI HELPERS
    # =========================================================================
    def action_view_schedules(self):
        self.ensure_one()
        return {
            "name": _("Schedules"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.emar.schedule",
            "view_mode": "list,form,calendar",
            "domain": [("order_id", "=", self.id)],
            "context": {"default_order_id": self.id},
        }
