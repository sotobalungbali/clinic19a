
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Treatment Session configuration through Odoo-native config parameters."""

    _inherit = "res.config.settings"

    session_reminder_offset_hours = fields.Float(config_parameter="clinic_treatment_session.reminder_offset_hours", default=24.0)
    session_auto_no_show_enabled = fields.Boolean(config_parameter="clinic_treatment_session.auto_no_show_enabled", default=False)
    session_auto_no_show_hours = fields.Float(config_parameter="clinic_treatment_session.auto_no_show_hours", default=2.0)
    session_location_src_id = fields.Many2one("stock.location", config_parameter="clinic_treatment_session.location_src_id")
    session_location_dest_id = fields.Many2one("stock.location", config_parameter="clinic_treatment_session.location_dest_id")
    session_auto_create_billing = fields.Boolean(config_parameter="clinic_treatment_session.auto_create_billing", default=False)
    session_billing_mode = fields.Selection([
        ("none", "No Automatic Billing"), ("clinic_billing", "Clinic Billing"),
        ("account_invoice", "Accounting Invoice"),
    ], config_parameter="clinic_treatment_session.billing_mode", default="clinic_billing")
    session_package_auto_deduct = fields.Boolean(config_parameter="clinic_treatment_session.package_auto_deduct", default=True)
    session_membership_auto_apply = fields.Boolean(config_parameter="clinic_treatment_session.membership_auto_apply", default=True)
    session_wallet_auto_consume = fields.Boolean(config_parameter="clinic_treatment_session.wallet_auto_consume", default=True)
