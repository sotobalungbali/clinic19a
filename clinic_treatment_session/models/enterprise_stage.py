
# -*- coding: utf-8 -*-
from odoo import api, models


class ClinicTreatmentSessionStageEnterprise(models.Model):
    """Idempotently ensure per-company default stages."""

    _inherit = "clinic.treatment.session.stage"

    @api.model
    def _ensure_enterprise_default_stages(self):
        Stage = self.sudo()
        specs = (
            ("Draft", "draft", 10, False, False),
            ("Confirmed", "confirmed", 20, False, False),
            ("In Progress", "in_progress", 30, False, False),
            ("Done", "done", 40, True, True),
            ("No-show", "no_show", 50, True, True),
            ("Cancelled", "cancelled", 60, True, True),
        )
        for company in self.env["res.company"].sudo().search([]):
            for name, state, sequence, final, fold in specs:
                stage = Stage.search([
                    ("company_id", "=", company.id),
                    ("technical_state", "=", state),
                ], order="is_default desc, sequence, id", limit=1)
                vals = {
                    "name": name, "company_id": company.id,
                    "technical_state": state, "sequence": sequence,
                    "is_default": True, "is_final": final,
                    "fold": fold, "active": True,
                }
                if stage:
                    vals.pop("name")
                    stage.write(vals)
                else:
                    Stage.create(vals)
        return True
