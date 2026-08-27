# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - External Bridge: Accounting
Bridges eMAR artifacts to Odoo Accounting (account.* models).

This file is the ONLY place inside clinic_emar that _inherit(s) accounting models,
to avoid multi-inherit collisions in Odoo 19 CE.

Key points
----------
- Adds eMAR linkage fields on account.move (invoice), account.move.line, and account.payment (optional).
- Mirrors Patient/Doctor context for analytics and security alignment.
- Keeps header <-> line eMAR context in sync on write/onchange.
- Uses 'invoice_origin' to reference eMAR origin (Administration/Order), enabling cross-navigation.
- Company alignment constraints to prevent cross-company contamination.

Dependencies
------------
- Odoo 19 CE "account" module
- eMAR core models (order, prescription, schedule, administration, medication line)

"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# Local utilities
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


# =============================================================================
# account.move (Invoices)
# =============================================================================
class AccountMoveEmarBridge(models.Model):
    _inherit = "account.move"

    # eMAR semantic intent (informational)
    emar_intent = fields.Selection(
        [
            ("emar_billing", "eMAR Billing"),
            ("emar_refund", "eMAR Refund"),
            ("other", "Other"),
        ],
        string="eMAR Intent",
        default="emar_billing",
        help="Indicates how this invoice is related to eMAR flows."
    )

    # Direct links to eMAR artifacts (header scope)
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        index=True,
        help="Administration that originated this invoice (if any).",
    )
    emar_order_id = fields.Many2one(
        "clinic.emar.order",
        string="eMAR Order",
        index=True,
        help="eMAR Order billed on this invoice (if any).",
    )
    emar_schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="eMAR Schedule",
        index=True,
        help="eMAR Schedule billed on this invoice (if any).",
    )
    emar_prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="eMAR Prescription",
        index=True,
        help="eMAR Prescription billed on this invoice (if any).",
    )

    # Context mirrors for analytics / security
    emar_patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient resolved from eMAR context."
    )
    emar_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor resolved from eMAR context."
    )

    # Quick flag for UI filters
    is_emar_invoice = fields.Boolean(
        string="Is eMAR Invoice",
        compute="_compute_is_emar_invoice",
        store=True,
        help="True if this invoice is linked to any eMAR artifact."
    )

    @api.depends("emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id")
    def _compute_is_emar_invoice(self):
        for rec in self:
            rec.is_emar_invoice = bool(
                rec.emar_administration_id or rec.emar_order_id or rec.emar_schedule_id or rec.emar_prescription_id
            )

    # --------------------------------------------------------------
    # Onchange: backfill invoice_origin, patient, doctor
    # --------------------------------------------------------------
    @api.onchange("emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id")
    def _onchange_emar_links_fill_context(self):
        for rec in self:
            # Set invoice_origin if empty (non-destructive)
            if not rec.invoice_origin:
                if rec.emar_administration_id:
                    rec.invoice_origin = _("Administration: %s") % rec.emar_administration_id.display_name
                elif rec.emar_order_id:
                    rec.invoice_origin = _("Order: %s") % rec.emar_order_id.display_name
                elif rec.emar_schedule_id:
                    rec.invoice_origin = _("Schedule: %s") % rec.emar_schedule_id.display_name
                elif rec.emar_prescription_id:
                    rec.invoice_origin = _("Prescription: %s") % rec.emar_prescription_id.display_name

            # Patient mirror
            if not rec.emar_patient_id:
                for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_schedule_id, rec.emar_prescription_id):
                    patient = _clinic_patient_from(obj)
                    if patient:
                        rec.emar_patient_id = patient.id
                        break
            # Doctor mirror
            if not rec.emar_doctor_id:
                for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_schedule_id, rec.emar_prescription_id):
                    doctor = _clinic_doctor_from(obj)
                    if doctor:
                        rec.emar_doctor_id = doctor.id
                        break

    # --------------------------------------------------------------
    # Write: propagate header eMAR context to lines
    # --------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        touch = {"emar_administration_id", "emar_order_id", "emar_schedule_id",
                 "emar_prescription_id", "emar_patient_id", "emar_doctor_id"}
        if any(k in vals for k in touch):
            for mv in self:
                for line in mv.invoice_line_ids:
                    updates = {}
                    if "emar_administration_id" in vals:
                        updates["emar_administration_id"] = mv.emar_administration_id.id or False
                    if "emar_order_id" in vals:
                        updates["emar_order_id"] = mv.emar_order_id.id or False
                    if "emar_schedule_id" in vals:
                        updates["emar_schedule_id"] = mv.emar_schedule_id.id or False
                    if "emar_prescription_id" in vals:
                        updates["emar_prescription_id"] = mv.emar_prescription_id.id or False
                    if "emar_patient_id" in vals and not line.emar_patient_id:
                        updates["emar_patient_id"] = mv.emar_patient_id.id or False
                    if "emar_doctor_id" in vals and not line.emar_doctor_id:
                        updates["emar_doctor_id"] = mv.emar_doctor_id.id or False
                    if updates:
                        line.sudo().write(updates)
        return res

    # --------------------------------------------------------------
    # Validation: cross-company safety
    # --------------------------------------------------------------
    @api.constrains("company_id", "emar_administration_id", "emar_order_id", "emar_schedule_id", "emar_prescription_id")
    def _check_company_alignment(self):
        for rec in self:
            cmp = rec.company_id
            for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_schedule_id, rec.emar_prescription_id):
                if obj and _has_field(obj, "company_id") and obj.company_id and obj.company_id != cmp:
                    raise ValidationError(_("Company mismatch between the Invoice and its eMAR link."))

    # --------------------------------------------------------------
    # Convenience action: open eMAR source
    # --------------------------------------------------------------
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
        raise UserError(_("No eMAR origin linked to this invoice."))


