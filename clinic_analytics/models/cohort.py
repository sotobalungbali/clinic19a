# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAnalyticsCohort(models.Model):
    _name = "clinic.analytics.cohort"
    _description = "Clinic Analytics Patient Retention Cohort"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.analytics.scope.mixin",
    ]
    _order = "cohort_start desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        default=lambda self: _("New"),
        readonly=True,
        copy=False,
        index=True,
    )
    cohort_start = fields.Date(
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
        tracking=True,
    )
    cohort_end = fields.Date(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Ready"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    cohort_size = fields.Integer(readonly=True)
    retained_30 = fields.Integer(readonly=True)
    retained_60 = fields.Integer(readonly=True)
    retained_90 = fields.Integer(readonly=True)
    retention_30 = fields.Float(
        string="30-Day Retention (%)",
        readonly=True,
    )
    retention_60 = fields.Float(
        string="60-Day Retention (%)",
        readonly=True,
    )
    retention_90 = fields.Float(
        string="90-Day Retention (%)",
        readonly=True,
    )
    source_booking_count = fields.Integer(readonly=True)
    generated_at = fields.Datetime(readonly=True)
    generated_by_id = fields.Many2one(
        "res.users",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)
    insight_ids = fields.One2many(
        "clinic.analytics.insight",
        "cohort_id",
        string="Insights",
        readonly=True,
    )
    insight_count = fields.Integer(
        compute="_compute_insight_count"
    )
    notes = fields.Text()

    @api.depends("insight_ids")
    def _compute_insight_count(self):
        for rec in self:
            rec.insight_count = len(rec.insight_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = (
                    sequence.next_by_code(
                        "clinic.analytics.cohort"
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
            if self.filtered(lambda rec: rec.state == "done") and {
                "company_id",
                "branch_id",
                "cohort_start",
            }.intersection(vals):
                raise AccessError(
                    _("Ready retention cohorts are immutable.")
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda rec: rec.state == "done"):
            raise AccessError(
                _("Ready retention cohorts cannot be deleted.")
            )
        return super().unlink()

    def action_run(self):
        if not self.env.su and not self.env.user.has_group(
            "clinic_analytics.group_analytics_analyst"
        ):
            raise AccessError(
                _("Analytics Analyst access is required.")
            )

        Engine = self.env["clinic.analytics.engine"]
        for rec in self:
            rec._ensure_scope_authorized()
            if rec.state not in ("draft", "failed"):
                raise UserError(
                    _("Only Draft or Failed cohorts can be generated.")
                )

            rec.with_context(
                clinic_analytics_internal=True
            ).write({
                "state": "running",
                "error_message": False,
            })
            try:
                result = Engine.retention_cohort(
                    rec.company_id,
                    rec.branch_id,
                    rec.cohort_start,
                )
                rec.with_context(
                    clinic_analytics_internal=True
                ).write({
                    "state": "done",
                    "cohort_start": result["cohort_start"],
                    "cohort_end": result["cohort_end"],
                    "cohort_size": result["cohort_size"],
                    "retained_30": result["retained_30"],
                    "retained_60": result["retained_60"],
                    "retained_90": result["retained_90"],
                    "retention_30": result["retention_30"],
                    "retention_60": result["retention_60"],
                    "retention_90": result["retention_90"],
                    "source_booking_count": result["source_count"],
                    "generated_at": fields.Datetime.now(),
                    "generated_by_id": self.env.user.id,
                })
            except Exception as exc:
                rec.with_context(
                    clinic_analytics_internal=True
                ).write({
                    "state": "failed",
                    "error_message": str(exc)[:4000],
                })
                continue

            rec._generate_retention_insight()
            Bridge = self.env[
                "clinic.analytics.integration.service"
            ]
            Bridge.emit_audit(
                rec,
                "custom",
                _("Retention cohort generated."),
            )
            Bridge.publish_event(
                rec,
                "analytics.cohort.ready",
                {
                    "cohort_start": str(rec.cohort_start),
                    "cohort_size": rec.cohort_size,
                    "retention_30": rec.retention_30,
                    "retention_60": rec.retention_60,
                    "retention_90": rec.retention_90,
                },
            )
        return True

    def _generate_retention_insight(self):
        Insight = self.env["clinic.analytics.insight"]
        for rec in self:
            rec.insight_ids.filtered(
                lambda insight: insight.state
                not in ("resolved", "dismissed")
            ).sudo().with_context(
                clinic_analytics_internal=True
            ).unlink()

            if not rec.cohort_size:
                return
            if rec.retention_90 >= 50.0:
                return

            severity = (
                "critical"
                if rec.retention_90 < 25.0
                else "warning"
            )
            Insight.with_context(
                clinic_analytics_internal=True
            ).create({
                "company_id": rec.company_id.id,
                "branch_id": (
                    rec.branch_id.id
                    if rec.branch_id
                    else False
                ),
                "source_type": "cohort",
                "cohort_id": rec.id,
                "severity": severity,
                "title": _("Patient retention signal"),
                "narrative": _(
                    "The %s cohort has %.2f%% 90-day repeat-booking "
                    "retention across %s new patients."
                )
                % (
                    rec.cohort_start,
                    rec.retention_90,
                    rec.cohort_size,
                ),
                "recommendation": _(
                    "Review post-care, membership, feedback and marketing "
                    "journeys for this branch before choosing interventions."
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

    def action_view_insights(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Analytics Insights"),
            "res_model": "clinic.analytics.insight",
            "view_mode": "list,form",
            "domain": [("cohort_id", "=", self.id)],
        }

