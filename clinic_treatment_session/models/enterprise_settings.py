
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettingsTreatmentSessionEnterprise(models.TransientModel):
    """Additional overlap-safety configuration."""

    _inherit = "res.config.settings"

    session_prevent_doctor_overlap = fields.Boolean(
        config_parameter="clinic_treatment_session.prevent_doctor_overlap",
        default=True,
    )
    session_prevent_room_overlap = fields.Boolean(
        config_parameter="clinic_treatment_session.prevent_room_overlap",
        default=True,
    )
