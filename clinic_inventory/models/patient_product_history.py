# -*- coding: utf-8 -*-
# File: models/patient_product_history.py
# Module: clinic_inventory
#
# Purpose
#   Track patient-level product usage history for aesthetic clinics:
#   - Records every clinical product usage (consumption/delivery/return/etc.) tied to a patient
#   - Safe, optional links to stock moves/pickings and clinic treatment usage documents
#   - Public APIs to log history from pickings, moves, or treatment usage lines (no circular deps)
#   - Convenience actions for navigating related stock documents and filtering by patient
#
# Notes
#   - All user-facing texts are in English (fields, help, errors).
#   - Avoid hard dependencies on other clinic_* apps; use Reference fields and optional checks.
#   - Works with Odoo 18 CE stock/product/mail; hr is used for 'doctor' (optional).

from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicPatientProductHistory(models.Model):
    _name = "clinic.patient.product.history"
    _description = "Patient Product History"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_use desc, id desc"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # Core links & identities
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        domain=[("is_company", "=", False)],
        index=True,
        tracking=True,
        help="Patient associated with this product usage."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        index=True,
        tracking=True,
        help="Product that was used/dispensed to the patient."
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
        related="product_id.product_tmpl_id",
        store=True,
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('product_id', '=', product_id)]",
        help="Lot/serial consumed or dispensed (if applicable)."
    )

    date_use = fields.Datetime(
        string="Usage Date",
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
        help="Date and time when the product usage happened."
    )
    qty = fields.Float(
        string="Quantity",
        required=True,
        default=1.0,
        digits="Product Unit of Measure",
        help="Quantity used/dispensed (always positive number)."
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
        default=lambda self: self.env.ref("uom.product_uom_unit"),
        help="Unit of measure of the quantity above."
    )

    direction = fields.Selection(
        selection=[
            ("consume", "Consume (Treatment)"),
            ("deliver", "Deliver to Patient"),
            ("receive", "Receive (Return/Correction)"),
            ("return", "Return to Supplier (Patient-associated)"),
            ("adjust", "Inventory Adjustment"),
            ("scrap", "Scrap"),
            ("quarantine", "Quarantine"),
        ],
        string="Direction",
        required=True,
        default="consume",
        help=(
            "Semantic direction of the event:\n"
            "- Consume: clinical use during treatment.\n"
            "- Deliver: product delivered to the patient.\n"
            "- Receive: positive correction or patient return.\n"
            "- Return: sent back to supplier (patient-associated case).\n"
            "- Adjust: inventory adjustment.\n"
            "- Scrap: product written off.\n"
            "- Quarantine: moved into quarantine area."
        ),
        tracking=True,
    )

    purpose = fields.Selection(
        selection=[
            ("treatment", "Treatment"),
            ("retail", "Retail"),
            ("complimentary", "Complimentary"),
            ("warranty", "Warranty/Aftercare"),
            ("internal", "Internal/Training"),
        ],
        string="Purpose",
        default="treatment",
        help="Business purpose for this usage."
    )

    # Sign for analytics (derived from direction)
    signed_qty = fields.Float(
        string="Signed Quantity",
        compute="_compute_signed_qty",
        store=False,
        help="Quantity with sign based on direction (negative for consume/deliver/scrap/quarantine)."
    )

    # Clinical context (optional)
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor",
        help="Healthcare professional responsible for the treatment (optional)."
    )
    treatment_ref = fields.Reference(
        selection=lambda self: self._clinic_treatment_reference_models(),
        string="Treatment Reference",
        help="Link to treatment/appointment/encounter record (optional)."
    )

    # Stock document links (optional and safe)
    picking_id = fields.Many2one(
        "stock.picking",
        string="Picking",
        help="Related stock picking (if any)."
    )
    move_id = fields.Many2one(
        "stock.move",
        string="Stock Move",
        help="Related stock move (if any)."
    )
    usage_id = fields.Many2one(
        "clinic.treatment.product.usage",
        string="Usage Document",
        help="Clinical consumption document that generated this entry (if available)."
    )

    # Warehouse & locations (best-effort)
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        help="Warehouse context for this usage (best-effort)."
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        help="Where the product was taken from (best-effort)."
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        help="Where the product was moved to (best-effort)."
    )

    # Audit & free notes
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
        help="User who logged this event."
    )
    note = fields.Char(
        string="Note",
        help="Optional free text note."
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=False
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_display_name(self):
        for rec in self:
            patient = rec.patient_id.display_name or "Patient"
            prod = rec.product_id.display_name or "Product"
            dt = fields.Datetime.to_string(rec.date_use) if rec.date_use else ""
            dir_label = dict(self._fields["direction"].selection).get(rec.direction or "consume")
            rec.display_name = f"{patient} - {prod} - {dir_label} @ {dt}"

    def _compute_signed_qty(self):
        negative = {"consume", "deliver", "scrap", "quarantine"}
        for rec in self:
            sign = -1.0 if (rec.direction in negative) else 1.0
            rec.signed_qty = sign * (rec.qty or 0.0)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("qty")
    def _check_positive_qty(self):
        for rec in self:
            if rec.qty is None or rec.qty <= 0.0:
                raise ValidationError(_("Quantity must be greater than zero."))

    @api.constrains("patient_id")
    def _check_patient_is_person(self):
        for rec in self:
            if rec.patient_id and rec.patient_id.is_company:
                raise ValidationError(_("Patient must be an individual contact (not a company)."))

    # -------------------------------------------------------------------------
    # UI ACTIONS
    # -------------------------------------------------------------------------
    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No picking is linked to this history line."))
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["domain"] = [("id", "=", self.picking_id.id)]
        return action

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No stock move is linked to this history line."))
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [("id", "=", self.move_id.id)]
        return action

    # -------------------------------------------------------------------------
    # REFERENCE MODEL DISCOVERY (avoid hard deps)
    # -------------------------------------------------------------------------
    def _clinic_treatment_reference_models(self):
        """Discover candidate treatment models dynamically to avoid hard dependencies."""
        candidates = [
            ("clinic.treatment", "Treatment"),
            # ("booking.booking.appointment", "Appointment"),
            ("clinic.room.session", "Room Session"),
            ("clinic.treatment.product.usage", "Usage Document"),
        ]
        res = []
        IrModel = self.env["ir.model"].sudo()
        for model, label in candidates:
            if IrModel.search([("model", "=", model)], limit=1):
                res.append((model, label))
        return res

    # -------------------------------------------------------------------------
    # PUBLIC APIS (for other modules to log history)
    # -------------------------------------------------------------------------
    @api.model
    def log_from_move(self, move, patient, direction=None, purpose="treatment", doctor=None,
                      treatment_ref=None, lot=None, qty=None, note=None):
        """Create a history record from a stock.move.

        Args:
            move (record stock.move): the move related to this usage (required)
            patient (record res.partner): patient record (required)
            direction (str|None): semantic direction; if None, inferred from locations
            purpose (str): business purpose (default 'treatment')
            doctor (record hr.employee|None): optional doctor
            treatment_ref (tuple(model, id)|recordset|None): optional target record for Reference
            lot (record stock.lot|None): preferred lot if present
            qty (float|None): override quantity; defaults to move.product_uom_qty or done qty
            note (str|None): optional note

        Returns:
            clinic.patient.product.history record
        """
        if not move or not patient:
            raise UserError(_("Move and Patient are required to log patient product history."))

        # Infer direction if missing
        direction = direction or self._infer_direction_from_locations(move.location_id, move.location_dest_id)

        # Determine quantity (prefer done quantities if present on move lines)
        final_qty = 0.0
        if qty is not None:
            final_qty = qty
        else:
            # Sum done qty on move lines; fall back to product_uom_qty
            if move.move_line_ids:
                for ml in move.move_line_ids:
                    final_qty += ml.quantity or 0.0
            if final_qty <= 0.0:
                final_qty = move.product_uom_qty or 0.0

        if final_qty <= 0.0:
            raise UserError(_("Cannot log patient history with zero quantity."))

        # Select lot if possible
        final_lot = lot
        if not final_lot and move.move_line_ids:
            lots = move.move_line_ids.mapped("lot_id")
            final_lot = lots[:1] if lots else False

        # Warehouse best-effort
        wh = getattr(getattr(move, "picking_type_id", False), "warehouse_id", False)

        # Build treatment_ref value if a recordset was passed
        ref_value = False
        if treatment_ref:
            if isinstance(treatment_ref, models.BaseModel):
                ref_value = (treatment_ref._name, treatment_ref.id)
            elif isinstance(treatment_ref, (list, tuple)) and len(treatment_ref) == 2:
                ref_value = (treatment_ref[0], treatment_ref[1])

        vals = {
            "company_id": move.company_id.id,
            "patient_id": patient.id,
            "doctor_id": doctor.id if doctor else False,
            "product_id": move.product_id.id,
            "lot_id": final_lot.id if final_lot else False,
            "date_use": fields.Datetime.now(),
            "qty": final_qty,
            "uom_id": move.product_uom.id,
            "direction": direction,
            "purpose": purpose or "treatment",
            "picking_id": move.picking_id.id if move.picking_id else False,
            "move_id": move.id,
            "warehouse_id": wh.id if wh else False,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "note": note or "",
        }
        if ref_value:
            vals["treatment_ref"] = ref_value

        rec = self.create(vals)
        rec._clinic_hook_post_create_history()
        return rec

    @api.model
    def log_from_picking(self, picking, patient, direction=None, purpose="treatment",
                         doctor=None, treatment_ref=None, note=None):
        """Create history entries from a picking (one entry per product).

        Sums done quantities per product/lot where possible.
        """
        if not picking or not patient:
            raise UserError(_("Picking and Patient are required to log patient product history."))

        # Infer direction if missing
        direction = direction or self._infer_direction_from_locations(picking.location_id, picking.location_dest_id)

        # Group by (product, lot)
        groups = {}
        for ml in picking.move_line_ids:
            key = (ml.product_id.id, ml.lot_id.id if ml.lot_id else False, ml.product_uom_id.id)
            groups.setdefault(key, 0.0)
            groups[key] += ml.quantity or 0.0

        records = self.browse()
        if not groups:
            # If no move lines (rare), iterate moves
            for mv in picking.move_lines:
                rec = self.log_from_move(
                    move=mv, patient=patient, direction=direction, purpose=purpose,
                    doctor=doctor, treatment_ref=treatment_ref, lot=None, qty=None, note=note
                )
                records |= rec
        else:
            for (product_id, lot_id, uom_id), amount in groups.items():
                if amount <= 0.0:
                    continue
                vals = {
                    "company_id": picking.company_id.id,
                    "patient_id": patient.id,
                    "doctor_id": doctor.id if doctor else False,
                    "product_id": product_id,
                    "lot_id": lot_id or False,
                    "date_use": fields.Datetime.now(),
                    "qty": amount,
                    "uom_id": uom_id,
                    "direction": direction,
                    "purpose": purpose or "treatment",
                    "picking_id": picking.id,
                    "warehouse_id": getattr(picking.picking_type_id, "warehouse_id", False).id if getattr(picking.picking_type_id, "warehouse_id", False) else False,
                    "location_id": picking.location_id.id if picking.location_id else False,
                    "location_dest_id": picking.location_dest_id.id if picking.location_dest_id else False,
                    "note": note or "",
                }
                if treatment_ref:
                    if isinstance(treatment_ref, models.BaseModel):
                        vals["treatment_ref"] = (treatment_ref._name, treatment_ref.id)
                    elif isinstance(treatment_ref, (list, tuple)) and len(treatment_ref) == 2:
                        vals["treatment_ref"] = (treatment_ref[0], treatment_ref[1])
                records |= self.create(vals)

        for rec in records:
            rec._clinic_hook_post_create_history()
        return records

    @api.model
    def log_from_usage_line(self, usage_line):
        """Create a history entry from a clinic.treatment.product.usage.line (same module)."""
        if not usage_line or usage_line._name != "clinic.treatment.product.usage.line":
            raise UserError(_("Invalid usage line for logging."))

        usage = usage_line.usage_id
        vals = {
            "company_id": usage.company_id.id,
            "patient_id": usage.patient_id.id if usage.patient_id else False,
            "doctor_id": usage.doctor_id.id if usage.doctor_id else False,
            "product_id": usage_line.product_id.id,
            "lot_id": usage_line.lot_id.id if usage_line.lot_id else False,
            "date_use": usage.date_usage or fields.Datetime.now(),
            "qty": usage_line.product_uom_qty,
            "uom_id": usage_line.product_uom.id,
            "direction": "consume",
            "purpose": "treatment",
            "usage_id": usage.id,
            "warehouse_id": usage.warehouse_id.id if usage.warehouse_id else False,
            "location_id": usage.src_location_id.id if usage.src_location_id else False,
            "location_dest_id": usage.dest_location_id.id if usage.dest_location_id else False,
            "note": usage.notes or "",
        }
        if usage.treatment_ref:
            vals["treatment_ref"] = (usage.treatment_ref._name, usage.treatment_ref.id)
        rec = self.create(vals)
        rec._clinic_hook_post_create_history()
        return rec

    # -------------------------------------------------------------------------
    # INFERENCE HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def _infer_direction_from_locations(self, loc_src, loc_dest):
        """Best-effort mapping from locations to semantic direction."""
        src_usage = getattr(loc_src, "usage", "")
        dst_usage = getattr(loc_dest, "usage", "")

        # Quarantine
        if getattr(loc_dest, "clinic_is_quarantine", False):
            return "quarantine"

        # Consume if goes to 'inventory' sink
        if dst_usage == "inventory":
            return "consume"

        # Deliver if goes to customer
        if dst_usage == "customer":
            return "deliver"

        # Receive if comes from supplier to internal
        if src_usage == "supplier" and dst_usage == "internal":
            return "receive"

        # Return if goes to supplier
        if dst_usage == "supplier":
            return "return"

        # Scrap if goes to scrap/production scrap (usage 'inventory' may also represent scrap in some configs)
        if dst_usage in ("production",):
            return "scrap"

        # Adjust as fallback
        return "adjust"

    # -------------------------------------------------------------------------
    # HOOKS for bridges (post-create notifications/side-effects)
    # -------------------------------------------------------------------------
    def _clinic_hook_post_create_history(self):
        """Hook called after history line is created.

        Bridges may:
          - record loyalty/membership points,
          - emit billing/accounting side-effects,
          - update patient medical records or feedback loops.
        """
        return

    # -------------------------------------------------------------------------
    # SEARCH HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def clinic_find_by_patient(self, patient, limit=100):
        """Return latest history entries for the given patient."""
        if not patient:
            return self.browse()
        return self.search([("patient_id", "=", patient.id)], limit=limit, order="date_use desc, id desc")

    @api.model
    def clinic_patient_product_summary(self, patient):
        """Return a dict summary {product_id: total_signed_qty} for the patient."""
        if not patient:
            return {}
        data = {}
        rows = self.read_group(
            [("patient_id", "=", patient.id)],
            ["product_id", "qty:sum"],
            ["product_id"]
        )
        # We return raw positive sums; consumers may also inspect 'direction' if needed
        for r in rows:
            pid = r["product_id"][0]
            data[pid] = r.get("qty", 0.0) or 0.0
        return data

