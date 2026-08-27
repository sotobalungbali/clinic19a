# -*- coding: utf-8 -*-
"""Care Plan bridge for Encounter procedure sessions."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicProcedureSessionInherit(models.Model):
    _inherit = "clinic.procedure.session"

    care_plan_id = fields.Many2one(
        "clinic.care.plan",
        string="Care Plan",
        index=True,
        ondelete="set null",
        tracking=True,
        help="Care plan that governs this procedure session.",
    )

    care_plan_line_id = fields.Many2one(
        "clinic.care.plan.line",
        string="Care Plan Line",
        index=True,
        ondelete="set null",
        tracking=True,
        help="Executable care-plan line that originated this procedure session.",
    )

    @api.onchange("care_plan_line_id")
    def _onchange_care_plan_line_id(self):
        """Translate care-plan execution context to Encounter session fields."""
        for rec in self:
            line = rec.care_plan_line_id
            if not line:
                continue
            rec.care_plan_id = line.plan_id
            if not rec.treatment_id and line.treatment_id:
                rec.treatment_id = line.treatment_id
            if not rec.performer_doctor_id and line.doctor_id:
                rec.performer_doctor_id = line.doctor_id
            if not rec.planned_start and line.scheduled_datetime:
                rec.planned_start = line.scheduled_datetime
            if not rec.planned_duration and line.duration_minutes:
                rec.planned_duration = line.duration_minutes
            if not rec.internal_note and line.description:
                rec.internal_note = line.description

    @api.constrains("care_plan_id", "care_plan_line_id", "company_id")
    def _check_care_plan_company(self):
        """Keep plan, plan line and Encounter session within one company."""
        for rec in self:
            plan = rec.care_plan_id
            line = rec.care_plan_line_id
            if line and plan and line.plan_id != plan:
                raise ValidationError(
                    _("The Care Plan Line must belong to the selected Care Plan.")
                )
            if line and not plan:
                plan = line.plan_id
            if (
                plan
                and plan.company_id
                and rec.company_id
                and plan.company_id != rec.company_id
            ):
                raise ValidationError(
                    _("Care Plan company must match the Procedure Session company.")
                )

    def _sync_care_plan_line_link(self):
        """Keep the direct line → session smart link aligned."""
        for rec in self.filtered("care_plan_line_id"):
            line = rec.care_plan_line_id
            if line.session_id != rec:
                line.session_id = rec

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
