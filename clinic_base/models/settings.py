
# -*- coding: utf-8 -*-
# Komentar (ID): Pengaturan global ClinicOne via res.config.settings
from odoo import api, fields, models, _

class ClinicBaseSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # --- Feature flags (boolean) ---
    clinic_feature_new_booking = fields.Boolean(
        string="Enable New Booking Flow",
        help="Toggle the new booking workflow across ClinicOne modules.",
        config_parameter="clinic.feature.new_booking",
    )
    clinic_feature_audit_enabled = fields.Boolean(
        string="Enable Audit Bridge",
        help="Enable audit bridge (fallback to chatter if clinic_audit is not installed).",
        config_parameter="clinic.audit.enabled",
        default=True,
    )

    # --- Sequence behavior ---
    clinic_seq_per_company = fields.Boolean(
        string="Sequences per Company",
        help="Generate distinct sequences per company where applicable.",
        config_parameter="clinic.seq.per_company",
        default=True,
    )

    # --- Phone normalization & dedup ---
    clinic_phone_unique = fields.Boolean(
        string="Unique Normalized Phone",
        help="Enforce uniqueness on normalized phone in models that opt-in.",
        config_parameter="clinic.phone.unique",
    )

    # --- Interop / API ---
    clinic_api_timeout = fields.Float(
        string="API Timeout (seconds)",
        help="Default request timeout used by interop helpers.",
        config_parameter="clinic.api.timeout",
        default=3.0,
    )

    # --- UI/Display ---
    clinic_name_use_display_ref = fields.Boolean(
        string="Use [CODE] Name Display",
        help="Show records using '[CODE] Name' pattern where available.",
        config_parameter="clinic.name.use_display_ref",
        default=True,
    )

    # Catatan:
    # Menggunakan config_parameter di field -> Odoo otomatis handle get/set
    # sehingga kita tidak perlu override get_values/set_values.

