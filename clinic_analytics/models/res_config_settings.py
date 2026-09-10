# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_analytics_auto_generate_insights = fields.Boolean(
        string="Automatically Generate Insights",
        config_parameter="clinic.analytics.auto_generate_insights",
        default=True,
    )
    clinic_analytics_publish_integration_events = fields.Boolean(
        string="Publish Analytics Integration Events",
        config_parameter="clinic.analytics.publish_integration_events",
        default=False,
    )
    clinic_analytics_default_history_periods = fields.Integer(
        string="Default Forecast History Periods",
        config_parameter="clinic.analytics.default_history_periods",
        default=12,
    )
    clinic_analytics_default_horizon_periods = fields.Integer(
        string="Default Forecast Horizon Periods",
        config_parameter="clinic.analytics.default_horizon_periods",
        default=3,
    )

