# -*- coding: utf-8 -*-
"""Reverse Care Plan navigation on the canonical ClinicOne doctor."""

from odoo import api, fields, models, _


class ClinicDoctorCarePlan(models.Model):
    _inherit = "clinic.doctor"

    care_plan_ids = fields.One2many(
        "clinic.care.plan",
        "doctor_id",
        string="Care Plans",
        readonly=True,
    )
    care_plan_count = fields.Integer(
        string="Care Plans",
        compute="_compute_care_plan_count",
    )

    @api.depends("care_plan_ids")
    def _compute_care_plan_count(self):
        for rec in self:
            rec.care_plan_count = len(rec.care_plan_ids)

    def action_view_care_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plans"),
            "res_model": "clinic.care.plan",
            "view_mode": "list,form",
            "domain": [("doctor_id", "=", self.id)],
            "context": {
                "default_doctor_id": self.id,
                "default_company_id": self.company_id.id,
            },
            "target": "current",
        }
