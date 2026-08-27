# -*- coding: utf-8 -*-

from odoo import api, models


class ClinicTreatmentSessionStageEnterprise(models.Model):
    """Idempotent default-stage bootstrap for existing and fresh databases."""

    _inherit = "clinic.treatment.session.stage"

    @api.model
    def _ensure_enterprise_default_stages(self):
        Stage = self.sudo()
        companies = self.env["res.company"].sudo().search([])

        specs = (
            ("Draft", "draft", 10, False, False),
            ("Confirmed", "confirmed", 20, False, False),
            ("In Progress", "in_progress", 30, False, False),
            ("Done", "done", 40, True, True),
            ("No-show", "no_show", 50, True, True),
            ("Cancelled", "cancelled", 60, True, True),
        )

        for company in companies:
            for name, technical_state, sequence, is_final, fold in specs:
                stage = Stage.search(
                    [
                        ("company_id", "=", company.id),
                        ("technical_state", "=", technical_state),
                    ],
                    order="is_default desc, sequence, id",
                    limit=1,
                )

                values = {
                    "name": name,
                    "company_id": company.id,
                    "technical_state": technical_state,
                    "sequence": sequence,
                    "is_default": True,
                    "is_final": is_final,
                    "fold": fold,
                    "active": True,
                }

                if stage:
                    # Preserve a deliberately customized stage name; only fill
                    # governance flags and ordering needed for the workflow.
                    values.pop("name")
                    stage.write(values)
                else:
                    Stage.create(values)

        return True
