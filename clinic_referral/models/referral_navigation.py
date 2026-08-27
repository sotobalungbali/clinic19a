# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError

from .referral_utils import optional_model


class ClinicReferralNavigation(models.Model):
    """Human-friendly navigation layer for Referral cross-addon drill-down."""

    _inherit = "clinic.referral"

    def action_open_self(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Referral"),
            "res_model": "clinic.referral",
            "res_id": self.id,
            "view_mode": "form",
        }

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "clinic.patient",
            "res_id": self.patient_id.id,
            "view_mode": "form",
        }

    def action_open_origin(self):
        self.ensure_one()
        return self._open_generic_reference(
            self.origin_model_id,
            self.origin_res_id,
            _("Origin Document"),
        )

    def action_open_conversion(self):
        self.ensure_one()
        return self._open_generic_reference(
            self.conversion_model_id,
            self.conversion_res_id,
            _("Conversion Document"),
        )

    def _open_generic_reference(self, model_rec, res_id, title):
        if not model_rec or not res_id:
            raise UserError(_("No linked document is available."))
        Model = optional_model(self.env, model_rec.model)
        if not Model:
            raise UserError(_("The linked model is not available."))
        record = Model.browse(res_id).exists()
        if not record:
            raise UserError(_("The linked document no longer exists."))
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_rec.model,
            "res_id": record.id,
            "view_mode": "form",
        }

    def action_create_booking(self):
        self.ensure_one()
        if not self.patient_id.partner_id:
            raise UserError(
                _(
                    "The referral patient must have a linked Contact before "
                    "creating a booking."
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("New Booking from Referral"),
            "res_model": "booking.booking",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": self.patient_id.partner_id.id,
                "default_doctor_id": self.target_doctor_id.id,
                "default_referral_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_open_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Referral Bookings"),
            "res_model": "booking.booking",
            "view_mode": "list,calendar,form",
            "domain": [("referral_id", "=", self.id)],
            "context": {"default_referral_id": self.id},
        }

    def action_open_treatment_sessions(self):
        self.ensure_one()
        SessionLine = optional_model(self.env, "clinic.treatment.session.line")
        Session = optional_model(self.env, "clinic.treatment.session")
        if not SessionLine or not Session:
            raise UserError(_("Clinic Treatment Session is not installed."))
        lines = SessionLine.search([("referral_id", "=", self.id)])
        return {
            "type": "ir.actions.act_window",
            "name": _("Referral Treatment Sessions"),
            "res_model": "clinic.treatment.session",
            "view_mode": "list,form",
            "domain": [("id", "in", lines.mapped("session_id").ids)],
        }

    def action_open_memberships(self):
        self.ensure_one()
        Membership = optional_model(self.env, "membership.contract")
        if not Membership:
            raise UserError(_("Clinic Membership is not installed."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Referral Memberships"),
            "res_model": "membership.contract",
            "view_mode": "list,form",
            "domain": [("referral_id", "=", self.id)],
        }

    def action_open_audit_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Referral Audit Events"),
            "res_model": "clinic.audit.event",
            "view_mode": "list,form",
            "domain": [
                ("ref_model", "=", self._name),
                ("ref_res_id", "=", self.id),
            ],
        }

    def action_open_crm_lead(self):
        self.ensure_one()
        if not self.lead_id:
            raise UserError(_("No CRM Lead / Opportunity is linked."))
        return {
            "type": "ir.actions.act_window",
            "name": _("CRM Lead / Opportunity"),
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
        }

    def _compute_display_name(self):
        super()._compute_display_name()
        for referral in self:
            label = referral.name or ""
            if referral.patient_id:
                label = "%s - %s" % (label, referral.patient_id.display_name)
            referral.display_name = label

    def name_get(self):
        """Preserve the legacy public display-name API for downstream callers."""
        result = []
        for referral in self:
            display = referral.name or ""
            if referral.patient_id:
                display = "%s - %s" % (
                    display,
                    referral.patient_id.display_name,
                )
            result.append((referral.id, display))
        return result
