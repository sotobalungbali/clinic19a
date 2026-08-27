from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicInsuranceCompanyMixin(models.AbstractModel):
    """Shared company/branch boundary for insurance-owned business documents."""

    _name = "clinic.insurance.company.mixin"
    _description = "Clinic Insurance Company and Branch Mixin"

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
        default=lambda self: self._default_insurance_branch(),
        index=True,
    )

    @api.model
    def _default_insurance_branch(self):
        user = self.env.user
        if "working_branch_id" in user._fields and user.working_branch_id:
            return user.working_branch_id
        if "default_branch_id" in self.env.company._fields:
            return self.env.company.default_branch_id
        return False

    @api.constrains("company_id", "branch_id")
    def _check_insurance_branch_company(self):
        # UI domains are convenience only; imports/RPC must be protected too.
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(_("Insurance Branch must belong to the same company."))

    def _insurance_require_group(self, xmlid, message=None):
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                message or _("You do not have permission for this insurance operation.")
            )

