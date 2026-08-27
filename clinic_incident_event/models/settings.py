from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company defaults for Incident/Event management."""

    _inherit = "res.company"

    clinic_incident_default_case_owner_id = fields.Many2one(
        "res.users",
        string="Default Incident Case Owner",
        help=(
            "Optional default owner used when an Incident is created "
            "without an explicit Case Owner."
        ),
    )
    clinic_incident_default_capa_days = fields.Integer(
        string="Default CAPA Due Days",
        default=7,
    )
    clinic_incident_staff_kpi_enabled = fields.Boolean(
        string="Include Incidents in Staff KPI",
        default=True,
    )

    @api.constrains(
        "clinic_incident_default_case_owner_id",
        "clinic_incident_default_capa_days",
    )
    def _check_incident_defaults(self):
        for company in self:
            if (
                company.clinic_incident_default_case_owner_id
                and company not in
                company.clinic_incident_default_case_owner_id.company_ids
            ):
                raise ValidationError(
                    _(
                        "Default Incident Case Owner must have access "
                        "to this company."
                    )
                )

            if not 1 <= company.clinic_incident_default_capa_days <= 365:
                raise ValidationError(
                    _(
                        "Default CAPA Due Days must be between "
                        "1 and 365."
                    )
                )


class ResUsers(models.Model):
    """Branch access bridge used by Incident record rules."""

    _inherit = "res.users"

    clinic_incident_access_branch_ids = fields.Many2many(
        "clinic.branch",
        compute="_compute_clinic_incident_access_branch_ids",
        string="Incident Access Branches",
    )

    @api.depends("allowed_branch_ids", "company_ids")
    def _compute_clinic_incident_access_branch_ids(self):
        Branch = self.env["clinic.branch"].sudo()
        for user in self:
            allowed = user.sudo().allowed_branch_ids.filtered(
                lambda branch:
                branch.company_id in user.company_ids
            )
            if not allowed:
                allowed = Branch.search([
                    ("company_id", "in", user.company_ids.ids),
                ])
            user.clinic_incident_access_branch_ids = allowed


class ResConfigSettings(models.TransientModel):
    """Stable native Odoo Settings integration."""

    _inherit = "res.config.settings"

    clinic_incident_default_case_owner_id = fields.Many2one(
        related="company_id.clinic_incident_default_case_owner_id",
        readonly=False,
    )
    clinic_incident_default_capa_days = fields.Integer(
        related="company_id.clinic_incident_default_capa_days",
        readonly=False,
    )
    clinic_incident_staff_kpi_enabled = fields.Boolean(
        related="company_id.clinic_incident_staff_kpi_enabled",
        readonly=False,
    )
