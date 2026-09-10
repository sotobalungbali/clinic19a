
# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ClinicReferralTreatmentSessionBridge(models.Model):
    """Downstream Treatment Session lineage on Clinic Referral."""

    _inherit = "clinic.referral"

    treatment_session_ids = fields.One2many(
        "clinic.treatment.session", "referral_id",
        string="Direct Treatment Sessions", readonly=True,
    )

    def action_open_treatment_sessions(self):
        self.ensure_one()
        lines = self.env["clinic.treatment.session.line"].search(
            [("referral_id", "=", self.id)]
        )
        sessions = self.treatment_session_ids | lines.mapped("session_id")
        return {
            "type": "ir.actions.act_window", "name": _("Referral Treatment Sessions"),
            "res_model": "clinic.treatment.session", "view_mode": "list,kanban,form",
            "domain": [("id", "in", sessions.ids)],
            "context": {"default_referral_id": self.id},
        }
