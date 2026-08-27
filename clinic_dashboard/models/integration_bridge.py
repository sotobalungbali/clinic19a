from odoo import fields, models, _


class ClinicBranch(models.Model):
    """Branch-to-Dashboard navigation; Clinic Branch remains the master-data owner."""

    _inherit = "clinic.branch"

    dashboard_snapshot_ids = fields.One2many(
        "clinic.dashboard.snapshot",
        "branch_id",
        string="Dashboard Snapshots",
    )
    dashboard_snapshot_count = fields.Integer(
        compute="_compute_dashboard_snapshot_count"
    )

    def _compute_dashboard_snapshot_count(self):
        for branch in self:
            branch.dashboard_snapshot_count = len(branch.dashboard_snapshot_ids)

    # Branch integration is navigation-only; clinic_branch remains owner of Branch master data and policy.
    def action_open_dashboard_snapshots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Branch Dashboard Snapshots"),
            "res_model": "clinic.dashboard.snapshot",
            "view_mode": "kanban,list,form",
            "domain": [("branch_id", "=", self.id)],
            "context": {"search_default_ready": 1},
        }


class ResCompany(models.Model):
    """Company dashboard navigation, additive to Dashboard Settings and source ownership."""

    _inherit = "res.company"

    clinic_dashboard_board_ids = fields.One2many(
        "clinic.dashboard.board",
        "company_id",
        string="Clinic Dashboards",
    )
    clinic_dashboard_board_count = fields.Integer(
        compute="_compute_clinic_dashboard_board_count"
    )

    def _compute_clinic_dashboard_board_count(self):
        for company in self:
            company.clinic_dashboard_board_count = len(
                company.clinic_dashboard_board_ids
            )

    def action_open_clinic_dashboard_boards(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Dashboard Boards"),
            "res_model": "clinic.dashboard.board",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.id)],
            "context": {"default_company_id": self.id},
        }


class ClinicReportRun(models.Model):
    """Expose downstream Dashboard provenance without changing Report Run ownership or lifecycle."""

    _inherit = "clinic.report.run"

    dashboard_line_ids = fields.One2many(
        "clinic.dashboard.snapshot.line",
        "report_run_id",
        string="Dashboard KPI Uses",
    )
    dashboard_line_count = fields.Integer(
        compute="_compute_dashboard_line_count"
    )

    def _compute_dashboard_line_count(self):
        for run in self:
            run.dashboard_line_count = len(run.dashboard_line_ids)

    # Report Run provenance is downstream-only and never changes Clinic Reports finalization semantics.
    def action_open_dashboard_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard KPI Uses"),
            "res_model": "clinic.dashboard.snapshot.line",
            "view_mode": "list,form",
            "domain": [("report_run_id", "=", self.id)],
        }
