# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAnalyticsSnapshotLine(models.Model):
    _name = "clinic.analytics.snapshot.line"
    _description = "Clinic Analytics KPI Snapshot Line"
    _order = "date_to desc, kpi_sequence, id"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinic.analytics.snapshot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    kpi_id = fields.Many2one(
        "clinic.analytics.kpi",
        required=True,
        ondelete="restrict",
        index=True,
    )
    kpi_sequence = fields.Integer(
        related="kpi_id.sequence",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="snapshot_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        related="snapshot_id.branch_id",
        store=True,
        index=True,
        readonly=True,
    )
    date_from = fields.Date(
        related="snapshot_id.date_from",
        store=True,
        index=True,
        readonly=True,
    )
    date_to = fields.Date(
        related="snapshot_id.date_to",
        store=True,
        index=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="snapshot_id.currency_id",
        store=True,
        readonly=True,
    )
    unit = fields.Selection(
        related="kpi_id.unit",
        store=True,
        readonly=True,
    )
    value = fields.Float(readonly=True)
    previous_value = fields.Float(readonly=True)
    has_previous = fields.Boolean(readonly=True)
    trend_percent = fields.Float(readonly=True)
    status = fields.Selection(
        [
            ("normal", "Normal"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        default="normal",
        required=True,
        index=True,
        readonly=True,
    )
    display_value = fields.Char(
        compute="_compute_display_value",
        store=True,
    )
    source_model = fields.Char(readonly=True, index=True)
    source_count = fields.Integer(readonly=True)
    source_domain_json = fields.Text(
        readonly=True,
        groups="clinic_analytics.group_analytics_manager",
    )
    note = fields.Char(readonly=True)

    _kpi_snapshot_unique = models.Constraint(
        "UNIQUE(snapshot_id, kpi_id)",
        "A KPI can appear only once in an analytics snapshot.",
    )

    @api.depends("value", "unit", "currency_id")
    def _compute_display_value(self):
        for rec in self:
            if rec.unit == "percentage":
                rec.display_value = f"{rec.value:.2f}%"
            elif rec.unit == "amount":
                symbol = rec.currency_id.symbol or ""
                rec.display_value = f"{symbol} {rec.value:,.2f}".strip()
            elif rec.unit == "count":
                rec.display_value = f"{rec.value:,.0f}"
            else:
                rec.display_value = f"{rec.value:,.2f}"

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get(
                "clinic_analytics_internal"
            )
        ):
            raise AccessError(
                _("Snapshot lines can only be created by Analytics engine.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(
            "clinic_analytics_internal"
        ):
            raise AccessError(
                _("Analytics snapshot lines are immutable.")
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
                _("Analytics snapshot lines are immutable.")
            )
        return super().unlink()

    def action_open_source(self):
        self.ensure_one()
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
            "name": _("%s Source Records") % self.kpi_id.name,
            "res_model": self.source_model,
            "view_mode": "list,form",
            "domain": domain,
        }
