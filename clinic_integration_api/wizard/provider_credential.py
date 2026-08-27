# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ClinicApiProviderCredentialWizard(models.TransientModel):
    _name = "clinic.api.provider.credential.wizard"
    _description = "Set Clinic Integration Provider Credential"
    _transient_max_hours = 0.10

    provider_id = fields.Many2one("clinic.api.provider", required=True, ondelete="cascade")
    secret = fields.Char(required=True)

    def action_save(self):
        self.ensure_one()
        self.provider_id.set_outbound_secret(self.secret)
        self.secret = False
        return {"type": "ir.actions.act_window_close"}
