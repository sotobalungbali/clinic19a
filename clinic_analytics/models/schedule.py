# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicAnalyticsSchedule(models.Model):
    _name = "clinic.analytics.schedule"
    _description = "Clinic Analytics Schedule"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.analytics.scope.mixin",
    ]
    _order = "next_run_at, sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("paused", "Paused"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    schedule_type = fields.Selection(
        [
            ("snapshot", "KPI Snapshot"),
            ("forecast", "Forecast"),
            ("cohort", "Retention Cohort"),
        ],
        required=True,
        tracking=True,
    )
    cadence = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        default="monthly",
        required=True,
        tracking=True,
    )
    interval_count = fields.Integer(
        default=1,
        required=True,
    )
    next_run_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    last_run_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    window_days = fields.Integer(default=30)
    kpi_id = fields.Many2one(
        "clinic.analytics.kpi",
        domain="[('state', '=', 'active'), ('forecastable', '=', True)]",
    )
    forecast_frequency = fields.Selection(
        [
            ("week", "Weekly"),
            ("month", "Monthly"),
        ],
        default="month",
    )
    history_periods = fields.Integer(default=12)
    horizon_periods = fields.Integer(default=3)
    forecast_method = fields.Selection(
        [
            ("naive", "Naive"),
            ("moving_average", "Moving Average"),
            ("linear_trend", "Linear Trend"),
        ],
        default="moving_average",
    )
    moving_average_window = fields.Integer(default=3)
    cohort_month_offset = fields.Integer(
        default=1,
        help="Months before the current month for the cohort start.",
    )

    last_snapshot_id = fields.Many2one(
        "clinic.analytics.snapshot",
        readonly=True,
    )
    last_forecast_id = fields.Many2one(
        "clinic.analytics.forecast",
        readonly=True,
    )
    last_cohort_id = fields.Many2one(
        "clinic.analytics.cohort",
        readonly=True,
    )
    run_count = fields.Integer(default=0, readonly=True)

    _interval_positive = models.Constraint(
        "CHECK(interval_count >= 1 AND interval_count <= 365)",
        "Schedule interval must be between 1 and 365.",
    )
    _window_positive = models.Constraint(
        "CHECK(window_days >= 1 AND window_days <= 3660)",
        "Snapshot window must be between 1 and 3660 days.",
    )

    @api.constrains("schedule_type", "kpi_id")
    def _check_schedule_type(self):
        for rec in self:
            if rec.schedule_type == "forecast" and not rec.kpi_id:
                raise ValidationError(
                    _("Forecast schedules require a KPI.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_scope_authorized()
        return records

    def _require_manager(self):
        if not self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        ):
            raise AccessError(
                _("Analytics Manager access is required.")
            )

    def action_activate(self):
        self._require_manager()
        self._ensure_scope_authorized()
        self.write({
            "state": "active",
            "active": True,
            "last_error": False,
        })
        return True

    def action_pause(self):
        self._require_manager()
        self.write({"state": "paused"})
        return True

    def action_reset_draft(self):
        self._require_manager()
        self.write({"state": "draft"})
        return True

    def _next_run(self, base=None):
        self.ensure_one()
        base = fields.Datetime.to_datetime(
            base or self.next_run_at or fields.Datetime.now()
        )
        if self.cadence == "daily":
            return base + timedelta(days=self.interval_count)
        if self.cadence == "weekly":
            return base + timedelta(weeks=self.interval_count)
        return base + relativedelta(months=self.interval_count)

    def action_run_now(self):
        self._require_manager()
        self._run_once()
        return True

    def _run_once(self):
        self.ensure_one()
        self._ensure_scope_authorized()
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)

        try:
            if self.schedule_type == "snapshot":
                snapshot = self.env[
                    "clinic.analytics.snapshot"
                ].create({
                    "company_id": self.company_id.id,
                    "branch_id": (
                        self.branch_id.id
                        if self.branch_id
                        else False
                    ),
                    "date_from": today - timedelta(
                        days=self.window_days - 1
                    ),
                    "date_to": today,
                    "notes": _(
                        "Generated from schedule %s."
                    )
                    % self.display_name,
                })
                snapshot.action_generate()
                self.last_snapshot_id = snapshot.id

            elif self.schedule_type == "forecast":
                forecast = self.env[
                    "clinic.analytics.forecast"
                ].create({
                    "company_id": self.company_id.id,
                    "branch_id": (
                        self.branch_id.id
                        if self.branch_id
                        else False
                    ),
                    "kpi_id": self.kpi_id.id,
                    "as_of_date": today,
                    "frequency": self.forecast_frequency,
                    "history_periods": self.history_periods,
                    "horizon_periods": self.horizon_periods,
                    "method": self.forecast_method,
                    "moving_average_window": (
                        self.moving_average_window
                    ),
                    "notes": _(
                        "Generated from schedule %s."
                    )
                    % self.display_name,
                })
                forecast.action_run()
                self.last_forecast_id = forecast.id

            else:
                start = today.replace(day=1) - relativedelta(
                    months=self.cohort_month_offset
                )
                cohort = self.env[
                    "clinic.analytics.cohort"
                ].create({
                    "company_id": self.company_id.id,
                    "branch_id": (
                        self.branch_id.id
                        if self.branch_id
                        else False
                    ),
                    "cohort_start": start,
                    "notes": _(
                        "Generated from schedule %s."
                    )
                    % self.display_name,
                })
                cohort.action_run()
                self.last_cohort_id = cohort.id

            self.write({
                "last_run_at": now,
                "next_run_at": self._next_run(now),
                "run_count": self.run_count + 1,
                "last_error": False,
            })
        except Exception as exc:
            self.write({
                "last_run_at": now,
                "next_run_at": self._next_run(now),
                "last_error": str(exc)[:4000],
            })
        return True

    @api.model
    def _cron_run_due(self):
        """Bounded schedule runner; at most 10 schedules per cron pass."""
        now = fields.Datetime.now()
        schedules = self.sudo().search(
            [
                ("state", "=", "active"),
                ("active", "=", True),
                ("next_run_at", "<=", now),
            ],
            order="next_run_at, sequence, id",
            limit=10,
        )
        for schedule in schedules:
            schedule._run_once()
        if hasattr(self.env["ir.cron"], "_commit_progress"):
            self.env["ir.cron"]._commit_progress(
                len(schedules),
                remaining=(
                    self.sudo().search_count(
                        [
                            ("state", "=", "active"),
                            ("active", "=", True),
                            ("next_run_at", "<=", now),
                        ]
                    )
                ),
            )
        return True

    def action_open_last_result(self):
        self.ensure_one()
        if self.last_snapshot_id:
            model = "clinic.analytics.snapshot"
            res_id = self.last_snapshot_id.id
        elif self.last_forecast_id:
            model = "clinic.analytics.forecast"
            res_id = self.last_forecast_id.id
        elif self.last_cohort_id:
            model = "clinic.analytics.cohort"
            res_id = self.last_cohort_id.id
        else:
            raise UserError(
                _("This schedule has not generated a result yet.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Last Analytics Result"),
            "res_model": model,
            "res_id": res_id,
            "view_mode": "form",
        }

