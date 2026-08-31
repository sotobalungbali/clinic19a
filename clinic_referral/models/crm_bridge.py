# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmLeadReferral(models.Model):
    """Connect CRM acquisition opportunities to ClinicOne referrals."""

    _inherit = "crm.lead"

    clinic_referral_ids = fields.One2many(
        "clinic.referral",
        "lead_id",
        string="Clinic Referrals",
        readonly=True,
    )
    clinic_referral_count = fields.Integer(
        compute="_compute_clinic_referral_counts"
    )
    clinic_converted_referral_count = fields.Integer(
        compute="_compute_clinic_referral_counts"
    )

    @api.depends("clinic_referral_ids.state")
    def _compute_clinic_referral_counts(self):
        for lead in self:
            lead.clinic_referral_count = len(lead.clinic_referral_ids)
            lead.clinic_converted_referral_count = len(
                lead.clinic_referral_ids.filtered(
                    lambda referral: referral.state == "converted"
                )
            )

    def action_open_clinic_referrals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Referrals"),
            "res_model": "clinic.referral",
            "view_mode": "list,kanban,form",
            "domain": [("lead_id", "=", self.id)],
            "context": {"default_lead_id": self.id},
        }

