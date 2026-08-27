from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicReportGenerateWizard(models.TransientModel):
    """Human-friendly entry point for one governed Report Run."""

    _name = "clinic.report.generate.wizard"
    _description = "Generate Clinic Report"

    definition_id = fields.Many2one(
        "clinic.report.definition",
        required=True,
        domain="[('state', '=', 'active')]",
    )
    family = fields.Selection(
        related="definition_id.family",
        readonly=True,
    )
    report_key = fields.Selection(
        related="definition_id.report_key",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('company_id', '=', company_id)]",
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    include_details = fields.Boolean(default=True)
    detail_limit = fields.Integer(default=500)

    @api.model
    def default_get(self, field_list):
        vals = super().default_get(field_list)
        company = self.env["res.company"].browse(
            vals.get("company_id")
        ) or self.env.company
        date_to = fields.Date.context_today(self)
        window = max(company.clinic_reports_default_window_days or 30, 1)

        vals.setdefault("date_to", date_to)
        vals.setdefault("date_from", date_to - timedelta(days=window - 1))
        vals.setdefault(
            "detail_limit",
            company.clinic_reports_default_detail_limit or 500,
        )
        return vals

    @api.onchange("definition_id")
    def _onchange_definition(self):
        if self.definition_id:
            self.include_details = self.definition_id.include_details_by_default
            self.detail_limit = self.definition_id.default_detail_limit
            if not self.definition_id.allow_branch_filter:
                self.branch_id = False

    @api.constrains("date_from", "date_to", "detail_limit")
    def _check_scope(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("Start Date cannot be after End Date."))
            if not 1 <= wizard.detail_limit <= 10000:
                raise ValidationError(
                    _("Detail Limit must be between 1 and 10,000 rows.")
                )

    # The wizard creates a normal Report Run, then delegates all KPI logic to the governed engine dispatch.
    def action_generate(self):
        self.ensure_one()
        if not self.env.user.has_group("clinic_reports.group_reports_analyst"):
            raise UserError(_("Only a Reports Analyst can generate reports."))
        if self.definition_id.state != "active":
            raise UserError(_("Select an Active Report Definition."))

        run = self.env["clinic.report.run"].create({
            "definition_id": self.definition_id.id,
            "company_id": self.company_id.id,
            "branch_id": self.branch_id.id or False,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "include_details": self.include_details,
            "detail_limit": self.detail_limit,
        })
        run.action_generate()

        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Report"),
            "res_model": "clinic.report.run",
            "view_mode": "form",
            "res_id": run.id,
        }
