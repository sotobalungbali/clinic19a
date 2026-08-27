# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


SOURCE_KEYS = [
    ("revenue_total", "Revenue - Gross Posted/Paid"),
    ("revenue_paid", "Revenue - Fully Paid"),
    ("booking_count", "Bookings - Volume"),
    ("booking_completion_rate", "Bookings - Completion Rate"),
    ("booking_no_show_rate", "Bookings - No Show Rate"),
    ("unique_patients", "Patients - Unique Completed"),
    ("repeat_patient_rate", "Patients - Repeat Rate"),
    ("membership_active", "Membership - Active Contracts"),
    ("membership_renewal_rate", "Membership - Renewal Rate"),
    ("wallet_balance", "Wallet - Active Balance"),
    ("feedback_nps", "Feedback - Net Promoter Score"),
    ("feedback_avg_rating", "Feedback - Average Rating"),
    ("quality_score", "Quality - Compliance Score"),
    ("incident_count", "Incident - Volume"),
    ("critical_incident_count", "Incident - Critical Volume"),
    ("marketing_reach", "Marketing - Included Reach"),
    ("marketing_delivery_rate", "Marketing - Delivery Rate"),
]

UNITS = [
    ("number", "Number"),
    ("count", "Count"),
    ("amount", "Amount"),
    ("percentage", "Percentage"),
    ("score", "Score"),
]


class ClinicAnalyticsKPI(models.Model):
    _name = "clinic.analytics.kpi"
    _description = "Clinic Analytics KPI Definition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, code, id"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("retired", "Retired"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    family = fields.Selection(
        [
            ("financial", "Financial"),
            ("operational", "Operational"),
            ("retention", "Retention"),
            ("experience", "Patient Experience"),
            ("quality", "Quality & Safety"),
            ("marketing", "Marketing"),
        ],
        required=True,
        index=True,
        tracking=True,
    )
    source_key = fields.Selection(
        SOURCE_KEYS,
        required=True,
        index=True,
        tracking=True,
    )
    unit = fields.Selection(
        UNITS,
        required=True,
        default="number",
        tracking=True,
    )
    direction = fields.Selection(
        [
            ("higher", "Higher is Better"),
            ("lower", "Lower is Better"),
            ("neutral", "Neutral"),
        ],
        default="higher",
        required=True,
        tracking=True,
    )
    forecastable = fields.Boolean(default=False, tracking=True)
    default_history_periods = fields.Integer(default=12)
    default_horizon_periods = fields.Integer(default=3)
    default_forecast_method = fields.Selection(
        [
            ("naive", "Naive"),
            ("moving_average", "Moving Average"),
            ("linear_trend", "Linear Trend"),
        ],
        default="moving_average",
        required=True,
    )

    has_target = fields.Boolean(default=False)
    target_value = fields.Float()
    has_warning_threshold = fields.Boolean(default=False)
    warning_threshold = fields.Float()
    has_critical_threshold = fields.Boolean(default=False)
    critical_threshold = fields.Float()

    report_definition_id = fields.Many2one(
        "clinic.report.definition",
        string="Governed Report Definition",
        ondelete="set null",
    )
    dashboard_board_ids = fields.Many2many(
        "clinic.dashboard.board",
        "clinic_an_kpi_board_rel",
        "kpi_id",
        "board_id",
        string="Related Dashboard Boards",
    )
    description = fields.Text()
    methodology = fields.Html()

    snapshot_line_count = fields.Integer(
        compute="_compute_usage_counts"
    )
    forecast_count = fields.Integer(
        compute="_compute_usage_counts"
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Analytics KPI code must be unique.",
    )
    _history_positive = models.Constraint(
        "CHECK(default_history_periods >= 2 AND default_history_periods <= 60)",
        "Default history periods must be between 2 and 60.",
    )
    _horizon_positive = models.Constraint(
        "CHECK(default_horizon_periods >= 1 AND default_horizon_periods <= 24)",
        "Default horizon periods must be between 1 and 24.",
    )

    @api.depends("code")
    def _compute_usage_counts(self):
        Line = self.env["clinic.analytics.snapshot.line"]
        Forecast = self.env["clinic.analytics.forecast"]
        for rec in self:
            rec.snapshot_line_count = Line.search_count(
                [("kpi_id", "=", rec.id)]
            )
            rec.forecast_count = Forecast.search_count(
                [("kpi_id", "=", rec.id)]
            )

    @api.constrains(
        "has_warning_threshold",
        "warning_threshold",
        "has_critical_threshold",
        "critical_threshold",
        "direction",
    )
    def _check_threshold_order(self):
        for rec in self:
            if not (
                rec.has_warning_threshold
                and rec.has_critical_threshold
                and rec.direction != "neutral"
            ):
                continue
            if (
                rec.direction == "higher"
                and rec.critical_threshold > rec.warning_threshold
            ):
                raise ValidationError(
                    _(
                        "For Higher-is-Better KPIs, Critical threshold must "
                        "be less than or equal to Warning."
                    )
                )
            if (
                rec.direction == "lower"
                and rec.critical_threshold < rec.warning_threshold
            ):
                raise ValidationError(
                    _(
                        "For Lower-is-Better KPIs, Critical threshold must "
                        "be greater than or equal to Warning."
                    )
                )

    def evaluate_status(self, value):
        self.ensure_one()
        value = float(value or 0.0)

        if self.direction == "neutral":
            return "normal"

        if self.direction == "higher":
            if (
                self.has_critical_threshold
                and value <= self.critical_threshold
            ):
                return "critical"
            if (
                self.has_warning_threshold
                and value <= self.warning_threshold
            ):
                return "warning"
            return "normal"

        if (
            self.has_critical_threshold
            and value >= self.critical_threshold
        ):
            return "critical"
        if (
            self.has_warning_threshold
            and value >= self.warning_threshold
        ):
            return "warning"
        return "normal"

    def action_activate(self):
        self.write({"state": "active", "active": True})
        return True

    def action_retire(self):
        self.write({"state": "retired", "active": False})
        return True

    def action_reset_draft(self):
        self.write({"state": "draft", "active": True})
        return True

    def action_view_snapshots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("KPI Snapshot Lines"),
            "res_model": "clinic.analytics.snapshot.line",
            "view_mode": "list,graph,pivot,form",
            "domain": [("kpi_id", "=", self.id)],
        }

    def action_view_forecasts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("KPI Forecasts"),
            "res_model": "clinic.analytics.forecast",
            "view_mode": "list,form",
            "domain": [("kpi_id", "=", self.id)],
            "context": {"default_kpi_id": self.id},
        }
