# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicAnalyticsSnapshot(models.Model):
    _name = "clinic.analytics.snapshot"
    _description = "Clinic Analytics KPI Snapshot"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.analytics.scope.mixin",
    ]
    _order = "date_to desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        default=lambda self: _("New"),
        copy=False,
        readonly=True,
        index=True,
    )
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)
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
    generated_at = fields.Datetime(readonly=True, index=True)
    generated_by_id = fields.Many2one(
        "res.users",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        "clinic.analytics.snapshot.line",
        "snapshot_id",
        string="KPI Lines",
        copy=False,
    )
    line_count = fields.Integer(compute="_compute_counts")
    warning_count = fields.Integer(compute="_compute_counts")
    critical_count = fields.Integer(compute="_compute_counts")
    insight_ids = fields.One2many(
        "clinic.analytics.insight",
        "snapshot_id",
        string="Insights",
        readonly=True,
    )
    insight_count = fields.Integer(compute="_compute_counts")
    source_dashboard_snapshot_id = fields.Many2one(
        "clinic.dashboard.snapshot",
        string="Related Dashboard Snapshot",
        ondelete="set null",
    )
    notes = fields.Text()

    _date_order = models.Constraint(
        "CHECK(date_from <= date_to)",
        "Analytics snapshot From Date must not be after To Date.",
    )

    @api.depends(
        "line_ids",
        "line_ids.status",
        "insight_ids",
    )
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.warning_count = len(
                rec.line_ids.filtered(
                    lambda line: line.status == "warning"
                )
            )
            rec.critical_count = len(
                rec.line_ids.filtered(
                    lambda line: line.status == "critical"
                )
            )
            rec.insight_count = len(rec.insight_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = (
                    sequence.next_by_code(
                        "clinic.analytics.snapshot"
                    )
                    or _("New")
                )
        records = super().create(vals_list)
        records._ensure_scope_authorized()
        return records

    def write(self, vals):
        if not self.env.context.get("clinic_analytics_internal"):
            locked = self.filtered(lambda rec: rec.state == "done")
            protected = {
                "company_id",
                "branch_id",
                "date_from",
                "date_to",
                "line_ids",
            }
            if locked and protected.intersection(vals):
                raise AccessError(
                    _("Ready analytics snapshots are immutable.")
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda rec: rec.state == "done"):
            raise AccessError(
                _("Ready analytics snapshots cannot be deleted.")
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

    def action_generate(self):
        self._require_analyst()
        Engine = self.env["clinic.analytics.engine"]
        Line = self.env["clinic.analytics.snapshot.line"]

        for rec in self:
            rec._ensure_scope_authorized()
            if rec.state not in ("draft", "failed"):
                raise UserError(
                    _("Only Draft or Failed snapshots can be generated.")
                )

            rec.with_context(
                clinic_analytics_internal=True
            ).write({
                "state": "running",
                "error_message": False,
            })

            try:
                with self.env.cr.savepoint():
                    rec.line_ids.with_context(
                        clinic_analytics_internal=True
                    ).unlink()

                    kpis = self.env[
                        "clinic.analytics.kpi"
                    ].search(
                        [
                            ("state", "=", "active"),
                            ("active", "=", True),
                        ],
                        order="sequence, id",
                    )

                    for kpi in kpis:
                        result = Engine.evaluate(
                            kpi.source_key,
                            rec.company_id,
                            rec.branch_id,
                            rec.date_from,
                            rec.date_to,
                        )

                        previous = Line.search(
                            [
                                ("kpi_id", "=", kpi.id),
                                ("company_id", "=", rec.company_id.id),
                                (
                                    "branch_id",
                                    "=",
                                    rec.branch_id.id
                                    if rec.branch_id
                                    else False,
                                ),
                                ("snapshot_id.state", "=", "done"),
                                ("date_to", "<", rec.date_from),
                            ],
                            order="date_to desc, id desc",
                            limit=1,
                        )
                        previous_value = (
                            previous.value
                            if previous
                            else 0.0
                        )
                        trend_percent = (
                            (
                                (
                                    result["value"]
                                    - previous_value
                                )
                                / abs(previous_value)
                                * 100.0
                            )
                            if previous and abs(previous_value) > 1e-9
                            else 0.0
                        )

                        Line.with_context(
                            clinic_analytics_internal=True
                        ).create({
                            "snapshot_id": rec.id,
                            "kpi_id": kpi.id,
                            "value": result["value"],
                            "previous_value": previous_value,
                            "has_previous": bool(previous),
                            "trend_percent": trend_percent,
                            "status": kpi.evaluate_status(
                                result["value"]
                            ),
                            "source_model": result[
                                "source_model"
                            ],
                            "source_count": result[
                                "source_count"
                            ],
                            "source_domain_json": result[
                                "source_domain_json"
                            ],
                            "note": result.get(
                                "note", ""
                            ),
                        })

                    rec.with_context(
                        clinic_analytics_internal=True
                    ).write({
                        "state": "done",
                        "generated_at": fields.Datetime.now(),
                        "generated_by_id": self.env.user.id,
                        "error_message": False,
                    })
            except Exception as exc:
                rec.with_context(
                    clinic_analytics_internal=True
                ).write({
                    "state": "failed",
                    "error_message": str(exc)[:4000],
                })
                continue

            if (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param(
                    "clinic.analytics.auto_generate_insights",
                    "true",
                )
                .strip()
                .lower()
                in {"1", "true", "yes", "on"}
            ):
                rec.action_generate_insights()

            Bridge = self.env[
                "clinic.analytics.integration.service"
            ]
            Bridge.emit_audit(
                rec,
                "custom",
                _("Analytics snapshot generated."),
            )
            Bridge.publish_event(
                rec,
                "analytics.snapshot.ready",
                {
                    "date_from": str(rec.date_from),
                    "date_to": str(rec.date_to),
                    "line_count": rec.line_count,
                    "warning_count": rec.warning_count,
                    "critical_count": rec.critical_count,
                },
            )
        return True

    def action_generate_insights(self):
        self._require_analyst()
        Insight = self.env["clinic.analytics.insight"]
        for rec in self:
            if rec.state != "done":
                raise UserError(
                    _("Generate the snapshot before creating insights.")
                )
            existing = rec.insight_ids.filtered(
                lambda insight: insight.state
                not in ("resolved", "dismissed")
            )
            existing.sudo().with_context(
                clinic_analytics_internal=True
            ).unlink()

            for line in rec.line_ids.filtered(
                lambda value: value.status
                in ("warning", "critical")
            ):
                recommendation = (
                    _(
                        "Review the underlying source records and operational "
                        "drivers before taking corrective action."
                    )
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
                    "source_type": "snapshot",
                    "snapshot_id": rec.id,
                    "snapshot_line_id": line.id,
                    "kpi_id": line.kpi_id.id,
                    "severity": (
                        "critical"
                        if line.status == "critical"
                        else "warning"
                    ),
                    "title": _("%s threshold signal")
                    % line.kpi_id.name,
                    "narrative": _(
                        "KPI %s produced value %s for %s to %s."
                    )
                    % (
                        line.kpi_id.name,
                        line.display_value,
                        rec.date_from,
                        rec.date_to,
                    ),
                    "recommendation": recommendation,
                })
        return True

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

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("KPI Snapshot Lines"),
            "res_model": "clinic.analytics.snapshot.line",
            "view_mode": "list,graph,pivot,form",
            "domain": [("snapshot_id", "=", self.id)],
        }

    def action_view_insights(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Analytics Insights"),
            "res_model": "clinic.analytics.insight",
            "view_mode": "list,form",
            "domain": [("snapshot_id", "=", self.id)],
        }

    def action_open_dashboards(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "active"),
        ]
        if self.branch_id:
            domain += [
                "|",
                ("default_branch_id", "=", False),
                ("default_branch_id", "=", self.branch_id.id),
            ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Related Dashboard Boards"),
            "res_model": "clinic.dashboard.board",
            "view_mode": "list,form",
            "domain": domain,
        }
