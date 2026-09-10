from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicDashboardSnapshotLine(models.Model):
    """One immutable KPI card value captured in a Dashboard Snapshot."""

    _name = "clinic.dashboard.snapshot.line"
    _description = "Clinic Dashboard Snapshot KPI"
    _order = "snapshot_id, sequence, id"
    _check_company_auto = True

    _widget_snapshot_unique = models.Constraint(
        "UNIQUE(snapshot_id, widget_id)",
        "A Dashboard Widget can only have one KPI line per Snapshot.",
    )
    _snapshot_status_idx = models.Index("(snapshot_id, status, sequence)")
    _company_metric_idx = models.Index(
        "(company_id, metric_code, report_run_id)"
    )

    snapshot_id = fields.Many2one(
        "clinic.dashboard.snapshot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    board_id = fields.Many2one(
        related="snapshot_id.board_id",
        store=True,
        readonly=True,
        index=True,
    )
    widget_id = fields.Many2one(
        "clinic.dashboard.widget",
        required=True,
        ondelete="restrict",
        index=True,
    )
    company_id = fields.Many2one(
        related="snapshot_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="snapshot_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="snapshot_id.currency_id",
        store=True,
        readonly=True,
    )
    date_from = fields.Date(
        related="snapshot_id.date_from",
        store=True,
        readonly=True,
        index=True,
    )
    date_to = fields.Date(
        related="snapshot_id.date_to",
        store=True,
        readonly=True,
        index=True,
    )
    generated_at = fields.Datetime(
        related="snapshot_id.generated_at",
        store=True,
        readonly=True,
        index=True,
    )
    dashboard_type = fields.Selection(
        related="board_id.dashboard_type",
        store=True,
        readonly=True,
        index=True,
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    metric_code = fields.Char(required=True, index=True)
    metric_type = fields.Selection(
        [
            ("count", "Count"),
            ("amount", "Amount"),
            ("percentage", "Percentage"),
            ("duration", "Duration (Minutes)"),
            ("score", "Score"),
            ("quantity", "Quantity"),
            ("number", "Number"),
        ],
        index=True,
    )
    icon = fields.Char()
    display_style = fields.Selection(
        [
            ("kpi", "KPI Card"),
            ("progress", "Progress / Target"),
            ("trend", "Trend Card"),
        ],
    )
    column_span = fields.Selection(
        [
            ("3", "Quarter Width"),
            ("4", "One Third"),
            ("6", "Half Width"),
            ("12", "Full Width"),
        ],
        default="3",
    )

    definition_id = fields.Many2one(
        "clinic.report.definition",
        string="Report Definition",
        ondelete="restrict",
        index=True,
    )
    report_run_id = fields.Many2one(
        "clinic.report.run",
        string="Report Run",
        ondelete="restrict",
        index=True,
    )
    metric_id = fields.Many2one(
        "clinic.report.metric",
        string="Source Metric",
        ondelete="restrict",
        index=True,
    )

    value = fields.Float(default=0.0)
    display_value = fields.Char()
    previous_value = fields.Float(default=0.0)
    has_trend = fields.Boolean(default=False)
    trend_percent = fields.Float()
    trend_direction = fields.Selection(
        [
            ("none", "No Trend"),
            ("up", "Up"),
            ("down", "Down"),
            ("flat", "Flat"),
        ],
        default="none",
        index=True,
    )

    has_target = fields.Boolean(default=False)
    target_value = fields.Float(default=0.0)
    target_progress = fields.Float(default=0.0)

    status = fields.Selection(
        [
            ("normal", "On Track"),
            ("warning", "Warning"),
            ("critical", "Critical"),
            ("no_data", "No Data"),
            ("unsupported_scope", "Unsupported Scope"),
            ("error", "Error"),
        ],
        default="no_data",
        required=True,
        index=True,
    )
    status_label = fields.Char()
    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get("dashboard_generation")):
            raise AccessError(
                _("Dashboard KPI Lines can only be created by the Dashboard engine.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if not (self.env.su and self.env.context.get("dashboard_generation")):
            raise AccessError(
                _("Dashboard KPI Lines are immutable generated evidence.")
            )
        return super().write(vals)

    def unlink(self):
        if not (self.env.su and self.env.context.get("dashboard_generation")):
            raise AccessError(
                _("Dashboard KPI Lines can only be removed by controlled maintenance.")
            )
        return super().unlink()

    # Provenance drill-down opens the Reports-owned Run under the current user's ordinary access rights.
    def action_open_report_run(self):
        self.ensure_one()
        if not self.report_run_id:
            raise UserError(_("This KPI line has no source Report Run."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Report Run"),
            "res_model": "clinic.report.run",
            "view_mode": "form",
            "res_id": self.report_run_id.id,
        }

    def action_open_metric(self):
        self.ensure_one()
        if not self.metric_id:
            raise UserError(_("This KPI line has no source Report Metric."))
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "clinic.report.metric",
            "view_mode": "form",
            "res_id": self.metric_id.id,
        }

    def action_open_definition(self):
        self.ensure_one()
        if not self.definition_id:
            raise UserError(_("This KPI line has no Report Definition."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Definition"),
            "res_model": "clinic.report.definition",
            "view_mode": "form",
            "res_id": self.definition_id.id,
        }

    # Frontend formatting is prepared server-side to keep the Owl template simple and deterministic.
    def _as_dashboard_card(self):
        self.ensure_one()
        return {
            "id": self.widget_id.id,
            "line_id": self.id,
            "name": self.name,
            "icon": self.icon or "fa-line-chart",
            "display_style": self.display_style or "kpi",
            "column_span": self.column_span or "3",
            "metric_code": self.metric_code,
            "metric_type": self.metric_type or False,
            "value": self.value,
            "display_value": self.display_value or _("No Data"),
            "status": self.status,
            "status_label": self.status_label or "",
            "has_trend": self.has_trend,
            "trend_percent": self.trend_percent,
            "trend_display": f"{self.trend_percent:.2f}%",
            "trend_direction": self.trend_direction,
            "has_target": self.has_target,
            "target_value": self.target_value if self.has_target else False,
            "target_progress": self.target_progress,
            "target_progress_capped": min(max(self.target_progress, 0.0), 100.0),
            "target_progress_display": f"{min(max(self.target_progress, 0.0), 100.0):.1f}%",
            "report_run_id": self.report_run_id.id if self.report_run_id else False,
            "report_definition_id": self.definition_id.id if self.definition_id else False,
            "metric_id": self.metric_id.id if self.metric_id else False,
            "note": self.note or "",
        }

