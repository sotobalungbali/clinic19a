
# -*- coding: utf-8 -*-
"""Package portfolio summary on the Odoo contact used by ClinicOne patients."""

from odoo import fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    clinic_package_allocation_count = fields.Integer(compute="_compute_clinic_package_stats")
    clinic_package_active_count = fields.Integer(compute="_compute_clinic_package_stats")
    clinic_package_remaining_value = fields.Monetary(
        compute="_compute_clinic_package_stats", currency_field="clinic_package_currency_id"
    )
    clinic_package_currency_id = fields.Many2one(
        "res.currency", compute="_compute_clinic_package_currency", readonly=True
    )

    def _compute_clinic_package_currency(self):
        currency = self.env.company.currency_id
        for partner in self:
            partner.clinic_package_currency_id = currency

    def _compute_clinic_package_stats(self):
        Allocation = self.env["clinic.package.allocation"]
        for partner in self:
            allocations = Allocation.search([("company_id", "=", self.env.company.id), ("partner_id", "child_of", partner.commercial_partner_id.id)])
            partner.clinic_package_allocation_count = len(allocations)
            partner.clinic_package_active_count = len(
                allocations.filtered(lambda allocation: allocation.state in ("active", "paused"))
            )
            partner.clinic_package_remaining_value = sum(allocations.mapped("remaining_value"))

    def action_view_clinic_packages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Packages"),
            "res_model": "clinic.package.allocation",
            "view_mode": "list,form",
            "domain": [("partner_id", "child_of", self.commercial_partner_id.id)],
            "context": {"default_partner_id": self.id},
        }
