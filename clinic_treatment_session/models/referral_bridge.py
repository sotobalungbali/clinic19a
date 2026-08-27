# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ClinicReferralTreatmentSessionBridge(models.Model):
    """Downstream Referral bridge without changing Referral ownership."""

    _inherit = "clinic.referral"

    treatment_session_ids = fields.One2many(
        "clinic.treatment.session",
        "referral_id",
        string="Direct Treatment Sessions",
        readonly=True,
    )

    def _compute_related_counts(self):
        super()._compute_related_counts()
        SessionLine = self.env["clinic.treatment.session.line"]

        for referral in self:
            direct = referral.treatment_session_ids
            lines = SessionLine.search(
                [("referral_id", "=", referral.id)]
            )
            referral.treatment_session_count = len(
                direct | lines.mapped("session_id")
            )

    def action_open_treatment_sessions(self):
        self.ensure_one()
        lines = self.env["clinic.treatment.session.line"].search(
            [("referral_id", "=", self.id)]
        )
        sessions = self.treatment_session_ids | lines.mapped("session_id")

        return {
            "type": "ir.actions.act_window",
            "name": _("Referral Treatment Sessions"),
            "res_model": "clinic.treatment.session",
            "view_mode": "list,kanban,form",
            "domain": [("id", "in", sessions.ids)],
            "context": {"default_referral_id": self.id},
        }
