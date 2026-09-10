# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - External Bridge: Stock
Bridges eMAR artifacts to Odoo Inventory (stock.* models).

This file is the ONLY place inside clinic_emar that _inherit(s) stock models,
to avoid multi-inherit collisions in Odoo 19 CE.

Key points
----------
- Adds eMAR linkage fields on stock.picking, stock.move, stock.move.line.
- Company/patient/doctor context mirroring with safety checks.
- Optional lot-expiration validation on move lines.
- Helpers to propagate/align eMAR context from picking → moves.
- Soft behavior: does not assume custom states/picking types; plays well with
  the generic creation flows implemented in clinic.emar.mixin.inventory.

Dependencies
------------
- Odoo 19 CE "stock" module
- eMAR core models (order, schedule, administration, medication line)

"""

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# Small utilities (local to this file)
# -----------------------------------------------------------------------------
def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


def _clinic_patient_from(obj):
    """Resolve the canonical clinic.patient from any eMAR artifact.

    eMAR Order intentionally exposes ``patient_id`` as ``res.partner`` for
    downstream compatibility, while other eMAR ledgers use ``clinic.patient``.
    Never copy raw IDs across different comodels.
    """
    if not obj:
        return False
    if _has_field(obj, "clinic_patient_id") and obj.clinic_patient_id:
        return obj.clinic_patient_id
    if _has_field(obj, "patient_id") and obj.patient_id:
        field = obj._fields.get("patient_id")
        if getattr(field, "comodel_name", None) == "clinic.patient":
            return obj.patient_id
    return False


def _clinic_doctor_from(obj):
    """Resolve the canonical clinic.doctor from any eMAR artifact."""
    if not obj:
        return False
    if _has_field(obj, "clinic_doctor_id") and obj.clinic_doctor_id:
        return obj.clinic_doctor_id
    if _has_field(obj, "doctor_id") and obj.doctor_id:
        field = obj._fields.get("doctor_id")
        if getattr(field, "comodel_name", None) == "clinic.doctor":
            return obj.doctor_id
    return False


def _is_lot_expired(lot):
    """
    Check lot/serial expiration with compatibility to various field names
    used by different Odoo/community variants.
    """
    if not lot:
        return False
    # Try common field names in order
    for fname in ("life_date", "expiration_date", "use_date", "removal_date"):
        if _has_field(lot, fname):
            val = getattr(lot, fname)
            # 'life_date' may be datetime; cast to date if needed
            if not val:
                continue
            try:
                if hasattr(val, "date"):
                    when = val.date()
                else:
                    when = val
                return when < date.today()
            except Exception:
                continue
    return False


# =============================================================================
# stock.picking
# =============================================================================
class StockPickingEmarBridge(models.Model):
    _inherit = "stock.picking"

    # eMAR semantic intent (informational)
    emar_intent = fields.Selection(
        [
            ("consumption", "eMAR Consumption"),
            ("return", "eMAR Return"),
            ("other", "Other"),
        ],
        string="eMAR Intent",
        default="consumption",
        help="Indicates how this picking is related to eMAR flows."
    )

    # Direct links to eMAR artifacts
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        index=True,
        help="Administration that triggered this picking (if any).",
    )
    emar_order_id = fields.Many2one(
        "clinic.emar.order",
        string="eMAR Order",
        index=True,
        help="Order related to this picking (if any).",
    )
    emar_schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="eMAR Schedule",
        index=True,
        help="Schedule related to this picking (if any).",
    )
    emar_prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="eMAR Prescription",
        index=True,
        help="Prescription related to this picking (if any).",
    )

    # Context mirrors for reporting / security
    emar_patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient resolved from the related eMAR document."
    )
    emar_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor resolved from the related eMAR document."
    )

    emar_origin_name = fields.Char(
        string="eMAR Origin",
        compute="_compute_emar_origin",
        store=True,
        help="Human-readable origin (e.g., Administration/Order name)."
    )

    @api.depends("emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id")
    def _compute_emar_origin(self):
        for rec in self:
            label = False
            if rec.emar_administration_id:
                label = _("Administration: %s") % rec.emar_administration_id.display_name
            elif rec.emar_order_id:
                label = _("Order: %s") % rec.emar_order_id.display_name
            elif rec.emar_schedule_id:
                label = _("Schedule: %s") % rec.emar_schedule_id.display_name
            elif rec.emar_prescription_id:
                label = _("Prescription: %s") % rec.emar_prescription_id.display_name
            rec.emar_origin_name = label or ""

    @api.onchange("emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id")
    def _onchange_emar_links_fill_context(self):
        """
        When an eMAR link is set, mirror patient/doctor for traceability.
        """
        for rec in self:
            # Patient
            if not rec.emar_patient_id:
                for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_schedule_id, rec.emar_prescription_id):
                    patient = _clinic_patient_from(obj)
                    if patient:
                        rec.emar_patient_id = patient.id
                        break
            # Doctor
            if not rec.emar_doctor_id:
                for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_schedule_id, rec.emar_prescription_id):
                    doctor = _clinic_doctor_from(obj)
                    if doctor:
                        rec.emar_doctor_id = doctor.id
                        break

    def write(self, vals):
        """
        Keep moves aligned with picking-level eMAR context when these fields change.
        """
        res = super().write(vals)
        touch_keys = {"emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id", "emar_patient_id", "emar_doctor_id"}
        if any(k in vals for k in touch_keys):
            for pick in self:
                for mv in pick.move_ids:
                    updates = {}
                    if "emar_administration_id" in vals:
                        updates["emar_administration_id"] = pick.emar_administration_id.id or False
                    if "emar_order_id" in vals:
                        updates["emar_order_id"] = pick.emar_order_id.id or False
                    if "emar_schedule_id" in vals:
                        updates["emar_schedule_id"] = pick.emar_schedule_id.id or False
                    if "emar_prescription_id" in vals:
                        updates["emar_prescription_id"] = pick.emar_prescription_id.id or False
                    if "emar_patient_id" in vals:
                        updates["emar_patient_id"] = pick.emar_patient_id.id or False
                    if "emar_doctor_id" in vals:
                        updates["emar_doctor_id"] = pick.emar_doctor_id.id or False
                    if updates:
                        mv.sudo().write(updates)
        return res

    @api.constrains("company_id", "emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id")
    def _check_company_alignment(self):
        for rec in self:
            for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_schedule_id, rec.emar_prescription_id):
                if obj and _has_field(obj, "company_id") and obj.company_id and obj.company_id != rec.company_id:
                    raise ValidationError(_("Company mismatch between the Picking and its eMAR link."))

    # Convenience action: view eMAR source
    def action_open_emar_source(self):
        self.ensure_one()
        if self.emar_administration_id:
            return {
                "name": _("Administration"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.administration",
                "view_mode": "form",
                "res_id": self.emar_administration_id.id,
            }
        if self.emar_order_id:
            return {
                "name": _("Order"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.order",
                "view_mode": "form",
                "res_id": self.emar_order_id.id,
            }
        if self.emar_schedule_id:
            return {
                "name": _("Schedule"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.schedule",
                "view_mode": "form",
                "res_id": self.emar_schedule_id.id,
            }
        if self.emar_prescription_id:
            return {
                "name": _("Prescription"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.prescription",
                "view_mode": "form",
                "res_id": self.emar_prescription_id.id,
            }
        raise UserError(_("No eMAR origin linked to this picking."))


# =============================================================================
# stock.move
# =============================================================================
class StockMoveEmarBridge(models.Model):
    _inherit = "stock.move"

    # eMAR linkage
    emar_line_id = fields.Many2one(
        "clinic.emar.medication.line",
        string="eMAR Line",
        index=True,
        help="Medication line that this stock move is fulfilling (if any)."
    )
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        index=True,
        help="Administration record associated to this move (if any)."
    )
    emar_order_id = fields.Many2one(
        "clinic.emar.order",
        string="eMAR Order",
        index=True,
        help="Order associated to this move (if any)."
    )
    emar_schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="eMAR Schedule",
        index=True,
        help="Schedule associated to this move (if any)."
    )
    emar_prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="eMAR Prescription",
        index=True,
        help="Prescription associated to this move (if any)."
    )

    # Context mirrors for analytics
    emar_patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient resolved from the eMAR context."
    )
    emar_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor resolved from the eMAR context."
    )

    @api.onchange("emar_line_id")
    def _onchange_emar_line_autofill(self):
        for rec in self:
            ln = rec.emar_line_id
            if ln:
                # product fallback (admin mixin typically sets product_id already)
                if not rec.product_id and _has_field(ln, "product_id") and ln.product_id:
                    rec.product_id = ln.product_id
                # mirror header refs
                if _has_field(ln, "order_id") and ln.order_id:
                    rec.emar_order_id = ln.order_id.id
                if _has_field(ln, "prescription_id") and ln.prescription_id:
                    rec.emar_prescription_id = ln.prescription_id.id
                # patient/doctor mirrors
                patient = _clinic_patient_from(ln)
                if patient and not rec.emar_patient_id:
                    rec.emar_patient_id = patient.id
                doctor = _clinic_doctor_from(ln)
                if doctor and not rec.emar_doctor_id:
                    rec.emar_doctor_id = doctor.id

    @api.onchange("picking_id")
    def _onchange_picking_emar_context(self):
        for rec in self:
            pick = rec.picking_id
            if pick:
                # copy eMAR context from picking if empty
                if not rec.emar_administration_id and pick.emar_administration_id:
                    rec.emar_administration_id = pick.emar_administration_id.id
                if not rec.emar_order_id and pick.emar_order_id:
                    rec.emar_order_id = pick.emar_order_id.id
                if not rec.emar_schedule_id and pick.emar_schedule_id:
                    rec.emar_schedule_id = pick.emar_schedule_id.id
                if not rec.emar_prescription_id and pick.emar_prescription_id:
                    rec.emar_prescription_id = pick.emar_prescription_id.id
                if not rec.emar_patient_id and pick.emar_patient_id:
                    rec.emar_patient_id = pick.emar_patient_id.id
                if not rec.emar_doctor_id and pick.emar_doctor_id:
                    rec.emar_doctor_id = pick.emar_doctor_id.id

    @api.constrains("company_id", "picking_id", "emar_administration_id", "emar_order_id", "emar_prescription_id")
    def _check_company_alignment(self):
        for rec in self:
            cmp = rec.company_id
            for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_prescription_id):
                if obj and _has_field(obj, "company_id") and obj.company_id and obj.company_id != cmp:
                    raise ValidationError(_("Company mismatch between the Move and its eMAR link."))


# =============================================================================
# stock.move.line
# =============================================================================
class StockMoveLineEmarBridge(models.Model):
    _inherit = "stock.move.line"

    emar_line_id = fields.Many2one(
        "clinic.emar.medication.line",
        string="eMAR Line",
        index=True,
        help="Medication line that this move line is fulfilling (if any)."
    )
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        index=True,
        help="Administration record associated to this move line (if any)."
    )

    @api.onchange("move_id")
    def _onchange_move_copy_emar(self):
        for rec in self:
            mv = rec.move_id
            if mv:
                if not rec.emar_line_id and mv.emar_line_id:
                    rec.emar_line_id = mv.emar_line_id.id
                if not rec.emar_administration_id and mv.emar_administration_id:
                    rec.emar_administration_id = mv.emar_administration_id.id

    @api.constrains("lot_id")
    def _check_lot_not_expired(self):
        """
        Prevent using an expired lot for eMAR-related consumptions.
        Only enforce when an eMAR context is present to avoid disrupting generic operations.
        """
        for rec in self:
            if rec.lot_id and (rec.emar_line_id or rec.emar_administration_id):
                if _is_lot_expired(rec.lot_id):
                    raise ValidationError(_("Selected Lot/Serial is expired for this eMAR move line."))

