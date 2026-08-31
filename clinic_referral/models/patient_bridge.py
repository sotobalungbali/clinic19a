# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ClinicPatientReferral(models.Model):
    """Expose referral acquisition history on Patient 360."""

    _inherit = "clinic.patient"

    referral_ids = fields.One2many(
        "clinic.referral",
        "patient_id",
        string="Inbound Referrals",
        readonly=True,
    )
    referral_count = fields.Integer(compute="_compute_referral_counts")
    converted_referral_count = fields.Integer(
        compute="_compute_referral_counts"
    )
    outgoing_referral_ids = fields.One2many(
        "clinic.referral",
        "referrer_patient_id",
        string="Patient Referrals",
        readonly=True,
    )
    outgoing_referral_count = fields.Integer(
        compute="_compute_referral_counts"
    )

    @api.depends("referral_ids.state", "outgoing_referral_ids.state")
    def _compute_referral_counts(self):
        for patient in self:
            patient.referral_count = len(patient.referral_ids)
            patient.converted_referral_count = len(
                patient.referral_ids.filtered(
                    lambda referral: referral.state == "converted"
                )
            )
            patient.outgoing_referral_count = len(patient.outgoing_referral_ids)

    def action_open_referrals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Referrals"),
            "res_model": "clinic.referral",
            "view_mode": "list,kanban,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    def action_open_outgoing_referrals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Referrals by Patient"),
            "res_model": "clinic.referral",
            "view_mode": "list,kanban,form",
            "domain": [("referrer_patient_id", "=", self.id)],
            "context": {
                "default_referrer_type": "patient",
                "default_referrer_patient_id": self.id,
            },
        }