# =============================================================================
# account.move.line (Invoice Lines)
# =============================================================================
class AccountMoveLineEmarBridge(models.Model):
    _inherit = "account.move.line"

    # Link to eMAR artifacts (line scope)
    emar_line_id = fields.Many2one(
        "clinic.emar.medication.line",
        string="eMAR Line",
        index=True,
        help="Medication line that this invoice line is billing (if any)."
    )
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        index=True,
        help="Administration associated to this invoice line (if any)."
    )
    emar_order_id = fields.Many2one(
        "clinic.emar.order",
        string="eMAR Order",
        index=True,
        help="Order associated to this invoice line (if any)."
    )
    emar_schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="eMAR Schedule",
        index=True,
        help="Schedule associated to this invoice line (if any)."
    )
    emar_prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="eMAR Prescription",
        index=True,
        help="Prescription associated to this invoice line (if any)."
    )

    # Mirrors for analytics
    emar_patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient resolved from eMAR context."
    )
    emar_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor resolved from eMAR context."
    )

    # --------------------------------------------------------------
    # Onchange: copy from header if missing
    # --------------------------------------------------------------
    @api.onchange("move_id")
    def _onchange_move_copy_emar(self):
        for rec in self:
            mv = rec.move_id
            if not mv:
                continue
            # copy header links if not set on line
            if not rec.emar_administration_id and mv.emar_administration_id:
                rec.emar_administration_id = mv.emar_administration_id.id
            if not rec.emar_order_id and mv.emar_order_id:
                rec.emar_order_id = mv.emar_order_id.id
            if not rec.emar_schedule_id and mv.emar_schedule_id:
                rec.emar_schedule_id = mv.emar_schedule_id.id
            if not rec.emar_prescription_id and mv.emar_prescription_id:
                rec.emar_prescription_id = mv.emar_prescription_id.id
            if not rec.emar_patient_id and mv.emar_patient_id:
                rec.emar_patient_id = mv.emar_patient_id.id
            if not rec.emar_doctor_id and mv.emar_doctor_id:
                rec.emar_doctor_id = mv.emar_doctor_id.id

    # --------------------------------------------------------------
    # Validation: cross-company safety (via move.company_id)
    # --------------------------------------------------------------
    @api.constrains("move_id", "emar_administration_id", "emar_order_id", "emar_prescription_id")
    def _check_company_alignment(self):
        for rec in self:
            cmp = rec.move_id.company_id if rec.move_id else False
            for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_prescription_id):
                if obj and _has_field(obj, "company_id") and obj.company_id and cmp and obj.company_id != cmp:
                    raise ValidationError(_("Company mismatch between the Invoice Line and its eMAR link."))


# =============================================================================
# account.payment (optional bridge)
# =============================================================================
class AccountPaymentEmarBridge(models.Model):
    _inherit = "account.payment"

    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        index=True,
        help="Administration associated to this payment (if any)."
    )
    emar_order_id = fields.Many2one(
        "clinic.emar.order",
        string="eMAR Order",
        index=True,
        help="Order associated to this payment (if any)."
    )
    emar_prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="eMAR Prescription",
        index=True,
        help="Prescription associated to this payment (if any)."
    )
    emar_patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient resolved from eMAR context."
    )
    emar_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor resolved from eMAR context."
    )

    @api.onchange("ref")
    def _onchange_ref_hint_emar(self):
        """
        Non-intrusive helper: if 'ref' contains an Administration/Order name,
        users can manually link the payment to the appropriate eMAR document.
        (No auto-search here to avoid surprises.)
        """
        # Reserved for future enhancements
        return

    @api.constrains("company_id", "emar_administration_id", "emar_order_id", "emar_prescription_id")
    def _check_company_alignment(self):
        for rec in self:
            cmp = rec.company_id
            for obj in (rec.emar_administration_id, rec.emar_order_id, rec.emar_prescription_id):
                if obj and _has_field(obj, "company_id") and obj.company_id and obj.company_id != cmp:
                    raise ValidationError(_("Company mismatch between the Payment and its eMAR link."))

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
        if self.emar_prescription_id:
            return {
                "name": _("Prescription"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.prescription",
                "view_mode": "form",
                "res_id": self.emar_prescription_id.id,
            }
        raise UserError(_("No eMAR origin linked to this payment."))
