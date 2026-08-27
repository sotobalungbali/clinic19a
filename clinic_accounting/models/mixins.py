from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicAccountingCompanyMixin(models.AbstractModel):
    """Shared company/branch scope and permission helpers for Accounting-owned records."""

    _name = "clinic.accounting.company.mixin"
    _description = "Clinic Accounting Company and Branch Mixin"

    # Company is explicit on every persistent Accounting document so company
    # record rules and native Odoo accounting scope remain aligned.
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
        default=lambda self: self._default_accounting_branch(),
        index=True,
    )

    @api.model
    def _default_accounting_branch(self):
        user = self.env.user
        if "working_branch_id" in user._fields and user.working_branch_id:
            return user.working_branch_id
        if "default_branch_id" in self.env.company._fields:
            return self.env.company.default_branch_id
        return False

    @api.constrains("company_id", "branch_id")
    def _check_accounting_branch_company(self):
        # UI domains are convenience only; backend validation prevents
        # cross-company branch assignment through RPC/import.
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(
                    _("The selected branch must belong to the Accounting document company.")
                )

    def _accounting_require_group(self, xmlid, message=None):
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                message or _("You do not have permission for this Accounting operation.")
            )
