from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicPostcareTask(models.Model):
    """Concrete follow-up work item; technical name preserves clinic_staff contract."""

    _name = "clinic.postcare.task"
    _description = "Clinic Post-Care Task"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.postcare.company.mixin"]
    _order = "due_datetime, priority desc, id"
    _check_company_auto = True

    _timing_nonnegative = models.Constraint(
        "CHECK(escalation_after_hours >= 0)",
        "Post-Care escalation delay cannot be negative.",
    )
    _plan_due_idx = models.Index("(company_id, plan_id, state, due_datetime)")
    _assignee_due_idx = models.Index("(company_id, assignee_id, state, due_datetime)")

    reference = fields.Char(default="/", readonly=True, copy=False, index=True)
    name = fields.Char(required=True, tracking=True, index=True)
    plan_id = fields.Many2one(
        "clinic.postcare.plan",
        required=True,
        check_company=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    protocol_step_id = fields.Many2one(
        "clinic.postcare.protocol.step",
        string="Protocol Step",
        ondelete="set null",
        index=True,
    )
    patient_id = fields.Many2one(
        related="plan_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="plan_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="plan_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="plan_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )
    assignee_id = fields.Many2one(
        "clinic.staff",
        string="Assigned Staff",
        check_company=True,
        ondelete="set null",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )

    task_type = fields.Selection(
        [
            ("instruction", "Care Instruction"),
            ("reminder", "Reminder"),
            ("checkin", "Patient Check-in"),
            ("call", "Follow-up Call"),
            ("medication", "Medication Follow-up"),
            ("wound", "Wound / Recovery Review"),
            ("review", "Clinical Review"),
        ],
        default="reminder",
        required=True,
        tracking=True,
        index=True,
    )
    channel = fields.Selection(
        [
            ("email", "Email"),
            ("phone", "Phone"),
            ("internal", "Internal Task"),
            ("manual", "Manual Contact"),
        ],
        default="email",
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Important"), ("2", "Urgent"), ("3", "Very Urgent")],
        default="0",
        required=True,
        tracking=True,
    )

    due_datetime = fields.Datetime(required=True, tracking=True, index=True)
    response_required = fields.Boolean(default=False)
    response_due_datetime = fields.Datetime(index=True)
    auto_send = fields.Boolean(default=True)
    instruction_html = fields.Html(sanitize=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("scheduled", "Scheduled"),
            ("due", "Due"),
            ("sent", "Reminder Sent"),
            ("contacted", "Contacted"),
            ("completed", "Completed"),
            ("overdue", "Overdue"),
            ("escalated", "Escalated"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    sent_at = fields.Datetime(readonly=True)
    contacted_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    completed_by_id = fields.Many2one("res.users", readonly=True)
    send_count = fields.Integer(default=0, readonly=True)

    escalate_if_overdue = fields.Boolean(default=True)
    escalation_after_hours = fields.Integer(default=24)
    escalation_severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
    )

    checkin_ids = fields.One2many(
        "clinic.postcare.checkin",
        "task_id",
        string="Check-ins",
        copy=False,
    )
    escalation_ids = fields.One2many(
        "clinic.postcare.escalation",
        "task_id",
        string="Escalations",
        copy=False,
    )
    checkin_count = fields.Integer(compute="_compute_counts")
    escalation_count = fields.Integer(compute="_compute_counts")
    is_overdue = fields.Boolean(
        compute="_compute_is_overdue",
        store=True,
        index=True,
    )
    completed_on_time = fields.Boolean(
        compute="_compute_completed_on_time",
        store=True,
        index=True,
    )

    @api.depends("checkin_ids", "escalation_ids")
    def _compute_counts(self):
        for record in self:
            record.checkin_count = len(record.checkin_ids)
            record.escalation_count = len(record.escalation_ids)

    @api.depends("state")
    def _compute_is_overdue(self):
        for record in self:
            record.is_overdue = record.state in ("overdue", "escalated")

    @api.depends("state", "completed_at", "due_datetime")
    def _compute_completed_on_time(self):
        for record in self:
            record.completed_on_time = bool(
                record.state == "completed"
                and record.completed_at
                and record.due_datetime
                and record.completed_at <= record.due_datetime
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            plan = self.env["clinic.postcare.plan"].browse(vals.get("plan_id"))
            if plan.exists():
                # Company/Branch are readonly related fields from the Plan.
                vals.setdefault("assignee_id", plan.responsible_staff_id.id or False)
            company = plan.company_id if plan.exists() else self.env.company
            if vals.get("reference") in (False, "/"):
                vals["reference"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.postcare.task")
                    or "/"
                )
            prepared.append(vals)
        return super().create(prepared)

    @api.constrains("assignee_id", "company_id", "plan_id", "protocol_step_id")
    def _check_task_scope(self):
        for record in self:
            if record.assignee_id and record.assignee_id.company_id != record.company_id:
                raise ValidationError(_("Assigned Post-Care Staff must belong to the Task company."))
            if record.plan_id.company_id != record.company_id:
                raise ValidationError(_("Post-Care Task and Plan company must match."))
            if (
                record.protocol_step_id
                and record.protocol_step_id.protocol_id != record.plan_id.protocol_id
            ):
                raise ValidationError(_("Protocol Step must belong to the Plan Protocol."))

    def write(self, vals):
        workflow_fields = {
            "state",
            "sent_at",
            "contacted_at",
            "completed_at",
            "completed_by_id",
            "send_count",
        }
        if workflow_fields.intersection(vals) and not self.env.context.get("postcare_transition"):
            raise AccessError(_("Use Post-Care Task workflow actions to update status/contact evidence."))
        if {
            "plan_id",
            "company_id",
            "branch_id",
            "protocol_step_id",
            "due_datetime",
        }.intersection(vals):
            for record in self:
                if record.state not in ("pending", "scheduled"):
                    raise UserError(_("Task scope/timing can only be edited before contact starts."))
        return super().write(vals)

    # clinic.staff links through res.partner; activities resolve the matching internal user when available.
    def _assignee_user(self):
        self.ensure_one()
        if not self.assignee_id or not self.assignee_id.partner_id:
            return self.create_uid
        return self.env["res.users"].search(
            [("partner_id", "=", self.assignee_id.partner_id.id)],
            limit=1,
        ) or self.create_uid

    # Non-email follow-up becomes a real staff activity rather than a falsely reported patient delivery.
    def _schedule_staff_activity(self):
        for record in self:
            user = record._assignee_user()
            deadline = fields.Date.to_date(record.due_datetime or fields.Datetime.now())
            existing = record.activity_ids.filtered(
                lambda activity:
                    activity.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
                    and activity.user_id == user
            )
            if not existing:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=deadline,
                    user_id=user.id,
                    summary=_("Post-Care Follow-up: %s") % record.name,
                    note=record.instruction_html or "",
                )

    def action_schedule(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can schedule Tasks."),
        )
        for record in self:
            if record.state != "pending":
                raise UserError(_("Only Pending Tasks can be scheduled."))
            record.with_context(postcare_transition=True).write({"state": "scheduled"})
        return True

    # Email is the only delivery channel automated by this addon without a future provider dependency.
    def _send_email_reminder(self):
        template = self.env.ref(
            "clinic_post_care_followup.mail_template_postcare_task",
            raise_if_not_found=False,
        )
        for record in self:
            if record.channel != "email":
                raise UserError(_("Automatic sending is supported only for Email tasks."))
            if not record.partner_id.email:
                raise UserError(_("Patient contact has no email address."))
            if not template:
                raise UserError(_("Post-Care reminder email template is not configured."))
            template.sudo().send_mail(record.id, force_send=True)
            record.with_context(postcare_transition=True).write({
                "state": "sent",
                "sent_at": fields.Datetime.now(),
                "send_count": record.send_count + 1,
            })
            record.message_post(body=_("Post-Care email reminder sent to %s.") % record.partner_id.email)
        return True

    def action_send_reminder(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can send reminders."),
        )
        return self._send_email_reminder()

    def action_mark_due(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can mark Tasks due."),
        )
        for record in self:
            if record.state not in ("pending", "scheduled"):
                raise UserError(_("Only Pending/Scheduled Tasks can become Due."))
            record.with_context(postcare_transition=True).write({"state": "due"})
            record._schedule_staff_activity()
        return True

    def action_mark_contacted(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can record patient contact."),
        )
        for record in self:
            if record.state in ("completed", "cancelled"):
                raise UserError(_("Completed/Cancelled Tasks cannot be marked Contacted."))
            record.with_context(postcare_transition=True).write({
                "state": "contacted",
                "contacted_at": fields.Datetime.now(),
            })
        return True

    # Required-response Tasks cannot close until structured Check-in evidence exists.
    def action_complete(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can complete Tasks."),
        )
        for record in self:
            if record.state == "cancelled":
                raise UserError(_("Cancelled Tasks cannot be completed."))
            if record.response_required and not record.checkin_ids:
                raise UserError(_("Record a Patient Check-in before completing this required-response Task."))
            record.with_context(postcare_transition=True).write({
                "state": "completed",
                "completed_at": fields.Datetime.now(),
                "completed_by_id": self.env.user.id,
            })
            record.activity_ids.action_done()
        return True

    def action_cancel(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can cancel Tasks."),
        )
        self.with_context(postcare_transition=True).write({"state": "cancelled"})
        return True

    # One open escalation per Task prevents cron retries from multiplying clinical attention records.
    def _ensure_escalation(self, reason=None):
        Escalation = self.env["clinic.postcare.escalation"]
        for record in self:
            existing = Escalation.search([
                ("task_id", "=", record.id),
                ("state", "not in", ("resolved", "cancelled")),
            ], limit=1)
            if existing:
                continue
            Escalation.create({
                "plan_id": record.plan_id.id,
                "task_id": record.id,
                "severity": record.escalation_severity,
                "reason": reason or _("Post-Care Task is overdue."),
                "owner_staff_id": (
                    record.assignee_id.id
                    or record.plan_id.responsible_staff_id.id
                    or False
                ),
            })

    def action_escalate(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can escalate Tasks."),
        )
        for record in self:
            if record.state in ("completed", "cancelled"):
                raise UserError(_("Completed/Cancelled Tasks cannot be escalated."))
            record._ensure_escalation()
            record.with_context(postcare_transition=True).write({"state": "escalated"})
        return True

    def action_new_checkin(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Patient Check-in"),
            "res_model": "clinic.postcare.checkin",
            "view_mode": "form",
            "context": {
                "default_plan_id": self.plan_id.id,
                "default_task_id": self.id,
                "default_patient_id": self.patient_id.id,
            },
        }

    def action_open_plan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plan"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "form",
            "res_id": self.plan_id.id,
        }

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

    @api.model
    # Hourly housekeeping moves work through due/overdue states and sends only supported email reminders.
    def _cron_process_due_tasks(self):
        now = fields.Datetime.now()
        due = self.sudo().search([
            ("state", "in", ("pending", "scheduled")),
            ("due_datetime", "<=", now),
        ])
        for task in due:
            if task.channel == "email" and task.auto_send:
                try:
                    task._send_email_reminder()
                except Exception as exc:
                    task.message_post(
                        body=_("Automatic Post-Care email failed: %s") % str(exc)
                    )
                    task.with_context(postcare_transition=True).write({"state": "due"})
                    task._schedule_staff_activity()
            else:
                task.with_context(postcare_transition=True).write({"state": "due"})
                task._schedule_staff_activity()

        escalation_candidates = self.sudo().search([
            ("state", "in", ("due", "sent", "contacted")),
            ("escalate_if_overdue", "=", True),
            ("due_datetime", "!=", False),
        ])
        for task in escalation_candidates:
            threshold = fields.Datetime.to_datetime(task.due_datetime) + timedelta(
                hours=task.escalation_after_hours
            )
            if now > threshold:
                task.with_context(postcare_transition=True).write({"state": "overdue"})
                task._ensure_escalation(
                    reason=_("Post-Care Task exceeded its escalation grace period.")
                )
