
# -*- coding: utf-8 -*-
"""Governed package ownership transfer wizard."""

from odoo import fields, models, _
from odoo.exceptions import UserError


class ClinicPackageTransferWizard(models.TransientModel):
    _name = "clinic.package.transfer.wizard"
    _description = "Transfer Clinic Package"

    allocation_id = fields.Many2one("clinic.package.allocation", required=True, check_company=True)
    current_patient_id = fields.Many2one(related="allocation_id.patient_id", readonly=True)
    target_patient_id = fields.Many2one("clinic.patient", required=True, check_company=True)
    transfer_fee = fields.Monetary(compute="_compute_transfer_fee", currency_field="currency_id")
    currency_id = fields.Many2one(related="allocation_id.currency_id", readonly=True)
    reason = fields.Text(required=True)

    def _compute_transfer_fee(self):
        for wizard in self:
            policy = wizard.allocation_id.package_id.policy_id
            wizard.transfer_fee = policy.compute_transfer_fee(wizard.allocation_id) if policy else 0.0

    def action_transfer(self):
        self.ensure_one()
        if self.target_patient_id == self.current_patient_id:
            raise UserError(_("Choose a different target patient."))
        self.allocation_id._transfer_to_patient(self.target_patient_id, note=self.reason)
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocation"),
            "res_model": "clinic.package.allocation",
            "view_mode": "form",
            "res_id": self.allocation_id.id,
        }
