from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company policy for Telemedicine and secure patient communication."""

    _inherit = "res.company"

    clinic_telemedicine_provider_mode = fields.Selection(
        [
            ("manual_url", "Manual HTTPS Meeting URL"),
            ("provider_hook", "Provider Extension Hook"),
        ],
        string="Default Telemedicine Provider Mode",
        default="manual_url",
        required=True,
    )
    clinic_telemedicine_early_join_minutes = fields.Integer(
        string="Patient Early Join Window (Minutes)",
        default=15,
    )
    clinic_telemedicine_late_join_minutes = fields.Integer(
        string="Patient Late Join Window (Minutes)",
        default=60,
    )
    clinic_telemedicine_require_signed_consent = fields.Boolean(
        string="Require Signed Consent Before Ready",
        default=False,
        help=(
            "When enabled, a linked clinic.consent.form must be Signed before "
            "a Telemedicine Session can become Ready."
        ),
    )
    clinic_telemedicine_auto_create_thread = fields.Boolean(
        string="Auto-create Secure Thread on Scheduling",
        default=True,
    )
    clinic_telemedicine_allow_patient_new_threads = fields.Boolean(
        string="Allow Patients to Start Secure Threads",
        default=True,
    )
    clinic_telemedicine_max_open_threads = fields.Integer(
        string="Maximum Open Patient-Initiated Threads",
        default=5,
    )
    clinic_telemedicine_max_message_chars = fields.Integer(
        string="Maximum Secure Message Characters",
        default=5000,
    )
    clinic_telemedicine_max_file_mb = fields.Integer(
        string="Maximum Secure File Size (MB)",
        default=10,
    )

    @api.constrains(
        "clinic_telemedicine_early_join_minutes",
        "clinic_telemedicine_late_join_minutes",
        "clinic_telemedicine_max_open_threads",
        "clinic_telemedicine_max_message_chars",
        "clinic_telemedicine_max_file_mb",
    )
    def _check_telemedicine_settings(self):
        for company in self:
            if not 0 <= company.clinic_telemedicine_early_join_minutes <= 180:
                raise ValidationError(
                    _("Early Join Window must be between 0 and 180 minutes.")
                )
            if not 0 <= company.clinic_telemedicine_late_join_minutes <= 360:
                raise ValidationError(
                    _("Late Join Window must be between 0 and 360 minutes.")
                )
            if not 1 <= company.clinic_telemedicine_max_open_threads <= 50:
                raise ValidationError(
                    _("Maximum Open Threads must be between 1 and 50.")
                )
            if not 250 <= company.clinic_telemedicine_max_message_chars <= 20000:
                raise ValidationError(
                    _("Maximum Message Characters must be between 250 and 20,000.")
                )
            if not 1 <= company.clinic_telemedicine_max_file_mb <= 25:
                raise ValidationError(
                    _("Maximum Secure File Size must be between 1 and 25 MB.")
                )


class ResConfigSettings(models.TransientModel):
    """Expose Telemedicine governance in stable Odoo Settings architecture."""

    _inherit = "res.config.settings"

    clinic_telemedicine_provider_mode = fields.Selection(
        related="company_id.clinic_telemedicine_provider_mode",
        readonly=False,
    )
    clinic_telemedicine_early_join_minutes = fields.Integer(
        related="company_id.clinic_telemedicine_early_join_minutes",
        readonly=False,
    )
    clinic_telemedicine_late_join_minutes = fields.Integer(
        related="company_id.clinic_telemedicine_late_join_minutes",
        readonly=False,
    )
    clinic_telemedicine_require_signed_consent = fields.Boolean(
        related="company_id.clinic_telemedicine_require_signed_consent",
        readonly=False,
    )
    clinic_telemedicine_auto_create_thread = fields.Boolean(
        related="company_id.clinic_telemedicine_auto_create_thread",
        readonly=False,
    )
    clinic_telemedicine_allow_patient_new_threads = fields.Boolean(
        related="company_id.clinic_telemedicine_allow_patient_new_threads",
        readonly=False,
    )
    clinic_telemedicine_max_open_threads = fields.Integer(
        related="company_id.clinic_telemedicine_max_open_threads",
        readonly=False,
    )
    clinic_telemedicine_max_message_chars = fields.Integer(
        related="company_id.clinic_telemedicine_max_message_chars",
        readonly=False,
    )
    clinic_telemedicine_max_file_mb = fields.Integer(
        related="company_id.clinic_telemedicine_max_file_mb",
        readonly=False,
    )

