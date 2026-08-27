from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company-level Quality governance defaults."""

    _inherit = "res.company"

    clinic_quality_default_approver_id = fields.Many2one(
        "res.users",
        string="Default Quality Approver",
        help=(
            "Optional default reviewer/approver used for Quality Checks "
            "and SOP governance."
        ),
    )
    clinic_quality_default_review_months = fields.Integer(
        string="Default SOP Review Months",
        default=12,
    )
    clinic_quality_default_pass_threshold = fields.Float(
        string="Default Compliance Threshold (%)",
        default=90.0,
    )
    clinic_quality_require_incident_critical = fields.Boolean(
        string="Require Incident for Critical Quality Failure",
        default=True,
        help=(
            "When enabled, a Quality Check with a failed critical control "
            "cannot be closed until that control has an Incident case."
        ),
    )

    @api.constrains(
        "clinic_quality_default_approver_id",
        "clinic_quality_default_review_months",
        "clinic_quality_default_pass_threshold",
    )
    def _check_quality_defaults(self):
        for company in self:
            approver = company.clinic_quality_default_approver_id
            if approver and company not in approver.company_ids:
                raise ValidationError(
                    _(
                        "Default Quality Approver must have access "
                        "to this company."
                    )
                )
            if approver and not approver.has_group(
                "clinic_quality.group_quality_approver"
            ):
                raise ValidationError(
                    _(
                        "Default Quality Approver must belong to the "
                        "Quality Approver role."
                    )
                )

            if not 1 <= company.clinic_quality_default_review_months <= 120:
                raise ValidationError(
                    _("Default SOP Review Months must be between 1 and 120.")
                )

            if not 0.0 <= company.clinic_quality_default_pass_threshold <= 100.0:
                raise ValidationError(
                    _("Default Compliance Threshold must be between 0 and 100.")
                )


class ResUsers(models.Model):
    """Quality-specific branch access bridge used by record rules."""

    _inherit = "res.users"

    clinic_quality_access_branch_ids = fields.Many2many(
        "clinic.branch",
        compute="_compute_clinic_quality_access_branch_ids",
        string="Quality Access Branches",
    )

    @api.depends("allowed_branch_ids", "company_ids")
    def _compute_clinic_quality_access_branch_ids(self):
        Branch = self.env["clinic.branch"].sudo()

        for user in self:
            allowed = user.sudo().allowed_branch_ids.filtered(
                lambda branch: branch.company_id in user.company_ids
            )
            if not allowed:
                allowed = Branch.search([
                    ("company_id", "in", user.company_ids.ids),
                ])
            user.clinic_quality_access_branch_ids = allowed


class ResConfigSettings(models.TransientModel):
    """Stable native Odoo Settings integration."""

    _inherit = "res.config.settings"

    clinic_quality_default_approver_id = fields.Many2one(
        related="company_id.clinic_quality_default_approver_id",
        readonly=False,
    )
    clinic_quality_default_review_months = fields.Integer(
        related="company_id.clinic_quality_default_review_months",
        readonly=False,
    )
    clinic_quality_default_pass_threshold = fields.Float(
        related="company_id.clinic_quality_default_pass_threshold",
        readonly=False,
    )
    clinic_quality_require_incident_critical = fields.Boolean(
        related="company_id.clinic_quality_require_incident_critical",
        readonly=False,
    )
