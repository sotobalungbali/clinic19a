from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .dashboard_defaults import DISPLAY_STYLE_SELECTION, DIRECTION_SELECTION


class ClinicDashboardWidget(models.Model):
    """One dashboard card mapped to one normalized Clinic Reports metric code."""

    _name = "clinic.dashboard.widget"
    _description = "Clinic Dashboard Widget"
    _order = "board_id, sequence, id"
    _check_company_auto = True

    _metric_unique = models.Constraint(
        "UNIQUE(board_id, definition_id, metric_code)",
        "The same Report Metric can only appear once on a Dashboard Board.",
    )
    _board_sequence_idx = models.Index("(board_id, active, sequence)")

    board_id = fields.Many2one(
        "clinic.dashboard.board",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="board_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    definition_id = fields.Many2one(
        "clinic.report.definition",
        string="Report Definition",
        required=True,
        ondelete="restrict",
        domain="[('state', '=', 'active')]",
        index=True,
    )
    report_key = fields.Selection(
        related="definition_id.report_key",
        store=True,
        readonly=True,
        index=True,
    )
    metric_code = fields.Char(
        required=True,
        index=True,
        help="Exact normalized metric code produced by clinic_reports.",
    )

    icon = fields.Char(
        default="fa-line-chart",
        help="Font Awesome class, for example fa-money or fa-clock-o.",
    )
    display_style = fields.Selection(
        DISPLAY_STYLE_SELECTION,
        required=True,
        default="kpi",
    )
    column_span = fields.Selection(
        [
            ("3", "Quarter Width"),
            ("4", "One Third"),
            ("6", "Half Width"),
            ("12", "Full Width"),
        ],
        default="3",
        required=True,
    )
    direction = fields.Selection(
        DIRECTION_SELECTION,
        default="neutral",
        required=True,
        help="Controls trend/threshold interpretation only; it does not change KPI calculation.",
    )

    has_target = fields.Boolean(default=False)
    target_value = fields.Float(default=0.0)

    has_warning_threshold = fields.Boolean(default=False)
    warning_threshold = fields.Float(default=0.0)
    has_critical_threshold = fields.Boolean(default=False)
    critical_threshold = fields.Float(default=0.0)

    help_text = fields.Text()
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("metric_code"):
                vals["metric_code"] = vals["metric_code"].strip().upper()
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if "metric_code" in vals and vals["metric_code"]:
            vals = dict(vals)
            vals["metric_code"] = vals["metric_code"].strip().upper()
        return super().write(vals)

    @api.constrains("board_id", "definition_id")
    def _check_definition_scope(self):
        for widget in self:
            if widget.definition_id.state != "active":
                raise ValidationError(
                    _("Dashboard Widgets require an Active Report Definition.")
                )

    @api.constrains(
        "direction",
        "has_warning_threshold",
        "warning_threshold",
        "has_critical_threshold",
        "critical_threshold",
    )
    def _check_threshold_order(self):
        for widget in self:
            if not (
                widget.has_warning_threshold
                and widget.has_critical_threshold
                and widget.direction != "neutral"
            ):
                continue

            if (
                widget.direction == "higher_good"
                and widget.critical_threshold > widget.warning_threshold
            ):
                raise ValidationError(
                    _(
                        "For Higher-is-Better KPIs, Critical Threshold must be "
                        "less than or equal to Warning Threshold."
                    )
                )

            if (
                widget.direction == "lower_good"
                and widget.critical_threshold < widget.warning_threshold
            ):
                raise ValidationError(
                    _(
                        "For Lower-is-Better KPIs, Critical Threshold must be "
                        "greater than or equal to Warning Threshold."
                    )
                )

    # Threshold interpretation is presentation governance only; the numeric KPI still comes from Clinic Reports.
    def _alert_level(self, value):
        self.ensure_one()
        if self.direction == "neutral":
            return "normal"

        if self.direction == "higher_good":
            if self.has_critical_threshold and value <= self.critical_threshold:
                return "critical"
            if self.has_warning_threshold and value <= self.warning_threshold:
                return "warning"
            return "normal"

        if self.has_critical_threshold and value >= self.critical_threshold:
            return "critical"
        if self.has_warning_threshold and value >= self.warning_threshold:
            return "warning"
        return "normal"

    # Empty cards stay visible to make missing report coverage explicit instead of silently hiding a KPI.
    def _empty_dashboard_card(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon or "fa-line-chart",
            "display_style": self.display_style,
            "column_span": self.column_span,
            "metric_code": self.metric_code,
            "metric_type": False,
            "value": 0.0,
            "display_value": _("No Data"),
            "status": "no_data",
            "status_label": _("No Data"),
            "has_trend": False,
            "trend_percent": 0.0,
            "trend_display": "0.00%",
            "trend_direction": "none",
            "has_target": self.has_target,
            "target_value": self.target_value if self.has_target else False,
            "target_progress": 0.0,
            "target_progress_capped": 0.0,
            "target_progress_display": "0.0%",
            "report_run_id": False,
            "report_definition_id": self.definition_id.id,
            "note": _(
                "Refresh the Dashboard or generate the matching Report Run."
            ),
        }

    # Manual drill-down uses the latest generated source Run but never changes its state or contents.
    def _latest_report_run(self):
        self.ensure_one()
        return self.env["clinic.report.run"].search([
            ("definition_id", "=", self.definition_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("ready", "finalized", "archived")),
        ], order="date_to desc, generated_at desc, id desc", limit=1)

    def action_open_definition(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Definition"),
            "res_model": "clinic.report.definition",
            "view_mode": "form",
            "res_id": self.definition_id.id,
        }

    def action_open_latest_report(self):
        self.ensure_one()
        run = self._latest_report_run()
        if not run:
            raise UserError(
                _("No generated Report Run is available for this Widget.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Report Run"),
            "res_model": "clinic.report.run",
            "view_mode": "form",
            "res_id": run.id,
        }

    def action_open_latest_metric(self):
        self.ensure_one()
        run = self._latest_report_run()
        if not run:
            raise UserError(_("No generated Report Run is available."))
        metric = run.metric_ids.filtered(
            lambda rec: rec.code == self.metric_code
        )[:1]
        if not metric:
            raise UserError(
                _("The latest Report Run did not produce metric %s.")
                % self.metric_code
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "clinic.report.metric",
            "view_mode": "form",
            "res_id": metric.id,
        }

