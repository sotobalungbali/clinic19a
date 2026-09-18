from odoo import fields, models, _


class ClinicBranch(models.Model):
    """Reporting drill-down on Branch without inheriting fragile upstream views."""

    _inherit = "clinic.branch"

    report_run_ids = fields.One2many(
        "clinic.report.run",
        "branch_id",
        string="Report Runs",
    )
    report_run_count = fields.Integer(compute="_compute_report_run_count")

    def _compute_report_run_count(self):
        for branch in self:
            branch.report_run_count = len(branch.report_run_ids)

    # Branch integration is navigation-only; Clinic Branch remains the owner of branch policy and master data.
    def action_open_report_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Branch Report Runs"),
            "res_model": "clinic.report.run",
            "view_mode": "list,form",
            "domain": [("branch_id", "=", self.id)],
            "context": {
                "default_company_id": self.company_id.id,
                "default_branch_id": self.id,
            },
        }


class ResCompany(models.Model):
    """Company-level Report Run navigation, additive to Settings fields."""

    _inherit = "res.company"

    clinic_report_run_ids = fields.One2many(
        "clinic.report.run",
        "company_id",
        string="Clinic Report Runs",
    )
    clinic_report_run_count = fields.Integer(
        compute="_compute_clinic_report_run_count"
    )

    def _compute_clinic_report_run_count(self):
        for company in self:
            company.clinic_report_run_count = len(company.clinic_report_run_ids)

    # Company smart navigation remains additive and does not redefine accounting/report source ownership.
    def action_open_clinic_report_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Company Report Runs"),
            "res_model": "clinic.report.run",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.id)],
            "context": {"default_company_id": self.id},
        }

