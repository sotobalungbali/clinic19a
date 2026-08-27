from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company governance for ClinicOne marketing communication."""

    _inherit = "res.company"

    clinic_marketing_require_explicit_consent = fields.Boolean(
        string="Require Explicit Marketing Opt-In",
        default=True,
        help=(
            "When enabled, Email/WhatsApp marketing requires an explicit channel "
            "opt-in in Clinic Marketing Preferences."
        ),
    )
    clinic_marketing_max_audience = fields.Integer(
        string="Maximum Campaign Audience",
        default=50000,
    )
    clinic_marketing_whatsapp_transport = fields.Selection(
        [
            ("manual", "Manual WhatsApp Handoff"),
            ("extension", "Provider Extension Hook"),
        ],
        string="WhatsApp Transport",
        default="manual",
        required=True,
        help=(
            "Manual opens wa.me links. Provider Extension Hook is reserved for "
            "a future clinic_integration_api transport override."
        ),
    )

    @api.constrains("clinic_marketing_max_audience")
    def _check_marketing_max_audience(self):
        for company in self:
            if not 100 <= company.clinic_marketing_max_audience <= 500000:
                raise ValidationError(
                    _("Maximum Campaign Audience must be between 100 and 500,000.")
                )


class ResConfigSettings(models.TransientModel):
    """Expose Clinic Marketing governance in stable Odoo Settings."""

    _inherit = "res.config.settings"

    clinic_marketing_require_explicit_consent = fields.Boolean(
        related="company_id.clinic_marketing_require_explicit_consent",
        readonly=False,
    )
    clinic_marketing_max_audience = fields.Integer(
        related="company_id.clinic_marketing_max_audience",
        readonly=False,
    )
    clinic_marketing_whatsapp_transport = fields.Selection(
        related="company_id.clinic_marketing_whatsapp_transport",
        readonly=False,
    )

