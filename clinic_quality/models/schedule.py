from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .scope_mixin import QUALITY_SCHEDULE_TRANSITION_TOKEN


QUALITY_SCHEDULE_STATES = [
    ("active", "Active"),
    ("paused", "Paused"),
]

QUALITY_RECURRENCES = [
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("annual", "Annual"),
]


class ClinicQualitySchedule(models.Model):
    """Recurring Quality Check planner.

    Cron creates governed Draft Quality Checks only. It does not auto-start,
    auto-score, auto-close, or mutate source business workflows.
    """

    _name = "clinic.quality.schedule"
    _description = "Clinic Quality Check Schedule"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.quality.scope.mixin",
    ]
    _order = "next_run_date, name, id"
    _check_company_auto = True

    _interval_positive = models.Constraint(
        "CHECK(interval_count > 0)",
        "Quality Schedule Interval must be greater than zero.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, next_run_date)"
    )

    name = fields.Char(
        required=True,
        index=True,
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )
    state = fields.Selection(
        QUALITY_SCHEDULE_STATES,
        default="paused",
        required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    template_id = fields.Many2one(
        "clinic.quality.check.template",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned Inspector",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )
    reviewer_user_id = fields.Many2one(
        "res.users",
        string="Reviewer / Approver",
        index=True,
        tracking=True,
    )

    recurrence = fields.Selection(
        QUALITY_RECURRENCES,
        required=True,
        default="monthly",
        index=True,
        tracking=True,
    )
    interval_count = fields.Integer(
        default=1,
        required=True,
        tracking=True,
    )
    next_run_date = fields.Date(
        required=True,
        default=fields.Date.today,
        index=True,
        tracking=True,
    )
    last_run_date = fields.Date(
        readonly=True,
        index=True,
    )
    last_check_id = fields.Many2one(
        "clinic.quality.check",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    last_error = fields.Text(
        readonly=True,
        copy=False,
    )

    check_ids = fields.One2many(
        "clinic.quality.check",
        "schedule_id",
        string="Generated Quality Checks",
        readonly=True,
    )
    check_count = fields.Integer(
        compute="_compute_check_count",
    )

    @api.depends("check_ids")
    def _compute_check_count(self):
        for schedule in self:
            schedule.check_count = len(schedule.check_ids)

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_manager()

        prepared = []
        for original in vals_list:
            vals = dict(original)
            template = self.env[
                "clinic.quality.check.template"
            ].browse(vals.get("template_id")).exists()

            if not template:
                raise ValidationError(
                    _("A valid Quality Template is required.")
                )

            vals["company_id"] = template.company_id.id
            vals.setdefault("scope_type", template.scope_type)
            vals.setdefault(
                "reviewer_user_id",
                template.company_id.clinic_quality_default_approver_id.id
                if template.company_id.clinic_quality_default_approver_id
                else False,
            )
            prepared.append(vals)

        schedules = super().create(prepared)
        schedules._check_schedule_contract()
        return schedules

    def write(self, vals):
        vals = dict(vals)

        if (
            "state" in vals
            or "active" in vals
            or "last_run_date" in vals
            or "last_check_id" in vals
            or "last_error" in vals
        ) and not self.env.context.get("quality_schedule_transition") is QUALITY_SCHEDULE_TRANSITION_TOKEN:
            raise AccessError(
                _("Use Quality Schedule actions to change lifecycle/run evidence.")
            )

        material_fields = {
            "template_id",
            "company_id",
            "branch_id",
            "scope_type",
            "room_id",
            "staff_id",
            "doctor_id",
            "stock_lot_id",
            "treatment_id",
            "assigned_user_id",
            "reviewer_user_id",
            "recurrence",
            "interval_count",
            "next_run_date",
        }
        if (
            material_fields.intersection(vals)
            and self.filtered(
                lambda schedule: schedule.state == "active"
            )
            and not self.env.context.get("quality_schedule_transition") is QUALITY_SCHEDULE_TRANSITION_TOKEN
        ):
            raise AccessError(
                _("Pause an Active Quality Schedule before changing its setup.")
            )

        if not self.env.context.get("quality_schedule_transition") is QUALITY_SCHEDULE_TRANSITION_TOKEN:
            self._quality_require_manager()

        result = super().write(vals)
        self._check_schedule_contract()
        return result

    def unlink(self):
        self._quality_require_manager()

        if self.filtered(
            lambda schedule:
            schedule.state == "active"
            or schedule.check_ids
        ):
            raise UserError(
                _(
                    "Only an unused Paused Quality Schedule may be deleted. "
                    "Keep generated-check provenance."
                )
            )
        return super().unlink()

    @api.constrains(
        "template_id",
        "company_id",
        "branch_id",
        "scope_type",
        "assigned_user_id",
        "reviewer_user_id",
        "interval_count",
        "next_run_date",
    )
    def _check_schedule_contract(self):
        for schedule in self:
            schedule._check_quality_scope()

            if schedule.template_id.company_id != schedule.company_id:
                raise ValidationError(
                    _("Quality Schedule Template belongs to another company.")
                )
            if (
                schedule.company_id.policy_branch_scope_incident_event
                and not schedule.branch_id
            ):
                raise ValidationError(
                    _(
                        "This company requires Branch scope for Incident "
                        "governance. Select a Quality Branch before activating "
                        "the Schedule."
                    )
                )
            if schedule.scope_type != schedule.template_id.scope_type:
                raise ValidationError(
                    _(
                        "Schedule Scope Type must match "
                        "the Quality Template Scope Type."
                    )
                )
            if schedule.template_id.branch_ids and not schedule.branch_id:
                raise ValidationError(
                    _(
                        "This Template is Branch-restricted. "
                        "Select one of its Applicable Branches."
                    )
                )
            if (
                schedule.template_id.branch_ids
                and schedule.branch_id not in schedule.template_id.branch_ids
            ):
                raise ValidationError(
                    _(
                        "Schedule Branch is not within "
                        "the Template applicability."
                    )
                )
            if schedule.interval_count <= 0:
                raise ValidationError(
                    _("Schedule Interval must be greater than zero.")
                )

            for role_name, user in (
                (_("Assigned Inspector"), schedule.assigned_user_id),
                (_("Reviewer / Approver"), schedule.reviewer_user_id),
            ):
                if user and schedule.company_id not in user.company_ids:
                    raise ValidationError(
                        _(
                            "%(role)s does not have access "
                            "to the Schedule company."
                        ) % {"role": role_name}
                    )

            if schedule.assigned_user_id and not schedule.assigned_user_id.has_group(
                "clinic_quality.group_quality_inspector"
            ):
                raise ValidationError(
                    _(
                        "Assigned Inspector must belong to the "
                        "Quality Inspector role."
                    )
                )
            if schedule.reviewer_user_id and not schedule.reviewer_user_id.has_group(
                "clinic_quality.group_quality_approver"
            ):
                raise ValidationError(
                    _(
                        "Reviewer / Approver must belong to the "
                        "Quality Approver role."
                    )
                )

    def _next_quality_date(self, base_date):
        self.ensure_one()

        count = self.interval_count
        if self.recurrence == "daily":
            return base_date + relativedelta(days=count)
        if self.recurrence == "weekly":
            return base_date + relativedelta(weeks=count)
        if self.recurrence == "monthly":
            return base_date + relativedelta(months=count)
        if self.recurrence == "quarterly":
            return base_date + relativedelta(months=3 * count)
        if self.recurrence == "annual":
            return base_date + relativedelta(years=count)
        raise ValidationError(_("Unsupported Quality recurrence."))

    def _prepare_quality_check_vals(self):
        self.ensure_one()

        return {
            "template_id": self.template_id.id,
            "company_id": self.company_id.id,
            "branch_id": (
                self.branch_id.id
                if self.branch_id
                else False
            ),
            "scope_type": self.scope_type,
            "room_id": self.room_id.id if self.room_id else False,
            "staff_id": self.staff_id.id if self.staff_id else False,
            "doctor_id": self.doctor_id.id if self.doctor_id else False,
            "stock_lot_id": (
                self.stock_lot_id.id
                if self.stock_lot_id
                else False
            ),
            "treatment_id": (
                self.treatment_id.id
                if self.treatment_id
                else False
            ),
            "planned_date": self.next_run_date or fields.Date.today(),
            "performed_by_user_id": self.assigned_user_id.id,
            "reviewed_by_user_id": (
                self.reviewer_user_id.id
                if self.reviewer_user_id
                else False
            ),
            "schedule_id": self.id,
            "title": _("%(template)s — Scheduled %(date)s") % {
                "template": self.template_id.name,
                "date": self.next_run_date or fields.Date.today(),
            },
        }

    def _run_quality_schedule_once(self):
        self.ensure_one()

        if self.state != "active":
            raise UserError(_("Only an Active Quality Schedule can run."))
        if self.template_id.state != "active":
            raise UserError(
                _("The Quality Schedule Template is not Active.")
            )

        check_env = (
            self.env["clinic.quality.check"]
            .with_user(self.assigned_user_id)
            .with_company(self.company_id)
        )
        check = check_env.create(
            self._prepare_quality_check_vals()
        )

        base_date = self.next_run_date or fields.Date.today()
        self.with_context(
            quality_schedule_transition=QUALITY_SCHEDULE_TRANSITION_TOKEN
        ).write({
            "last_run_date": fields.Date.today(),
            "last_check_id": check.id,
            "last_error": False,
            "next_run_date": self._next_quality_date(base_date),
        })

        self.message_post(
            body=_(
                "Generated Quality Check %(check)s for %(date)s."
            ) % {
                "check": check.display_name,
                "date": base_date,
            }
        )
        return check

    def action_run_now(self):
        self._quality_require_manager()
        self.ensure_one()

        check = self._run_quality_schedule_once()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Quality Check"),
            "res_model": "clinic.quality.check",
            "view_mode": "form",
            "res_id": check.id,
        }

    def action_resume(self):
        self._quality_require_manager()

        for schedule in self:
            if schedule.state == "active":
                continue
            if schedule.template_id.state != "active":
                raise UserError(
                    _("Activate the Quality Template before resuming Schedule.")
                )
            schedule.with_context(
                quality_schedule_transition=QUALITY_SCHEDULE_TRANSITION_TOKEN
            ).write({
                "state": "active",
                "active": True,
            })
        return True

    def action_pause(self):
        self._quality_require_manager()

        for schedule in self:
            if schedule.state == "paused":
                continue
            schedule.with_context(
                quality_schedule_transition=QUALITY_SCHEDULE_TRANSITION_TOKEN
            ).write({
                "state": "paused",
            })
        return True

    def action_open_checks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scheduled Quality Checks"),
            "res_model": "clinic.quality.check",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("schedule_id", "=", self.id)],
            "context": {"default_schedule_id": self.id},
        }

    def action_open_last_check(self):
        self.ensure_one()
        if not self.last_check_id:
            raise UserError(_("No Quality Check has been generated yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Last Quality Check"),
            "res_model": "clinic.quality.check",
            "view_mode": "form",
            "res_id": self.last_check_id.id,
        }

    @api.model
    def _cron_generate_due_quality_checks(self):
        today = fields.Date.today()

        schedules = self.sudo().search([
            ("state", "=", "active"),
            ("active", "=", True),
            ("next_run_date", "<=", today),
        ], order="next_run_date, id")

        for schedule in schedules:
            try:
                with self.env.cr.savepoint():
                    schedule._run_quality_schedule_once()
            except Exception as exc:
                # A failing schedule must not abort all due schedules and must
                # not retry endlessly in the same cron cycle.
                next_date = schedule._next_quality_date(
                    schedule.next_run_date or today
                )
                schedule.with_context(
                    quality_schedule_transition=QUALITY_SCHEDULE_TRANSITION_TOKEN
                ).write({
                    "last_run_date": today,
                    "last_error": str(exc)[:4000],
                    "next_run_date": next_date,
                })
                schedule.message_post(
                    body=_(
                        "Quality Schedule run failed and was advanced "
                        "to the next recurrence. Error: %s"
                    ) % str(exc)
                )
        return True
