from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company Dashboard defaults; KPI semantics remain owned by clinic_reports."""

    _inherit = "res.company"

    clinic_dashboard_default_board_id = fields.Many2one(
        "clinic.dashboard.board",
        string="Default Clinic Dashboard",
        ondelete="set null",
        help="Company default Board; the Settings view applies the current-company domain.",
    )
    clinic_dashboard_snapshot_retention_days = fields.Integer(
        string="Dashboard Snapshot Active Retention (Days)",
        default=365,
        help=(
            "Ready snapshots older than this threshold are archived, never "
            "deleted, by Dashboard maintenance."
        ),
    )

    @api.constrains(
        "clinic_dashboard_default_board_id",
        "clinic_dashboard_snapshot_retention_days",
    )
    def _check_dashboard_settings(self):
        for company in self:
            if (
                company.clinic_dashboard_default_board_id
                and company.clinic_dashboard_default_board_id.company_id != company
            ):
                raise ValidationError(
                    _("Default Dashboard must belong to this company.")
                )
            if company.clinic_dashboard_snapshot_retention_days < 30:
                raise ValidationError(
                    _("Dashboard Snapshot retention must be at least 30 days.")
                )

    # Company setup invokes the same idempotent blueprint seeding used by the post-init hook.
    def action_ensure_clinic_dashboards(self):
        for company in self:
            self.env["clinic.dashboard.board"]._ensure_default_boards(company)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Clinic Dashboards"),
                "message": _("Default Dashboard Boards and Widgets are ready."),
                "type": "success",
                "sticky": False,
            },
        }


class ResConfigSettings(models.TransientModel):
    """Expose company Dashboard governance through stable Odoo Settings."""

    _inherit = "res.config.settings"

    clinic_dashboard_default_board_id = fields.Many2one(
        related="company_id.clinic_dashboard_default_board_id",
        readonly=False,
    )
    clinic_dashboard_snapshot_retention_days = fields.Integer(
        related="company_id.clinic_dashboard_snapshot_retention_days",
        readonly=False,
    )

    def action_ensure_clinic_dashboards(self):
        self.ensure_one()
        return self.company_id.action_ensure_clinic_dashboards()
