# -*- coding: utf-8 -*-
from odoo import fields, models


class ClinicApiWebhookTokenWizard(models.TransientModel):
    _name = "clinic.api.webhook.token.wizard"
    _description = "Clinic Integration Webhook Token Reveal"
    _transient_max_hours = 0.10

    provider_id = fields.Many2one("clinic.api.provider", required=True, readonly=True)
    token = fields.Char(required=True, readonly=True, help="Copy this token now. Only its SHA-256 digest is retained after this window is closed.")
