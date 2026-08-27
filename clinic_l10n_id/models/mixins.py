from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicL10nIdCompanyMixin(models.AbstractModel):
    """Shared company/branch scope for ClinicOne Indonesia localization records."""

    _name = "clinic.l10n.id.company.mixin"
    _description = "Clinic Indonesia Company and Branch Mixin"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self._default_l10n_branch(),
        index=True,
    )

    @api.model
    def _default_l10n_branch(self):
        user = self.env.user
        if "working_branch_id" in user._fields and user.working_branch_id:
            return user.working_branch_id
        if "default_branch_id" in self.env.company._fields:
            return self.env.company.default_branch_id
        return False

    @api.constrains("company_id", "branch_id")
    def _check_branch_company(self):
        # Backend validation is mandatory because form domains are not a security boundary.
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(_("The selected branch must belong to the same company."))

    # Shared permission helper keeps backend authorization explicit and reusable across localization workflows.
    def _l10n_require_group(self, xmlid, message=None):
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                message or _("You do not have permission for this Indonesia localization operation.")
            )

