from datetime import timedelta
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)


class ClinicReportSchedule(models.Model):
    """Recurring governed report execution without changing source transactions."""

    _name = "clinic.report.schedule"
    _description = "Clinic Report Schedule"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.report.company.mixin",
    ]
    _order = "next_run_at, name, id"
    _check_company_auto = True

    _name_company_unique = models.Constraint(
        "UNIQUE(company_id, name)",
        "Report Schedule name must be unique per company.",
    )
    _window_positive = models.Constraint(
        "CHECK(window_days >= 1)",
        "Scheduled Report window must be at least one day.",
    )
    _company_next_idx = models.Index("(company_id, state, next_run_at)")

    name = fields.Char(required=True, tracking=True, index=True)
    definition_id = fields.Many2one(
        "clinic.report.definition",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('state', '=', 'active')]",
    )
    family = fields.Selection(
        related="definition_id.family",
        store=True,
        readonly=True,
        index=True,
    )
    report_key = fields.Selection(
        related="definition_id.report_key",
        store=True,
        readonly=True,
        index=True,
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
    window_days = fields.Integer(
        default=30,
        required=True,
        help="Rolling number of calendar days included in each generated report.",
    )
    include_details = fields.Boolean(default=True)
    detail_limit = fields.Integer(default=500)

    owner_user_id = fields.Many2one(
        "res.users",
        string="Report Owner",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    next_run_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
    )
    last_run_at = fields.Datetime(readonly=True)
    last_run_id = fields.Many2one(
        "clinic.report.run",
        readonly=True,
        ondelete="set null",
    )
    run_count = fields.Integer(compute="_compute_run_count")

    state = fields.Selection(
        [
            ("active", "Active"),
            ("paused", "Paused"),
        ],
        default="paused",
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    @api.constrains("definition_id", "branch_id")
    def _check_definition_branch(self):
        for record in self:
            if (
                record.branch_id
                and record.definition_id
                and not record.definition_id.allow_branch_filter
            ):
                raise ValidationError(
                    _("This Report Definition does not support Branch scheduling.")
                )

    @api.constrains("owner_user_id")
    def _check_owner_user(self):
        for record in self:
            if record.owner_user_id and not record.owner_user_id.has_group(
                "clinic_reports.group_reports_analyst"
            ):
                raise ValidationError(
                    _("Scheduled Report owner must be a Reports Analyst or Manager.")
                )

    @api.constrains("detail_limit")
    def _check_detail_limit(self):
        for record in self:
            if not 1 <= record.detail_limit <= 10000:
                raise ValidationError(
                    _("Detail Limit must be between 1 and 10,000 rows.")
                )

    def _compute_run_count(self):
        Run = self.env["clinic.report.run"]
        for record in self:
            record.run_count = Run.search_count(
                [("schedule_id", "=", record.id)]
            )

    def write(self, vals):
        if "state" in vals and not self.env.context.get("report_schedule_transition"):
            raise AccessError(
                _("Use Report Schedule workflow actions to change status.")
            )
        return super().write(vals)

    def _next_occurrence(self, current=None):
        self.ensure_one()
        current = fields.Datetime.to_datetime(
            current or self.next_run_at or fields.Datetime.now()
        )
        if self.cadence == "daily":
            return current + timedelta(days=1)
        if self.cadence == "weekly":
            return current + timedelta(weeks=1)
        return current + relativedelta(months=1)

    # Schedules create ordinary governed Report Runs so scheduled and manual output share one audit model.
    def _create_run(self, execute=True):
        self.ensure_one()
        if self.definition_id.state != "active":
            raise UserError(_("Scheduled Report Definition must be Active."))

        date_to = fields.Date.context_today(self)
        date_from = date_to - timedelta(days=max(self.window_days, 1) - 1)

        run = self.env["clinic.report.run"].create({
            "definition_id": self.definition_id.id,
            "company_id": self.company_id.id,
            "branch_id": self.branch_id.id or False,
            "date_from": date_from,
            "date_to": date_to,
            "include_details": self.include_details,
            "detail_limit": self.detail_limit,
            "schedule_id": self.id,
        })

        if execute:
            run.with_user(self.owner_user_id).action_generate()
            run.invalidate_recordset(["state"])
            if (
                run.state == "ready"
                and self.company_id.clinic_reports_auto_finalize_scheduled
            ):
                run.sudo().action_finalize()

        self.last_run_id = run.id
        self.last_run_at = fields.Datetime.now()
        return run

    def action_run_now(self):
        self._reports_require_group(
            "clinic_reports.group_reports_manager",
            _("Only a Reports Manager can run schedules manually."),
        )
        self.ensure_one()
        run = self._create_run(execute=True)
        return {
            "type": "ir.actions.act_window",
            "name": _("Scheduled Report Run"),
            "res_model": "clinic.report.run",
            "view_mode": "form",
            "res_id": run.id,
        }

    def action_resume(self):
        self._reports_require_group(
            "clinic_reports.group_reports_manager",
            _("Only a Reports Manager can resume schedules."),
        )
        for record in self:
            record.with_context(report_schedule_transition=True).write({
                "state": "active",
                "next_run_at": record.next_run_at or fields.Datetime.now(),
            })
        return True

    def action_pause(self):
        self._reports_require_group(
            "clinic_reports.group_reports_manager",
            _("Only a Reports Manager can pause schedules."),
        )
        self.with_context(report_schedule_transition=True).write({"state": "paused"})
        return True

    def action_view_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scheduled Report Runs"),
            "res_model": "clinic.report.run",
            "view_mode": "list,form",
            "domain": [("schedule_id", "=", self.id)],
        }

    @api.model
    # Cron advances the recurrence after each attempt; it never loops indefinitely on one failing schedule.
    def _cron_run_due_schedules(self):
        now = fields.Datetime.now()
        schedules = self.sudo().search([
            ("active", "=", True),
            ("state", "=", "active"),
            ("next_run_at", "<=", now),
        ])

        for schedule in schedules:
            next_run_at = schedule._next_occurrence(
                schedule.next_run_at or now
            )
            try:
                # One broken schedule must not abort every due report in the
                # same hourly cron transaction.
                with self.env.cr.savepoint():
                    schedule._create_run(execute=True)
            except Exception as exc:
                _logger.exception(
                    "ClinicOne scheduled report failed: %s",
                    schedule.display_name,
                )
                schedule.message_post(
                    body=_("Scheduled report generation failed: %s") % str(exc)
                )
            finally:
                schedule.next_run_at = next_run_at
        return True

