from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company defaults for newly created Clinic Patient Portal Profiles."""

    _inherit = "res.company"

    clinic_portal_auto_profile = fields.Boolean(
        string="Auto-create & Activate Patient Portal Profile",
        default=False,
        help=(
            "Opt-in convenience policy. When enabled, an already-authorized "
            "native Odoo Portal User with an exact Patient Card may receive an "
            "Active Clinic Portal Profile on first ClinicOne portal visit."
        ),
    )
    clinic_portal_default_booking_view = fields.Boolean(
        string="Default: Show Bookings",
        default=True,
    )
    clinic_portal_default_invoice_view = fields.Boolean(
        string="Default: Show Invoices",
        default=True,
    )
    clinic_portal_default_treatment_view = fields.Boolean(
        string="Default: Show Treatment History",
        default=True,
    )
    clinic_portal_show_wallet_link = fields.Boolean(
        string="Show Wallet Shortcut",
        default=True,
    )
    clinic_portal_show_consent_link = fields.Boolean(
        string="Show Consent Shortcut",
        default=True,
    )
    clinic_portal_show_order_link = fields.Boolean(
        string="Show Orders Shortcut",
        default=True,
    )
    clinic_portal_show_shop_link = fields.Boolean(
        string="Show Clinic Shop Shortcut",
        default=True,
    )
    clinic_portal_page_size = fields.Integer(
        string="Portal Rows Per Page",
        default=20,
    )

    @api.constrains("clinic_portal_page_size")
    def _check_portal_page_size(self):
        for company in self:
            if not 5 <= company.clinic_portal_page_size <= 100:
                raise ValidationError(
                    _("Portal Rows Per Page must be between 5 and 100.")
                )


class ResConfigSettings(models.TransientModel):
    """Expose Clinic Patient Portal governance in stable Odoo Settings."""

    _inherit = "res.config.settings"

    clinic_portal_auto_profile = fields.Boolean(
        related="company_id.clinic_portal_auto_profile",
        readonly=False,
    )
    clinic_portal_default_booking_view = fields.Boolean(
        related="company_id.clinic_portal_default_booking_view",
        readonly=False,
    )
    clinic_portal_default_invoice_view = fields.Boolean(
        related="company_id.clinic_portal_default_invoice_view",
        readonly=False,
    )
    clinic_portal_default_treatment_view = fields.Boolean(
        related="company_id.clinic_portal_default_treatment_view",
        readonly=False,
    )
    clinic_portal_show_wallet_link = fields.Boolean(
        related="company_id.clinic_portal_show_wallet_link",
        readonly=False,
    )
    clinic_portal_show_consent_link = fields.Boolean(
        related="company_id.clinic_portal_show_consent_link",
        readonly=False,
    )
    clinic_portal_show_order_link = fields.Boolean(
        related="company_id.clinic_portal_show_order_link",
        readonly=False,
    )
    clinic_portal_show_shop_link = fields.Boolean(
        related="company_id.clinic_portal_show_shop_link",
        readonly=False,
    )
    clinic_portal_page_size = fields.Integer(
        related="company_id.clinic_portal_page_size",
        readonly=False,
    )
