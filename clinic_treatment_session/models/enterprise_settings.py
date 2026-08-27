# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettingsTreatmentSessionEnterprise(models.TransientModel):
    """Additive Odoo-native settings for operational safety."""

    _inherit = "res.config.settings"

    session_prevent_doctor_overlap = fields.Boolean(
        string="Prevent Clinic Doctor Overlap",
        config_parameter="clinic_treatment_session.prevent_doctor_overlap",
        default=True,
        help=(
            "Block confirmation/start when the same Clinic Doctor has another "
            "Confirmed or In Progress Treatment Session in the same period."
        ),
    )
    session_prevent_room_overlap = fields.Boolean(
        string="Prevent Room Overlap",
        config_parameter="clinic_treatment_session.prevent_room_overlap",
        default=True,
        help=(
            "Block confirmation/start when the selected room has another "
            "Confirmed or In Progress Treatment Session in the same period."
        ),
    )
