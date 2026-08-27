from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# Company settings govern Insurance behavior without overriding Billing or Accounting configuration.
class ResCompany(models.Model):
    """Company-scoped Insurance authorization and claim governance."""

    _inherit = "res.company"

    clinic_insurance_default_plan_id = fields.Many2one(
        "clinic.insurance.plan",
        string="Default Insurance Plan",
        check_company=True,
    )
    clinic_insurance_require_eligibility_before_authorization = fields.Boolean(
        string="Require Current Eligibility Before Authorization",
        default=True,
    )
    clinic_insurance_default_authorization_valid_days = fields.Integer(
        string="Default Authorization Validity (Days)",
        default=30,
    )
    clinic_insurance_claim_require_authorization = fields.Boolean(
        string="Require Authorization for Policy Claims",
        default=True,
        help="When the Policy itself requires authorization, Claim submission is blocked without a valid approval.",
    )
    clinic_insurance_auto_link_policy_to_billing = fields.Boolean(
        string="Auto-Link Active Policy to Billing",
        default=True,
    )

    @api.constrains(
        "clinic_insurance_default_plan_id",
        "clinic_insurance_default_authorization_valid_days",
    )
    def _check_clinic_insurance_settings(self):
        for company in self:
            plan = company.clinic_insurance_default_plan_id
            if plan and plan.company_id != company:
                raise ValidationError(_("Default Insurance Plan must belong to this company."))
            if company.clinic_insurance_default_authorization_valid_days < 0:
                raise ValidationError(_("Default Authorization Validity cannot be negative."))


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_insurance_default_plan_id = fields.Many2one(
        related="company_id.clinic_insurance_default_plan_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    clinic_insurance_require_eligibility_before_authorization = fields.Boolean(
        related="company_id.clinic_insurance_require_eligibility_before_authorization",
        readonly=False,
    )
    clinic_insurance_default_authorization_valid_days = fields.Integer(
        related="company_id.clinic_insurance_default_authorization_valid_days",
        readonly=False,
    )
    clinic_insurance_claim_require_authorization = fields.Boolean(
        related="company_id.clinic_insurance_claim_require_authorization",
        readonly=False,
    )
    clinic_insurance_auto_link_policy_to_billing = fields.Boolean(
        related="company_id.clinic_insurance_auto_link_policy_to_billing",
        readonly=False,
    )

