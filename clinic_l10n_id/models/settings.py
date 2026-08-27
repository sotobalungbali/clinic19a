from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company-scoped ClinicOne Indonesia localization settings."""

    _inherit = "res.company"

    # Company settings point only to a ClinicOne governance profile; native localization configuration remains in Odoo.
    clinic_l10n_id_profile_id = fields.Many2one(
        "clinic.l10n.id.tax.profile",
        string="Clinic Indonesia Tax Profile",
        check_company=True,
    )
    clinic_l10n_id_auto_monthly_tax_report = fields.Boolean(
        string="Auto-Generate Prior-Month PPN Report",
        default=False,
    )

    @api.constrains("clinic_l10n_id_profile_id")
    def _check_clinic_l10n_id_profile_company(self):
        for company in self:
            profile = company.clinic_l10n_id_profile_id
            if profile and profile.company_id != company:
                raise ValidationError(_("Clinic Indonesia Tax Profile must belong to this company."))


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_l10n_id_profile_id = fields.Many2one(
        related="company_id.clinic_l10n_id_profile_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('state', 'in', ('validated', 'active'))]",
    )
    clinic_l10n_id_auto_monthly_tax_report = fields.Boolean(
        related="company_id.clinic_l10n_id_auto_monthly_tax_report",
        readonly=False,
    )

