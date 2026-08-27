# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicAnalyticsInsight(models.Model):
    _name = "clinic.analytics.insight"
    _description = "Clinic Analytics Actionable Insight"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.analytics.scope.mixin",
    ]
    _order = "severity desc, create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        related="title",
        store=True,
        readonly=True,
    )
    title = fields.Char(required=True, tracking=True)
    source_type = fields.Selection(
        [
            ("snapshot", "KPI Snapshot"),
            ("forecast", "Forecast"),
            ("cohort", "Retention Cohort"),
            ("manual", "Manual"),
        ],
        default="manual",
        required=True,
        index=True,
    )
    snapshot_id = fields.Many2one(
        "clinic.analytics.snapshot",
        ondelete="cascade",
        index=True,
    )
    snapshot_line_id = fields.Many2one(
        "clinic.analytics.snapshot.line",
        ondelete="set null",
        index=True,
    )
    forecast_id = fields.Many2one(
        "clinic.analytics.forecast",
        ondelete="cascade",
        index=True,
    )
    cohort_id = fields.Many2one(
        "clinic.analytics.cohort",
        ondelete="cascade",
        index=True,
    )
    kpi_id = fields.Many2one(
        "clinic.analytics.kpi",
        ondelete="set null",
        index=True,
    )
    severity = fields.Selection(
        [
            ("info", "Information"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        default="info",
        required=True,
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("acknowledged", "Acknowledged"),
            ("resolved", "Resolved"),
            ("dismissed", "Dismissed"),
        ],
        default="new",
        required=True,
        index=True,
        tracking=True,
    )
    owner_id = fields.Many2one(
        "res.users",
        tracking=True,
    )
    narrative = fields.Text(required=True, readonly=True)
    recommendation = fields.Text(readonly=True)
    resolution_note = fields.Text()
    acknowledged_at = fields.Datetime(readonly=True)
    acknowledged_by_id = fields.Many2one(
        "res.users",
        readonly=True,
    )
    resolved_at = fields.Datetime(readonly=True)
    resolved_by_id = fields.Many2one(
        "res.users",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        internal = self.env.context.get(
            "clinic_analytics_internal"
        )
        if not internal and not self.env.user.has_group(
            "clinic_analytics.group_analytics_analyst"
        ):
            raise AccessError(
                _("Analytics Analyst access is required.")
            )
        records = super().create(vals_list)
        records._ensure_scope_authorized()
        return records

    @api.constrains(
        "source_type",
        "snapshot_id",
        "forecast_id",
        "cohort_id",
    )
    def _check_source(self):
        for rec in self:
            if rec.source_type == "snapshot" and not rec.snapshot_id:
                raise ValidationError(
                    _("Snapshot insight requires a Snapshot.")
                )
            if rec.source_type == "forecast" and not rec.forecast_id:
                raise ValidationError(
                    _("Forecast insight requires a Forecast.")
                )
            if rec.source_type == "cohort" and not rec.cohort_id:
                raise ValidationError(
                    _("Cohort insight requires a Cohort.")
                )

    def write(self, vals):
        if (
            not self.env.su
            and not self.env.context.get(
                "clinic_analytics_internal"
            )
            and not self.env.user.has_group(
                "clinic_analytics.group_analytics_manager"
            )
        ):
            allowed = {
                "state",
                "owner_id",
                "resolution_note",
                "acknowledged_at",
                "acknowledged_by_id",
                "resolved_at",
                "resolved_by_id",
                "message_follower_ids",
                "activity_ids",
            }
            if set(vals) - allowed:
                raise AccessError(
                    _(
                        "Analysts may only manage insight workflow, owner "
                        "and resolution fields."
                    )
                )
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get(
            "clinic_analytics_internal"
        ) and not self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        ):
            raise AccessError(
                _("Only Analytics Managers may delete insights.")
            )
        return super().unlink()

    def action_acknowledge(self):
        self.write({
            "state": "acknowledged",
            "acknowledged_at": fields.Datetime.now(),
            "acknowledged_by_id": self.env.user.id,
            "owner_id": self.env.user.id,
        })
        return True

    def action_resolve(self):
        if any(not rec.resolution_note for rec in self):
            raise ValidationError(
                _("Resolution Note is required.")
            )
        self.write({
            "state": "resolved",
            "resolved_at": fields.Datetime.now(),
            "resolved_by_id": self.env.user.id,
        })
        return True

    def action_dismiss(self):
        if not self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        ):
            raise AccessError(
                _("Analytics Manager access is required.")
            )
        self.write({
            "state": "dismissed",
            "resolved_at": fields.Datetime.now(),
            "resolved_by_id": self.env.user.id,
        })
        return True

    def action_reopen(self):
        if not self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        ):
            raise AccessError(
                _("Analytics Manager access is required.")
            )
        self.write({
            "state": "new",
            "resolved_at": False,
            "resolved_by_id": False,
        })
        return True

    def action_open_source(self):
        self.ensure_one()
        if self.snapshot_id:
            model = "clinic.analytics.snapshot"
            res_id = self.snapshot_id.id
        elif self.forecast_id:
            model = "clinic.analytics.forecast"
            res_id = self.forecast_id.id
        elif self.cohort_id:
            model = "clinic.analytics.cohort"
            res_id = self.cohort_id.id
        else:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Analytics Source"),
            "res_model": model,
            "res_id": res_id,
            "view_mode": "form",
        }
