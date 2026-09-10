# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ClinicDashboardBoardAnalytics(models.Model):
    _inherit = "clinic.dashboard.board"

    analytics_forecast_count = fields.Integer(
        compute="_compute_analytics_counts"
    )
    analytics_insight_count = fields.Integer(
        compute="_compute_analytics_counts"
    )

    def _compute_analytics_counts(self):
        Forecast = self.env["clinic.analytics.forecast"]
        Insight = self.env["clinic.analytics.insight"]
        for rec in self:
            scope = [
                ("company_id", "=", rec.company_id.id),
            ]
            if rec.default_branch_id:
                scope.append(
                    ("branch_id", "=", rec.default_branch_id.id)
                )
            rec.analytics_forecast_count = Forecast.search_count(
                scope
            )
            rec.analytics_insight_count = Insight.search_count(
                scope + [
                    (
                        "state",
                        "in",
                        ("new", "acknowledged"),
                    )
                ]
            )

    def action_view_analytics_forecasts(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
        ]
        if self.default_branch_id:
            domain.append(
                ("branch_id", "=", self.default_branch_id.id)
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Predictive Forecasts"),
            "res_model": "clinic.analytics.forecast",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_company_id": self.company_id.id,
                "default_branch_id": (
                    self.default_branch_id.id
                    if self.default_branch_id
                    else False
                ),
            },
        }

    def action_view_analytics_insights(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("new", "acknowledged")),
        ]
        if self.default_branch_id:
            domain.append(
                ("branch_id", "=", self.default_branch_id.id)
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Analytics Insights"),
            "res_model": "clinic.analytics.insight",
            "view_mode": "list,form",
            "domain": domain,
        }


class ClinicReportDefinitionAnalytics(models.Model):
    _inherit = "clinic.report.definition"

    analytics_kpi_count = fields.Integer(
        compute="_compute_analytics_kpi_count"
    )

    def _compute_analytics_kpi_count(self):
        KPI = self.env["clinic.analytics.kpi"]
        for rec in self:
            rec.analytics_kpi_count = KPI.search_count(
                [("report_definition_id", "=", rec.id)]
            )

    def action_view_analytics_kpis(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Analytics KPIs"),
            "res_model": "clinic.analytics.kpi",
            "view_mode": "list,form",
            "domain": [
                ("report_definition_id", "=", self.id)
            ],
            "context": {
                "default_report_definition_id": self.id
            },
        }

