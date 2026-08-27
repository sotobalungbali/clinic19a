from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company-level Clinic eCommerce policies without redefining source workflows."""

    _inherit = "res.company"

    clinic_ecommerce_default_website_id = fields.Many2one(
        "website",
        string="Default Clinic eCommerce Website",
        ondelete="set null",
    )
    clinic_ecommerce_fulfillment_trigger = fields.Selection(
        [
            ("manual", "Manual Operator Processing"),
            ("order_confirmed", "Sales Order Confirmed"),
            ("payment_done", "Online Payment Done"),
        ],
        default="payment_done",
        required=True,
        string="Clinic Fulfillment Trigger",
    )
    clinic_ecommerce_allow_guest = fields.Boolean(
        string="Allow Guest Clinic Purchases",
        default=False,
        help="Individual Catalog Items can still require login/patient identification.",
    )
    clinic_ecommerce_require_terms = fields.Boolean(
        string="Require Clinic Terms",
        default=True,
    )
    clinic_ecommerce_single_branch_cart = fields.Boolean(
        string="Single Branch per Clinic Cart",
        default=True,
    )
    clinic_ecommerce_auto_activate_package = fields.Boolean(
        string="Activate Package Allocation After Fulfillment",
        default=True,
    )
    clinic_ecommerce_auto_activate_membership = fields.Boolean(
        string="Attempt Membership Activation After Fulfillment",
        default=False,
        help=(
            "Disabled by default because clinic_membership can require a paid Membership invoice. "
            "When enabled, eCommerce reuses a paid Odoo Sale invoice if available and never creates a duplicate invoice."
        ),
    )

    @api.constrains("clinic_ecommerce_default_website_id")
    # Company/Website consistency is backend-enforced and not delegated to a form domain.
    def _check_clinic_ecommerce_website(self):
        for company in self:
            if (
                company.clinic_ecommerce_default_website_id
                and company.clinic_ecommerce_default_website_id.company_id
                != company
            ):
                raise ValidationError(
                    _("Default Clinic eCommerce Website must belong to this company.")
                )

    def action_open_clinic_ecommerce_catalog(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic eCommerce Catalog"),
            "res_model": "clinic.ecommerce.catalog.item",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.id)],
            "context": {"default_company_id": self.id},
        }


class ResConfigSettings(models.TransientModel):
    """Expose Clinic eCommerce governance in stable Odoo Settings."""

    _inherit = "res.config.settings"

    clinic_ecommerce_default_website_id = fields.Many2one(
        related="company_id.clinic_ecommerce_default_website_id",
        readonly=False,
    )
    clinic_ecommerce_fulfillment_trigger = fields.Selection(
        related="company_id.clinic_ecommerce_fulfillment_trigger",
        readonly=False,
    )
    clinic_ecommerce_allow_guest = fields.Boolean(
        related="company_id.clinic_ecommerce_allow_guest",
        readonly=False,
    )
    clinic_ecommerce_require_terms = fields.Boolean(
        related="company_id.clinic_ecommerce_require_terms",
        readonly=False,
    )
    clinic_ecommerce_single_branch_cart = fields.Boolean(
        related="company_id.clinic_ecommerce_single_branch_cart",
        readonly=False,
    )
    clinic_ecommerce_auto_activate_package = fields.Boolean(
        related="company_id.clinic_ecommerce_auto_activate_package",
        readonly=False,
    )
    clinic_ecommerce_auto_activate_membership = fields.Boolean(
        related="company_id.clinic_ecommerce_auto_activate_membership",
        readonly=False,
    )

    def action_open_clinic_ecommerce_catalog(self):
        self.ensure_one()
        return self.company_id.action_open_clinic_ecommerce_catalog()
