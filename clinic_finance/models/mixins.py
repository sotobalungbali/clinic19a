from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicFinanceCompanyMixin(models.AbstractModel):
    """Shared company/branch guard used by Finance operational documents."""

    _name = "clinic.finance.company.mixin"
    _description = "Clinic Finance Company and Branch Mixin"

    # Company is mandatory on every owned finance document so record rules and posting stay aligned.
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self._default_finance_branch(),
        index=True,
    )

    @api.model
    def _default_finance_branch(self):
        user = self.env.user
        if "working_branch_id" in user._fields and user.working_branch_id:
            return user.working_branch_id
        if "default_branch_id" in self.env.company._fields:
            return self.env.company.default_branch_id
        return False

    # Branch validation is backend-enforced; UI domains are only a convenience layer.
    @api.constrains("company_id", "branch_id")
    def _check_finance_branch_company(self):
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(_("The selected branch must belong to the document company."))

    def _finance_require_group(self, xmlid, message=None):
        if not self.env.user.has_group(xmlid):
            raise AccessError(message or _("You do not have permission for this Finance operation."))
