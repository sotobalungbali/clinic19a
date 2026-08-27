
# -*- coding: utf-8 -*-
"""Patient-facing package portfolio integration."""

from odoo import fields, models, _


class ClinicPatient(models.Model):
    _inherit = "clinic.patient"

    package_allocation_ids = fields.One2many(
        "clinic.package.allocation", "patient_id", string="Treatment Packages"
    )
    package_allocation_count = fields.Integer(compute="_compute_package_portfolio")
    package_active_count = fields.Integer(compute="_compute_package_portfolio")
    package_remaining_value = fields.Monetary(
        compute="_compute_package_portfolio", currency_field="package_currency_id"
    )
    package_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )

    def _compute_package_portfolio(self):
        for patient in self:
            allocations = patient.package_allocation_ids
            patient.package_allocation_count = len(allocations)
            patient.package_active_count = len(
                allocations.filtered(lambda allocation: allocation.state in ("active", "paused"))
            )
            patient.package_remaining_value = sum(allocations.mapped("remaining_value"))

    def action_view_package_allocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Packages"),
            "res_model": "clinic.package.allocation",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id, "default_partner_id": self.partner_id.id},
        }

    def action_allocate_package(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Package Allocation"),
            "res_model": "clinic.package.allocation",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": self.id,
                "default_partner_id": self.partner_id.id or False,
                "default_company_id": self.company_id.id,
            },
        }
