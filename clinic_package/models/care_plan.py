
# -*- coding: utf-8 -*-
"""Care-plan linkage for package-backed multi-session treatment programs."""

from odoo import fields, models, _


class ClinicCarePlan(models.Model):
    _inherit = "clinic.care.plan"

    package_allocation_id = fields.Many2one(
        "clinic.package.allocation", string="Package Allocation", ondelete="set null", check_company=True
    )
    package_id = fields.Many2one(
        "clinic.package", related="package_allocation_id.package_id", store=True, readonly=True
    )
    package_usage_count = fields.Integer(compute="_compute_package_usage_count")

    def _compute_package_usage_count(self):
        Usage = self.env["clinic.package.usage"]
        for plan in self:
            plan.package_usage_count = Usage.search_count([("care_plan_id", "=", plan.id)])

    def action_view_package_allocation(self):
        self.ensure_one()
        if not self.package_allocation_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocation"),
            "res_model": "clinic.package.allocation",
            "view_mode": "form",
            "res_id": self.package_allocation_id.id,
        }

    def action_view_package_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("care_plan_id", "=", self.id)],
            "context": {
                "default_care_plan_id": self.id,
                "default_allocation_id": self.package_allocation_id.id,
            },
        }


class ClinicCarePlanLine(models.Model):
    _inherit = "clinic.care.plan.line"

    package_allocation_line_id = fields.Many2one(
        "clinic.package.allocation.line", string="Package Benefit", ondelete="set null", check_company=True
    )
    package_usage_ids = fields.One2many(
        "clinic.package.usage", "care_plan_line_id", string="Package Redemptions", readonly=True
    )
    package_usage_count = fields.Integer(compute="_compute_package_usage_count")

    def _compute_package_usage_count(self):
        for line in self:
            line.package_usage_count = len(line.package_usage_ids)

    def action_redeem_package_benefit(self):
        self.ensure_one()
        allocation = self.plan_id.package_allocation_id
        if not allocation:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Redeem Package Benefit"),
            "res_model": "clinic.package.redeem.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_allocation_id": allocation.id,
                "default_allocation_line_id": self.package_allocation_line_id.id,
                "default_care_plan_line_id": self.id,
                "default_booking_id": self.booking_id.id,
                "default_doctor_id": self.doctor_id.id,
            },
        }
