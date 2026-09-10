# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAnalyticsForecast(models.Model):
    _name = "clinic.analytics.forecast"
    _description = "Clinic Analytics Forecast Run"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.analytics.scope.mixin",
    ]
    _order = "as_of_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        default=lambda self: _("New"),
        readonly=True,
        copy=False,
        index=True,
    )
    kpi_id = fields.Many2one(
        "clinic.analytics.kpi",
        required=True,
        ondelete="restrict",
        domain="[('state', '=', 'active'), ('forecastable', '=', True)]",
        tracking=True,
    )
    as_of_date = fields.Date(
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    frequency = fields.Selection(
        [
            ("week", "Weekly"),
            ("month", "Monthly"),
        ],
        default="month",
        required=True,
        tracking=True,
    )
    history_periods = fields.Integer(
        default=12,
        required=True,
        tracking=True,
    )
    horizon_periods = fields.Integer(
        default=3,
        required=True,
        tracking=True,
    )
    method = fields.Selection(
        [
            ("naive", "Naive"),
            ("moving_average", "Moving Average"),
            ("linear_trend", "Linear Trend"),
        ],
        default="moving_average",
        required=True,
        tracking=True,
    )
    moving_average_window = fields.Integer(
        default=3,
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Ready"),
            ("failed", "Failed"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    generated_by_id = fields.Many2one(
        "res.users",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)

    mae = fields.Float(
        string="MAE",
        readonly=True,
        help="Mean Absolute Error over available historical fitted values.",
    )
    mape = fields.Float(
        string="MAPE (%)",
        readonly=True,
        help="Mean Absolute Percentage Error where actual value is non-zero.",
    )
    trend_slope = fields.Float(readonly=True)
    residual_std = fields.Float(
        string="Residual Std. Dev.",
        readonly=True,
    )

    point_ids = fields.One2many(
        "clinic.analytics.forecast.point",
        "forecast_id",
        string="Forecast Points",
        copy=False,
    )
    point_count = fields.Integer(compute="_compute_counts")
    insight_ids = fields.One2many(
        "clinic.analytics.insight",
        "forecast_id",
        string="Insights",
        readonly=True,
    )
    insight_count = fields.Integer(compute="_compute_counts")
    notes = fields.Text()

    _history_range = models.Constraint(
        "CHECK(history_periods >= 2 AND history_periods <= 60)",
        "History periods must be between 2 and 60.",
    )
    _horizon_range = models.Constraint(
        "CHECK(horizon_periods >= 1 AND horizon_periods <= 24)",
        "Forecast horizon must be between 1 and 24 periods.",
    )
    _window_range = models.Constraint(
        "CHECK(moving_average_window >= 2 AND moving_average_window <= 12)",
        "Moving Average window must be between 2 and 12.",
    )

    @api.depends("point_ids", "insight_ids")
    def _compute_counts(self):
        for rec in self:
            rec.point_count = len(rec.point_ids)
            rec.insight_count = len(rec.insight_ids)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        kpi_id = values.get("kpi_id")
        if kpi_id:
            kpi = self.env[
                "clinic.analytics.kpi"
            ].browse(kpi_id)
            values.setdefault(
                "history_periods",
                kpi.default_history_periods,
            )
            values.setdefault(
                "horizon_periods",
                kpi.default_horizon_periods,
            )
            values.setdefault(
                "method",
                kpi.default_forecast_method,
            )
        return values

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = (
                    sequence.next_by_code(
                        "clinic.analytics.forecast"
                    )
                    or _("New")
                )
        records = super().create(vals_list)
        records._ensure_scope_authorized()
        return records

    def write(self, vals):
        if not self.env.context.get(
            "clinic_analytics_internal"
        ):
            locked = self.filtered(
                lambda rec: rec.state in ("done", "archived")
            )
            protected = {
                "company_id",
                "branch_id",
                "kpi_id",
                "as_of_date",
                "frequency",
                "history_periods",
                "horizon_periods",
                "method",
                "moving_average_window",
                "point_ids",
            }
            if locked and protected.intersection(vals):
                raise AccessError(
                    _("Ready/Archived forecasts are immutable.")
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered(
            lambda rec: rec.state in ("done", "archived")
        ):
            raise AccessError(
                _("Ready/Archived forecasts cannot be deleted.")
            )
        return super().unlink()

    def _require_analyst(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_analytics.group_analytics_analyst"
        ):
            raise AccessError(
                _("Analytics Analyst access is required.")
            )

    def action_run(self):
        self._require_analyst()
        Engine = self.env["clinic.analytics.engine"]
        Forecaster = self.env[
            "clinic.analytics.forecasting"
        ]
        Point = self.env[
            "clinic.analytics.forecast.point"
        ]

        for rec in self:
            rec._ensure_scope_authorized()
            if rec.state not in ("draft", "failed"):
                raise UserError(
                    _("Only Draft or Failed forecasts can be run.")
                )
            if not rec.kpi_id.forecastable:
                raise UserError(
                    _("The selected KPI is not enabled for forecasting.")
                )

            rec.with_context(
                clinic_analytics_internal=True
            ).write({
                "state": "running",
                "started_at": fields.Datetime.now(),
                "error_message": False,
            })

            try:
                with self.env.cr.savepoint():
                    rec.point_ids.sudo().with_context(
                        clinic_analytics_internal=True
                    ).unlink()

                    history_periods = Engine.historical_periods(
                        rec.as_of_date,
                        rec.frequency,
                        rec.history_periods,
                    )
                    values = []
                    history_results = []

                    for period_start, period_end in history_periods:
                        result = Engine.evaluate(
                            rec.kpi_id.source_key,
                            rec.company_id,
                            rec.branch_id,
                            period_start,
                            period_end,
                        )
                        values.append(result["value"])
                        history_results.append(
                            (
                                period_start,
                                period_end,
                                result,
                            )
                        )

                    forecast_result = Forecaster.run(
                        values,
                        rec.method,
                        rec.horizon_periods,
                        rec.moving_average_window,
                        rec.kpi_id.unit,
                    )

                    for index, (
                        period_start,
                        period_end,
                        source,
                    ) in enumerate(history_results):
                        fitted = forecast_result[
                            "fitted"
                        ][index]
                        Point.sudo().with_context(
                            clinic_analytics_internal=True
                        ).create({
                            "forecast_id": rec.id,
                            "sequence": index + 1,
                            "point_type": "actual",
                            "period_start": period_start,
                            "period_end": period_end,
                            "actual_value": source["value"],
                            "predicted_value": (
                                fitted
                                if fitted is not None
                                else 0.0
                            ),
                            "has_prediction": fitted is not None,
                            "residual": (
                                source["value"] - fitted
                                if fitted is not None
                                else 0.0
                            ),
                            "source_model": source[
                                "source_model"
                            ],
                            "source_domain_json": source[
                                "source_domain_json"
                            ],
                        })

                    future_periods = Engine.future_periods(
                        rec.as_of_date,
                        rec.frequency,
                        rec.horizon_periods,
                    )
                    base_sequence = len(history_periods)
                    for offset, (
                        period_start,
                        period_end,
                    ) in enumerate(future_periods):
                        row = forecast_result["future"][offset]
                        Point.sudo().with_context(
                            clinic_analytics_internal=True
                        ).create({
                            "forecast_id": rec.id,
                            "sequence": base_sequence + offset + 1,
                            "point_type": "forecast",
                            "period_start": period_start,
                            "period_end": period_end,
                            "predicted_value": row[
                                "predicted"
                            ],
                            "has_prediction": True,
                            "lower_bound": row["lower"],
                            "upper_bound": row["upper"],
                        })

                    rec.with_context(
                        clinic_analytics_internal=True
                    ).write({
                        "state": "done",
                        "completed_at": fields.Datetime.now(),
                        "generated_by_id": self.env.user.id,
                        "mae": forecast_result["mae"],
                        "mape": forecast_result["mape"],
                        "trend_slope": forecast_result["slope"],
                        "residual_std": forecast_result[
                            "residual_std"
                        ],
                    })
            except Exception as exc:
                rec.with_context(
                    clinic_analytics_internal=True
                ).write({
                    "state": "failed",
                    "error_message": str(exc)[:4000],
                })
                continue

            rec._generate_forecast_insight()
            Bridge = self.env[
                "clinic.analytics.integration.service"
            ]
            Bridge.emit_audit(
                rec,
                "custom",
                _("Analytics forecast generated."),
            )
            Bridge.publish_event(
                rec,
                "analytics.forecast.ready",
                {
                    "kpi_code": rec.kpi_id.code,
                    "method": rec.method,
                    "history_periods": rec.history_periods,
                    "horizon_periods": rec.horizon_periods,
                    "mae": rec.mae,
                    "mape": rec.mape,
                    "trend_slope": rec.trend_slope,
                },
            )
        return True

    def _generate_forecast_insight(self):
        Insight = self.env["clinic.analytics.insight"]
        for rec in self:
            rec.insight_ids.filtered(
                lambda insight: insight.state
                not in ("resolved", "dismissed")
            ).sudo().with_context(
                clinic_analytics_internal=True
            ).unlink()

            slope = rec.trend_slope
            direction = rec.kpi_id.direction
            adverse = (
                direction == "higher" and slope < 0
            ) or (
                direction == "lower" and slope > 0
            )
            if not adverse or abs(slope) < 1e-9:
                continue

            severity = "warning"
            if rec.mape > 50:
                severity = "info"

            Insight.with_context(
                clinic_analytics_internal=True
            ).create({
                "company_id": rec.company_id.id,
                "branch_id": (
                    rec.branch_id.id
                    if rec.branch_id
                    else False
                ),
                "source_type": "forecast",
                "forecast_id": rec.id,
                "kpi_id": rec.kpi_id.id,
                "severity": severity,
                "title": _("%s adverse forecast direction")
                % rec.kpi_id.name,
                "narrative": _(
                    "The baseline %s forecast has slope %.4f. "
                    "MAPE is %.2f%%; treat this as decision support, "
                    "not a guarantee."
                )
                % (
                    dict(rec._fields["method"].selection)[
                        rec.method
                    ],
                    rec.trend_slope,
                    rec.mape,
                ),
                "recommendation": _(
                    "Review operational drivers and compare with governed "
                    "Clinic Reports before changing business policy."
                ),
            })

    def action_reset_draft(self):
        if not self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        ):
            raise AccessError(
                _("Analytics Manager access is required.")
            )
        self.with_context(
            clinic_analytics_internal=True
        ).write({
            "state": "draft",
            "error_message": False,
        })
        return True

    def action_archive(self):
        if not self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        ):
            raise AccessError(
                _("Analytics Manager access is required.")
            )
        self.with_context(
            clinic_analytics_internal=True
        ).write({"state": "archived"})
        return True

    def action_view_points(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Forecast Points"),
            "res_model": "clinic.analytics.forecast.point",
            "view_mode": "list,graph,pivot,form",
            "domain": [("forecast_id", "=", self.id)],
        }

    def action_view_insights(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Analytics Insights"),
            "res_model": "clinic.analytics.insight",
            "view_mode": "list,form",
            "domain": [("forecast_id", "=", self.id)],
        }
