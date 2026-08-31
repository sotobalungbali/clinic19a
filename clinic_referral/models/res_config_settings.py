# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_referral_default_valid_days = fields.Integer(
        related="company_id.clinic_referral_default_valid_days",
        readonly=False,
    )
    clinic_referral_require_source = fields.Boolean(
        related="company_id.clinic_referral_require_source",
        readonly=False,
    )
    clinic_referral_require_program_for_reward = fields.Boolean(
        related="company_id.clinic_referral_require_program_for_reward",
        readonly=False,
    )

