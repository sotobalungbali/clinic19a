from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicDashboardSnapshot(models.Model):
    """Immutable dashboard refresh evidence built only from Clinic Reports output."""

    _name = "clinic.dashboard.snapshot"
    _description = "Clinic Dashboard Snapshot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "generated_at desc, id desc"
    _check_company_auto = True

    _name_company_unique = models.Constraint(
        "UNIQUE(company_id, name)",
        "Dashboard Snapshot reference must be unique per company.",
    )
    _date_order_valid = models.Constraint(
        "CHECK(date_to >= date_from)",
        "Dashboard Snapshot end date must be on or after start date.",
    )
    _scope_idx = models.Index(
        "(company_id, board_id, branch_id, date_from, date_to, state)"
    )

    name = fields.Char(
        default="/",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    board_id = fields.Many2one(
        "clinic.dashboard.board",
        required=True,
        ondelete="restrict",
        index=True,
    )
    dashboard_type = fields.Selection(
        related="board_id.dashboard_type",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    date_from = fields.Date(required=True, index=True)
    date_to = fields.Date(required=True, index=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("refreshing", "Refreshing"),
            ("ready", "Ready"),
            ("failed", "Failed"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    generated_at = fields.Datetime(readonly=True, index=True)
    generated_by_id = fields.Many2one("res.users", readonly=True)
    error_message = fields.Text(readonly=True)

    line_ids = fields.One2many(
        "clinic.dashboard.snapshot.line",
        "snapshot_id",
        string="KPI Snapshot Lines",
        copy=False,
    )
    line_count = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    critical_count = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    warning_count = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    no_data_count = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    available_count = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    report_run_count = fields.Integer(compute="_compute_report_run_count")

    @api.model_create_multi
    def create(self, vals_list):
        # Snapshots are generated evidence; direct CRUD is intentionally blocked.
        if not (self.env.su and self.env.context.get("dashboard_generation")):
            raise AccessError(
                _("Dashboard Snapshots can only be created by the Dashboard engine.")
            )

        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.dashboard.snapshot")
                    or "/"
                )
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if not (self.env.su and self.env.context.get("dashboard_generation")):
            raise AccessError(
                _("Dashboard Snapshots are engine-owned and immutable by RPC.")
            )
        return super().write(vals)

    def unlink(self):
        if not (self.env.su and self.env.context.get("dashboard_generation")):
            raise AccessError(
                _("Dashboard Snapshots can only be removed by controlled maintenance.")
            )
        return super().unlink()

    @api.constrains("board_id", "company_id", "branch_id")
    def _check_scope(self):
        for snapshot in self:
            if snapshot.board_id.company_id != snapshot.company_id:
                raise ValidationError(
                    _("Dashboard Snapshot company must match its Board company.")
                )
            if (
                snapshot.branch_id
                and snapshot.branch_id.company_id != snapshot.company_id
            ):
                raise ValidationError(
                    _("Dashboard Snapshot Branch must belong to its company.")
                )

    @api.depends("line_ids", "line_ids.status")
    # Exception counters are stored so Search/List views can filter them safely in Odoo 19.
    def _compute_line_counts(self):
        for snapshot in self:
            snapshot.line_count = len(snapshot.line_ids)
            snapshot.critical_count = len(
                snapshot.line_ids.filtered(
                    lambda line: line.status == "critical"
                )
            )
            snapshot.warning_count = len(
                snapshot.line_ids.filtered(
                    lambda line: line.status == "warning"
                )
            )
            snapshot.no_data_count = len(
                snapshot.line_ids.filtered(
                    lambda line: line.status
                    in ("no_data", "unsupported_scope", "error")
                )
            )
            snapshot.available_count = len(
                snapshot.line_ids.filtered(
                    lambda line: line.status
                    in ("normal", "warning", "critical")
                )
            )

    def _compute_report_run_count(self):
        for snapshot in self:
            snapshot.report_run_count = len(
                snapshot.line_ids.mapped("report_run_id")
            )

    # Unsupported Branch scope is persisted as evidence; company-wide data is never substituted silently.
    def _line_vals_unsupported(self, widget):
        self.ensure_one()
        return {
            "widget_id": widget.id,
            "sequence": widget.sequence,
            "name": widget.name,
            "metric_code": widget.metric_code,
            "icon": widget.icon,
            "display_style": widget.display_style,
            "column_span": widget.column_span,
            "definition_id": widget.definition_id.id,
            "status": "unsupported_scope",
            "status_label": _("Unsupported Branch Scope"),
            "display_value": _("Not Available"),
            "note": _(
                "The selected Branch cannot be applied because this Report "
                "Definition has no authoritative branch path."
            ),
            "target_value": widget.target_value if widget.has_target else 0.0,
            "has_target": widget.has_target,
        }

    # Missing Report Runs/metrics produce an explicit no-data/error card rather than a fabricated zero KPI.
    def _line_vals_no_data(
        self,
        widget,
        run=None,
        status="no_data",
        note=None,
    ):
        self.ensure_one()
        line_status = "error" if status == "generation_failed" else "no_data"
        return {
            "widget_id": widget.id,
            "sequence": widget.sequence,
            "name": widget.name,
            "metric_code": widget.metric_code,
            "icon": widget.icon,
            "display_style": widget.display_style,
            "column_span": widget.column_span,
            "definition_id": widget.definition_id.id,
            "report_run_id": run.id if run else False,
            "status": line_status,
            "status_label": (
                _("Generation Failed")
                if line_status == "error"
                else _("No Data")
            ),
            "display_value": _("No Data"),
            "note": note or (
                _("The exact-scope Report Run is unavailable.")
                if line_status == "no_data"
                else _("The delegated clinic_reports generation did not reach Ready state.")
            ),
            "target_value": widget.target_value if widget.has_target else 0.0,
            "has_target": widget.has_target,
        }

    # Snapshot values copy normalized Report Metric facts and add only target/trend/threshold presentation metadata.
    def _line_vals_metric(
        self,
        widget,
        report_run,
        metric,
        previous_metric=None,
    ):
        self.ensure_one()

        has_trend = bool(previous_metric) and previous_metric.value != 0
        trend_percent = 0.0
        trend_direction = "none"
        if has_trend:
            trend_percent = (
                (metric.value - previous_metric.value)
                / abs(previous_metric.value)
                * 100.0
            )
            if trend_percent > 0.000001:
                trend_direction = "up"
            elif trend_percent < -0.000001:
                trend_direction = "down"
            else:
                trend_direction = "flat"

        target_progress = 0.0
        if widget.has_target:
            if widget.direction == "lower_good":
                if metric.value <= widget.target_value:
                    target_progress = 100.0
                elif metric.value:
                    target_progress = (
                        widget.target_value / abs(metric.value) * 100.0
                    )
            elif widget.target_value:
                target_progress = (
                    metric.value / widget.target_value * 100.0
                )
            target_progress = max(0.0, min(target_progress, 200.0))

        status = widget._alert_level(metric.value)
        status_label = {
            "normal": _("On Track"),
            "warning": _("Warning"),
            "critical": _("Critical"),
        }[status]

        return {
            "widget_id": widget.id,
            "sequence": widget.sequence,
            "name": widget.name,
            "metric_code": widget.metric_code,
            "metric_type": metric.metric_type,
            "icon": widget.icon,
            "display_style": widget.display_style,
            "column_span": widget.column_span,
            "definition_id": widget.definition_id.id,
            "report_run_id": report_run.id,
            "metric_id": metric.id,
            "value": metric.value,
            "display_value": metric.display_value,
            "previous_value": previous_metric.value if previous_metric else 0.0,
            "has_trend": has_trend,
            "trend_percent": trend_percent,
            "trend_direction": trend_direction,
            "has_target": widget.has_target,
            "target_value": widget.target_value if widget.has_target else 0.0,
            "target_progress": target_progress,
            "status": status,
            "status_label": status_label,
            "note": metric.note or "",
        }

    def action_open_board(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Board"),
            "res_model": "clinic.dashboard.board",
            "view_mode": "form",
            "res_id": self.board_id.id,
        }

    def action_open_live_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "clinic_dashboard.main",
            "target": "main",
            "params": {
                "board_id": self.board_id.id,
                "date_from": fields.Date.to_string(self.date_from),
                "date_to": fields.Date.to_string(self.date_to),
                "branch_id": self.branch_id.id if self.branch_id else False,
            },
        }

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard KPI Lines"),
            "res_model": "clinic.dashboard.snapshot.line",
            "view_mode": "list,form,pivot,graph",
            "domain": [("snapshot_id", "=", self.id)],
        }

    def action_view_report_runs(self):
        self.ensure_one()
        run_ids = self.line_ids.mapped("report_run_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Report Runs"),
            "res_model": "clinic.report.run",
            "view_mode": "list,form",
            "domain": [("id", "in", run_ids)],
        }

    @api.model
    # Retention maintenance archives historical snapshots; KPI evidence is never auto-deleted.
    def _cron_archive_old_snapshots(self):
        # Governance maintenance archives old Ready snapshots but never deletes
        # historical KPI evidence.
        today = fields.Date.context_today(self)
        for company in self.env["res.company"].sudo().search([]):
            retention = max(
                company.clinic_dashboard_snapshot_retention_days or 365,
                30,
            )
            cutoff = today - timedelta(days=retention)
            old = self.sudo().search([
                ("company_id", "=", company.id),
                ("state", "=", "ready"),
                ("date_to", "<", cutoff),
            ])
            if old:
                old.with_context(dashboard_generation=True).write({
                    "state": "archived",
                })
        return True

    def action_archive(self):
        if not self.env.user.has_group(
            "clinic_dashboard.group_dashboard_manager"
        ):
            raise AccessError(
                _("Only a Dashboard Manager can archive snapshots.")
            )
        self.sudo().with_context(dashboard_generation=True).write({
            "state": "archived",
        })
        return True
