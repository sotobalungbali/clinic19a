# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Core Model: Administration
Model: clinic.emar.administration

Purpose
-------
Represents a concrete administration event derived from an eMAR Schedule/Order.
Responsible for:
- Capturing the actual administration details (who, when, how much, route, notes).
- Consuming inventory for administered items (via inventory mixin).
- Preparing/creating billing entries for administered items (via billing mixin).
- Keeping traceability back to Order / Prescription / Schedule / Medication Line.

Design Principles
-----------------
- One-file-per-core-model: NO other file in this addon _inherit this model.
- Uses abstract mixins only: audit, inventory, billing (safe; no intra-addon inherit loops).
- Soft-coupled with Inventory/Accounting; graceful fallbacks at action time.
- Compatible with Odoo 19 CE & ClinicOne ecosystem (~38 addons).

"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


# =============================================================================
# Utilities
# =============================================================================
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


def _ensure_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return fields.Datetime.from_string(value)
        except Exception:
            pass
    return fields.Datetime.now()


# =============================================================================
# Core Model
# =============================================================================
class ClinicEmarAdministration(models.Model):
    _name = "clinic.emar.administration"
    _description = "ClinicOne eMAR Administration"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.emar.mixin.audit",       # abstract mixin (safe)
        "clinic.emar.mixin.inventory",   # abstract mixin (safe)
        "clinic.emar.mixin.billing",     # abstract mixin (safe)
    ]
    _order = "administered_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Administration",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Unique identifier for this administration."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this administration."
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
    # Linkage (Header Context)
    # -------------------------------------------------------------------------
    order_id = fields.Many2one(
        "clinic.emar.order",
        string="Order",
        index=True,
        help="Related eMAR Order."
    )
    schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="Schedule",
        index=True,
        help="Schedule from which this administration is created."
    )
    line_id = fields.Many2one(
        "clinic.emar.medication.line",
        string="Medication Line",
        index=True,
        help="Medication line associated with this administration."
    )
    prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="Prescription",
        compute="_compute_context_refs",
        store=True,
        help="Prescription context resolved from schedule/order/line."
    )

    # Mirrors for reporting & security alignment
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        compute="_compute_context_refs",
        store=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        compute="_compute_context_refs",
        store=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Product & Dose
    # -------------------------------------------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        index=True,
        tracking=True,
        help="Medication / consumable / service administered."
    )
    dose_qty = fields.Float(
        string="Planned Dose Qty",
        default=1.0,
        digits="Product Unit",
        help="Planned dose quantity (from schedule or line)."
    )
    administered_qty = fields.Float(
        string="Actual Clinical Dose",
        default=1.0,
        digits="Product Unit",
        help="Actual clinical dose administered, expressed in Dose UoM. This is not automatically the stock quantity consumed."
    )
    dose_uom_id = fields.Many2one(
        "uom.uom",
        string="Dose UoM",
        help="Clinical unit for planned/actual dose (for example mg or mL)."
    )
    inventory_qty = fields.Float(
        string="Inventory Qty Used",
        default=1.0,
        digits="Product Unit",
        help="Physical stock quantity consumed by this administration, independent from the clinical dose."
    )
    inventory_uom_id = fields.Many2one(
        "uom.uom",
        string="Inventory UoM",
        ondelete="restrict",
        help="Inventory unit used for stock consumption and billing, normally copied from the medication line."
    )
    waste_qty = fields.Float(
        string="Inventory Waste Qty",
        default=0.0,
        digits="Product Unit",
        help="Physical stock quantity wasted/spilled, expressed in Inventory UoM. Informational unless a downstream waste workflow consumes it."
    )

    # Lot/Serial (optional)
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        help="Lot/serial used in this administration (if tracked)."
    )
    lot_expired = fields.Boolean(
        string="Lot Expired",
        compute="_compute_lot_expiration",
        help="True if selected lot is expired (based on life_date/expiration_date)."
    )

    # Clinical details
    route = fields.Char(
        string="Route",
        help="Administration route (e.g., 'IM', 'IV', 'Topical', 'Oral')."
    )
    notes = fields.Text(
        string="Notes",
        help="Clinical or operational notes for this administration."
    )

    # -------------------------------------------------------------------------
    # Timing & Operators
    # -------------------------------------------------------------------------
    administered_datetime = fields.Datetime(
        string="Administered On",
        default=fields.Datetime.now,
        index=True,
        help="Date/time when the administration happened."
    )
    administered_by_user_id = fields.Many2one(
        "res.users",
        string="Administered By (User)",
        default=lambda self: self.env.user,
        help="System user who performed/recorded the administration."
    )
    administered_by_employee_id = fields.Many2one(
        "hr.employee",
        string="Administered By (Employee)",
        help="Employee who performed the administration."
    )
    double_check_user_id = fields.Many2one(
        "res.users",
        string="Verified By (User)",
        help="Second user who double-checked this administration (optional)."
    )

    # Optional location/session (soft-coupled)
    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        help="Room session where the administration occurred."
    )
    location_note = fields.Char(
        string="Location Note",
        help="Free-text site/room description if not using Room Session."
    )

    # -------------------------------------------------------------------------
    # Inventory / Billing Links
    # -------------------------------------------------------------------------
    picking_id = fields.Many2one(
        "stock.picking",
        string="Consumption Picking",
        help="Internal picking used to consume inventory for this administration."
    )
    invoice_ids = fields.Many2many(
        "account.move",
        string="Invoices",
        compute="_compute_invoices",
        help="Invoices that include lines associated with this administration."
    )

    # -------------------------------------------------------------------------
    # State
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends(
        "schedule_id", "order_id", "line_id",
        "order_id.clinic_patient_id", "order_id.clinic_doctor_id", "order_id.company_id",
        "line_id.patient_id", "line_id.doctor_id", "line_id.order_id", "line_id.prescription_id",
    )
    def _compute_context_refs(self):
        for rec in self:
            # Canonical clinical identity.  Order.patient_id/doctor_id are
            # compatibility fields (res.partner/hr.employee), so never copy their
            # raw IDs into clinic.patient/clinic.doctor mirrors.
            patient = rec.order_id.clinic_patient_id if rec.order_id else False
            if not patient and rec.line_id:
                patient = rec.line_id.patient_id or (
                    rec.line_id.prescription_id.patient_id if rec.line_id.prescription_id else False
                )
            rec.patient_id = patient

            doctor = rec.order_id.clinic_doctor_id if rec.order_id else False
            if not doctor and rec.line_id:
                doctor = rec.line_id.doctor_id or (
                    rec.line_id.prescription_id.doctor_id if rec.line_id.prescription_id else False
                )
            rec.doctor_id = doctor

            # Prescription
            rx = None
            if rec.line_id and rec.line_id.prescription_id:
                rx = rec.line_id.prescription_id
            elif rec.order_id and rec.order_id.prescription_id:
                rx = rec.order_id.prescription_id
            rec.prescription_id = rx

    @api.depends("lot_id")
    def _compute_lot_expiration(self):
        for rec in self:
            try:
                rec.lot_expired = rec._inventory_is_lot_expired(rec.lot_id) if rec.lot_id else False
            except Exception:
                rec.lot_expired = False

    def _resolve_partner_for_billing(self):
        partner = None
        header = self.order_id or self.prescription_id
        if header:
            partner = self._billing_get_partner(header)
        return partner

    def _search_invoices_by_origin_or_link(self):
        """
        Try to find invoices related to this administration:
        - Prefer account.move.emar_administration_id if such field exists.
        - Else, use invoice_origin equals to this admin name or its order name.
        """
        Move = _get_model(self.env, "account.move")
        if not Move:
            return Move.browse()
        dom = [("move_type", "=", "out_invoice"), ("state", "!=", "cancel")]
        if _has_field(Move, "emar_administration_id"):
            dom.append(("emar_administration_id", "=", self.id))
            return Move.search(dom)
        # Fallback by invoice_origin
        names = [n for n in (self.name, getattr(self.order_id, "name", False)) if n]
        if not names:
            return Move.browse()
        return Move.search(dom + [("invoice_origin", "in", names)])

    def _compute_invoices(self):
        for rec in self:
            try:
                rec.invoice_ids = [(6, 0, rec._search_invoices_by_origin_or_link().ids)]
            except Exception:
                rec.invoice_ids = [(5, 0, 0)]

    # =========================================================================
    # ONCHANGE & CONSTRAINTS
    # =========================================================================
    @api.onchange("schedule_id")
    def _onchange_schedule(self):
        for rec in self:
            if not rec.schedule_id:
                continue
            # Mirror product, dose, uom, route, notes
            if rec.schedule_id.product_id and not rec.product_id:
                rec.product_id = rec.schedule_id.product_id
            if rec.schedule_id.dose_uom_id and not rec.dose_uom_id:
                rec.dose_uom_id = rec.schedule_id.dose_uom_id
            rec.dose_qty = rec.schedule_id.dose_qty or rec.dose_qty
            rec.administered_qty = rec.dose_qty
            if rec.schedule_id.line_id:
                rec.inventory_qty = rec.schedule_id.line_id.quantity or rec.inventory_qty
                rec.inventory_uom_id = rec.schedule_id.line_id.product_uom_id or rec.inventory_uom_id
            elif rec.product_id:
                rec.inventory_qty = rec.inventory_qty or 1.0
                rec.inventory_uom_id = rec.inventory_uom_id or rec.product_id.uom_id
            if not rec.route and rec.schedule_id.route:
                rec.route = rec.schedule_id.route
            if not rec.notes and rec.schedule_id.notes:
                rec.notes = rec.schedule_id.notes

    @api.onchange("product_id")
    def _onchange_product(self):
        for rec in self:
            if rec.product_id and not rec.dose_uom_id:
                rec.dose_uom_id = rec.product_id.uom_id
            if rec.product_id and not rec.inventory_uom_id:
                rec.inventory_uom_id = rec.product_id.uom_id

    _nonnegative_administration_quantities = models.Constraint(
        "CHECK(administered_qty >= 0 AND inventory_qty >= 0 AND waste_qty >= 0)",
        "Clinical dose, inventory quantity, and waste quantity cannot be negative.",
    )

    @api.constrains("administered_qty", "inventory_qty", "waste_qty")
    def _check_administration_quantities(self):
        for rec in self:
            if rec.administered_qty < 0 or rec.inventory_qty < 0 or rec.waste_qty < 0:
                raise ValidationError(_("Clinical dose, inventory quantity, and waste quantity cannot be negative."))

    @api.constrains("company_id", "order_id", "line_id")
    def _check_company_alignment(self):
        for rec in self:
            cmp = None
            if rec.order_id and rec.order_id.company_id:
                cmp = rec.order_id.company_id
            elif rec.line_id:
                if rec.line_id.order_id and rec.line_id.order_id.company_id:
                    cmp = rec.line_id.order_id.company_id
                elif rec.line_id.prescription_id and rec.line_id.prescription_id.company_id:
                    cmp = rec.line_id.prescription_id.company_id
            if cmp and rec.company_id and cmp != rec.company_id:
                raise ValidationError(_("Company mismatch between the administration and its header context."))

    # =========================================================================
    # ORM BASICS
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        Seq = _get_model(self.env, "ir.sequence")
        Order = self.env["clinic.emar.order"]
        Line = self.env["clinic.emar.medication.line"]
        for vals in vals_list:
            if not vals.get("company_id"):
                order = Order.browse(vals.get("order_id")) if vals.get("order_id") else False
                line = Line.browse(vals.get("line_id")) if vals.get("line_id") else False
                source_company = (
                    order.company_id if order and order.company_id
                    else line.company_id if line and line.company_id
                    else self.env.company
                )
                vals["company_id"] = source_company.id
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (Seq and Seq.next_by_code("clinic.emar.administration")) or _("New")
            # Clinical dose defaults are separate from physical stock usage.
            if "administered_qty" not in vals:
                vals["administered_qty"] = vals.get("dose_qty", 1.0) or 1.0

            line = self.env["clinic.emar.medication.line"].browse(vals.get("line_id")) if vals.get("line_id") else False
            product = self.env["product.product"].browse(vals.get("product_id")) if vals.get("product_id") else False
            if "inventory_qty" not in vals:
                vals["inventory_qty"] = (line.quantity if line else 1.0) or 1.0
            if "inventory_uom_id" not in vals:
                inventory_uom = line.product_uom_id if line and line.product_uom_id else (product.uom_id if product else False)
                vals["inventory_uom_id"] = inventory_uom.id if inventory_uom else False
        recs = super().create(vals_list)
        return recs

    # =========================================================================
    # INVENTORY INTEGRATION
    # =========================================================================
    def _inventory_collect_consumption_items(self):
        """
        Override mixin default to consume the administered product & quantity.
        Returns: list of dict {product, qty, uom (optional), line (record), lot (optional)}
        """
        self.ensure_one()
        items = []
        prod = self.product_id
        qty = float(self.inventory_qty or 0.0)
        if prod and qty > 0:
            it = {"product": prod, "qty": qty, "line": self.line_id or False}
            # Provide lot if present
            if self.lot_id:
                it["lot"] = self.lot_id
            # Provide UoM if needed by downstream logic
            if self.inventory_uom_id:
                it["uom"] = self.inventory_uom_id
            items.append(it)
        return items

    def action_consume_inventory(self):
        """
        Create & validate an INTERNAL picking to consume inventory for this administration.
        Uses inventory mixin. Stores picking on 'picking_id'.
        """
        for rec in self:
            if rec.lot_id and rec.lot_expired:
                raise UserError(_("Selected Lot/Serial is expired. Please choose a valid lot."))
            picking, moves = rec.inventory_consume(items=None, admin=rec)  # items collected by override above
            if picking:
                rec.picking_id = picking.id
        return True

    # =========================================================================
    # BILLING INTEGRATION
    # =========================================================================
    def _billing_collect_default_items(self):
        """
        Override mixin default to bill exactly the administered quantity.
        Returns: list of dicts [{product, qty, uom, line, price_unit(opt), name(opt)}]
        """
        self.ensure_one()
        items = []
        prod = self.product_id
        qty = float(self.inventory_qty or 0.0)
        if prod and qty > 0:
            uom = self.inventory_uom_id or (prod.uom_id if _has_field(prod, "uom_id") else False)
            name = "%s (Inventory usage %s %s)" % (prod.display_name, qty, uom.name if uom else "")
            items.append({
                "product": prod,
                "qty": qty,
                "uom": uom,
                "line": self.line_id or False,
                "name": name,
            })
        return items

    def action_create_invoice(self):
        """
        Prepare/append a draft invoice for this administration via billing mixin.
        """
        for rec in self:
            partner = rec._resolve_partner_for_billing()
            if not partner:
                raise UserError(_("No billing partner resolved from Order/Prescription/Patient."))
            items = rec._billing_collect_default_items()
            inv = rec.billing_append_or_create(origin_obj=rec, partner=partner, items=items, admin=rec)
            # admin name used as invoice_origin in mixin header builder
        return True

    # =========================================================================
    # WORKFLOW ACTIONS
    # =========================================================================
    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue
            # Safety: product & quantity
            if not rec.product_id:
                raise UserError(_("Please select a product to administer."))
            if not rec.dose_uom_id:
                # default to product UoM if empty
                if rec.product_id.uom_id:
                    rec.dose_uom_id = rec.product_id.uom_id
            if rec.lot_id and rec.lot_expired:
                raise UserError(_("Selected Lot/Serial is expired. Please choose a valid lot."))
            rec._emar_guarded_write({"state": "confirmed"})
            rec._audit_log("state_change", message=_("Administration confirmed."),
                           changes=[{"field": "state", "old": "draft", "new": "confirmed"}])
        return True

    def action_start(self):
        for rec in self:
            if rec.state not in ("confirmed",):
                continue
            rec._emar_guarded_write({"state": "in_progress"})
            rec._audit_log("state_change", message=_("Administration started."),
                           changes=[{"field": "state", "old": "confirmed", "new": "in_progress"}])
        return True

    def action_done(self, consume_inventory=True, create_invoice=False):
        """
        Finalize the administration.
        Options:
          - consume_inventory: create & validate internal picking (default True).
          - create_invoice: prepare/append draft invoice line(s) (default False).
        """
        for rec in self:
            if rec.state not in ("confirmed", "in_progress"):
                continue

            # 1) Independent clinical verification, enforced server-side.
            rec._run_administration_safety_gate()

            # 2) Inventory consumption (optional, governed by clinic_inventory).
            if consume_inventory:
                rec.action_consume_inventory()

            # 3) Billing (optional)
            if create_invoice:
                rec.action_create_invoice()

            # 4) Mark done
            rec._emar_guarded_write({"state": "done"})
            if rec.schedule_id and rec.schedule_id.state not in ("administered", "cancelled"):
                # Administration and schedule finalization are one clinical
                # transaction.  Never swallow a schedule-state failure after
                # marking medication as administered.
                rec.schedule_id._emar_guarded_write({"state": "administered"})
            rec._audit_log("state_change", message=_("Administration completed."),
                           changes=[{"field": "state", "old": "in_progress/confirmed", "new": "done"}])
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "cancelled":
                continue
            rec._emar_guarded_write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancellation reason: %s") % reason)
            rec._audit_log("state_change", message=_("Administration cancelled."),
                           changes=[{"field": "state", "old": "any", "new": "cancelled"}])
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ("cancelled",):
                raise UserError(_("You can only reset a cancelled administration to Draft."))
            rec._emar_guarded_write({"state": "draft"})
            rec._audit_log("state_change", message=_("Administration reset to Draft."),
                           changes=[{"field": "state", "old": "cancelled", "new": "draft"}])
        return True

    # =========================================================================
    # UI HELPERS
    # =========================================================================
    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No consumption picking available."))
        return {
            "name": _("Consumption Picking"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "name": _("Invoices"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {"default_move_type": "out_invoice"},
        }
