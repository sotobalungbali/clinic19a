from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicPostcareCompanyMixin(models.AbstractModel):
    """Shared company / branch guard for owned post-care documents."""

    _name = "clinic.postcare.company.mixin"
    _description = "Clinic Post-Care Company and Branch Mixin"

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
        default=lambda self: self._default_postcare_branch(),
        index=True,
    )

    @api.model
    def _default_postcare_branch(self):
        user = self.env.user
        if "working_branch_id" in user._fields and user.working_branch_id:
            return user.working_branch_id
        if "default_branch_id" in self.env.company._fields:
            return self.env.company.default_branch_id
        return False

    @api.constrains("company_id", "branch_id")
    def _check_branch_company(self):
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(_("Post-Care Branch must belong to the selected company."))

    def _postcare_require_group(self, xmlid, message=None):
        # Scheduled housekeeping runs under superuser mode.  Business users
        # still require the explicit Post-Care privilege for the same action.
        if self.env.su:
            return True
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                message or _("You do not have permission for this Post-Care operation.")
            )
        return True
