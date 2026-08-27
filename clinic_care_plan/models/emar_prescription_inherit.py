# -*- coding: utf-8 -*-
"""Care Plan bridge for eMAR prescriptions."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicEmarPrescription(models.Model):
    _inherit = "clinic.emar.prescription"

    care_plan_id = fields.Many2one(
        "clinic.care.plan",
        string="Care Plan",
        index=True,
        ondelete="set null",
        tracking=True,
        help="Care plan this prescription belongs to.",
    )

    care_plan_line_id = fields.Many2one(
        "clinic.care.plan.line",
        string="Care Plan Line",
        index=True,
        ondelete="set null",
        tracking=True,
        help="Executable care-plan line that originated this prescription.",
    )

    @api.onchange("care_plan_id", "care_plan_line_id")
    def _onchange_care_plan_id(self):
        """Align eMAR header context without overwriting explicit user choices."""
        for rec in self:
            line = rec.care_plan_line_id
            plan = rec.care_plan_id or line.plan_id
            if line and not rec.care_plan_id:
                rec.care_plan_id = line.plan_id
            if not plan:
                continue
            if not rec.company_id:
                rec.company_id = plan.company_id
            if not rec.patient_id and plan.patient_id:
                rec.patient_id = plan.patient_id
            if not rec.doctor_id and plan.doctor_id:
                rec.doctor_id = plan.doctor_id

    @api.constrains("company_id", "care_plan_id", "care_plan_line_id")
    def _check_company_alignment_care_plan(self):
        for rec in self:
            line = rec.care_plan_line_id
            plan = rec.care_plan_id or line.plan_id
            if line and rec.care_plan_id and line.plan_id != rec.care_plan_id:
                raise ValidationError(
                    _("The Care Plan Line must belong to the selected Care Plan.")
                )
            if (
                plan
                and plan.company_id
                and rec.company_id
                and plan.company_id != rec.company_id
            ):
                raise ValidationError(
                    _("Company mismatch between the Prescription and its Care Plan.")
                )

    def _sync_care_plan_line_link(self):
        """Keep the direct line → prescription smart link aligned."""
        for rec in self.filtered("care_plan_line_id"):
            line = rec.care_plan_line_id
            if line.prescription_id != rec:
                line.prescription_id = rec

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_care_plan_line_link()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "care_plan_line_id" in vals:
            self._sync_care_plan_line_link()
        return result

    def action_open_care_plan(self):
        self.ensure_one()
        plan = self.care_plan_id or self.care_plan_line_id.plan_id
        if not plan:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plan"),
            "res_model": "clinic.care.plan",
            "view_mode": "form",
            "res_id": plan.id,
            "target": "current",
        }
