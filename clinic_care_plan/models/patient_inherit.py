# -*- coding: utf-8 -*-
"""Reverse Care Plan navigation on the canonical ClinicOne patient."""

from odoo import api, fields, models, _


class ClinicPatientCarePlan(models.Model):
    _inherit = "clinic.patient"

    care_plan_ids = fields.One2many(
        "clinic.care.plan",
        "patient_id",
        string="Care Plans",
        readonly=True,
    )
    care_plan_count = fields.Integer(
        string="Care Plans",
        compute="_compute_care_plan_metrics",
    )
    active_care_plan_count = fields.Integer(
        string="Active Care Plans",
        compute="_compute_care_plan_metrics",
    )

    @api.depends("care_plan_ids.state", "care_plan_ids.active")
    def _compute_care_plan_metrics(self):
        for rec in self:
            plans = rec.care_plan_ids
            rec.care_plan_count = len(plans)
            rec.active_care_plan_count = len(
                plans.filtered(lambda plan: plan.active and plan.state == "active")
            )

    def action_view_care_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plans"),
            "res_model": "clinic.care.plan",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.id,
                "default_company_id": self.company_id.id,
            },
            "target": "current",
        }

    def action_create_care_plan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Care Plan"),
            "res_model": "clinic.care.plan",
            "view_mode": "form",
            "context": {
                "default_patient_id": self.id,
                "default_company_id": self.company_id.id,
            },
            "target": "current",
        }
