# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAnalyticsForecastPoint(models.Model):
    _name = "clinic.analytics.forecast.point"
    _description = "Clinic Analytics Forecast Point"
    _order = "forecast_id, sequence, id"
    _check_company_auto = True

    forecast_id = fields.Many2one(
        "clinic.analytics.forecast",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(required=True)
    company_id = fields.Many2one(
        related="forecast_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        related="forecast_id.branch_id",
        store=True,
        index=True,
        readonly=True,
    )
    kpi_id = fields.Many2one(
        related="forecast_id.kpi_id",
        store=True,
        index=True,
        readonly=True,
    )
    unit = fields.Selection(
        related="kpi_id.unit",
        store=True,
        readonly=True,
    )
    point_type = fields.Selection(
        [
            ("actual", "Historical"),
            ("forecast", "Forecast"),
        ],
        required=True,
        index=True,
        readonly=True,
    )
    period_start = fields.Date(required=True, index=True, readonly=True)
    period_end = fields.Date(required=True, index=True, readonly=True)
    actual_value = fields.Float(readonly=True)
    predicted_value = fields.Float(readonly=True)
    has_prediction = fields.Boolean(readonly=True)
    lower_bound = fields.Float(readonly=True)
    upper_bound = fields.Float(readonly=True)
    residual = fields.Float(readonly=True)
    source_model = fields.Char(readonly=True)
    source_domain_json = fields.Text(
        readonly=True,
        groups="clinic_analytics.group_analytics_manager",
    )

    _forecast_sequence_unique = models.Constraint(
        "UNIQUE(forecast_id, sequence)",
        "Forecast point sequence must be unique within a forecast.",
    )
    _period_order = models.Constraint(
        "CHECK(period_start <= period_end)",
        "Forecast point start date must not be after end date.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get(
                "clinic_analytics_internal"
            )
        ):
            raise AccessError(
                _("Forecast points can only be created by Analytics engine.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(
            "clinic_analytics_internal"
        ):
            raise AccessError(
                _("Forecast points are immutable.")
            )
        return super().write(vals)

    def unlink(self):
        if not (
            self.env.su
            or self.env.context.get(
                "clinic_analytics_internal"
            )
        ):
            raise AccessError(
                _("Forecast points are immutable.")
            )
        return super().unlink()

    def action_open_source(self):
        self.ensure_one()
        if self.point_type != "actual":
            raise UserError(
                _("Forecast points do not reference future source records.")
            )
        if not self.source_model or self.source_model not in self.env:
            raise UserError(
                _("The source model is not available.")
            )
        try:
            domain = json.loads(
                self.sudo().source_domain_json or "[]"
            )
        except Exception:
            domain = []
        return {
            "type": "ir.actions.act_window",
            "name": _("Historical Source Records"),
            "res_model": self.source_model,
            "view_mode": "list,form",
            "domain": domain,
        }
