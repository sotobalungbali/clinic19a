from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicFeedbackCompanyMixin(models.AbstractModel):
    """Shared company/branch boundary for Feedback-owned documents."""

    _name = "clinic.feedback.company.mixin"
    _description = "Clinic Feedback Company and Branch Mixin"

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
        default=lambda self: self._default_feedback_branch(),
        index=True,
    )

    def _default_feedback_branch(self):
        user = self.env.user
        if "working_branch_id" in user._fields and user.working_branch_id:
            return user.working_branch_id
        return False

    def _feedback_require_group(self, xmlid, message=None):
        # Scheduled automation can run in superuser mode, while normal users
        # still require the explicit Feedback privilege.
        if self.env.su:
            return True
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                message or _("You do not have permission for this Feedback operation.")
            )
        return True

    @api.constrains("company_id", "branch_id")
    def _check_feedback_branch_company(self):
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(
                    _("Feedback Branch must belong to the selected company.")
                )
