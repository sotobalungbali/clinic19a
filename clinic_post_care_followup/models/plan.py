from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicPostcarePlan(models.Model):
    """Patient-specific post-treatment follow-up episode."""

    _name = "clinic.postcare.plan"
    _description = "Clinic Post-Care Follow-up Plan"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.postcare.company.mixin"]
    _order = "start_datetime desc, id desc"
    _check_company_auto = True

    _date_order = models.Constraint(
        "CHECK(expected_end_date IS NULL OR start_date IS NULL OR start_date <= expected_end_date)",
        "Post-Care expected end date cannot be before its start date.",
    )
    _patient_state_idx = models.Index("(company_id, patient_id, state, next_due_at)")
    _source_idx = models.Index("(company_id, encounter_id, booking_id, care_plan_id)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    patient_id = fields.Many2one(
        "clinic.patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    partner_id = fields.Many2one(
        related="patient_id.partner_id",
        store=True,
        readonly=True,
        index=True,
        string="Patient Contact",
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Responsible Doctor",
        ondelete="set null",
        check_company=True,
    )
    responsible_staff_id = fields.Many2one(
        "clinic.staff",
        string="Post-Care Coordinator",
        ondelete="set null",
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )
    protocol_id = fields.Many2one(
        "clinic.postcare.protocol",
        required=True,
        ondelete="restrict",
        check_company=True,
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )

    source_type = fields.Selection(
        [
            ("manual", "Manual"),
            ("encounter", "Encounter"),
            ("booking", "Booking"),
            ("care_plan", "Care Plan"),
            ("treatment", "Treatment"),
        ],
        default="manual",
        required=True,
        tracking=True,
        index=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        ondelete="set null",
        index=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        ondelete="set null",
        index=True,
    )
    care_plan_id = fields.Many2one(
        "clinic.care.plan",
        string="Care Plan",
        ondelete="set null",
        index=True,
        check_company=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        ondelete="set null",
        index=True,
    )

    start_datetime = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    start_date = fields.Date(compute="_compute_start_date", store=True, index=True)
    expected_end_date = fields.Date(tracking=True, index=True)
    completed_at = fields.Datetime(readonly=True, tracking=True)
    closed_at = fields.Datetime(readonly=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("escalated", "Escalated"),
            ("completed", "Completed"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Important"), ("2", "Urgent"), ("3", "Very Urgent")],
        default="0",
        required=True,
        tracking=True,
    )

    instruction_html = fields.Html(
        string="Patient Instructions",
        sanitize=True,
    )
    warning_signs_html = fields.Html(sanitize=True)
    emergency_instruction_html = fields.Html(sanitize=True)

    instruction_acknowledged = fields.Boolean(
        string="Instructions Acknowledged",
        tracking=True,
    )
    acknowledged_at = fields.Datetime(readonly=True)
    acknowledged_by_id = fields.Many2one("res.users", readonly=True)

    task_ids = fields.One2many(
        "clinic.postcare.task",
        "plan_id",
        string="Follow-up Tasks",
        copy=False,
    )
    checkin_ids = fields.One2many(
        "clinic.postcare.checkin",
        "plan_id",
        string="Patient Check-ins",
        copy=False,
    )
    escalation_ids = fields.One2many(
        "clinic.postcare.escalation",
        "plan_id",
        string="Escalations",
        copy=False,
    )

    task_count = fields.Integer(compute="_compute_metrics")
    completed_task_count = fields.Integer(compute="_compute_metrics")
    overdue_task_count = fields.Integer(compute="_compute_metrics")
    checkin_count = fields.Integer(compute="_compute_metrics")
    escalation_count = fields.Integer(compute="_compute_metrics")
    open_escalation_count = fields.Integer(compute="_compute_metrics")
    progress = fields.Float(compute="_compute_metrics")
    next_due_at = fields.Datetime(
        compute="_compute_metrics",
        store=True,
        index=True,
    )
    red_flag_count = fields.Integer(compute="_compute_metrics")
    notes = fields.Text()

    @api.depends("start_datetime")
    def _compute_start_date(self):
        for record in self:
            record.start_date = (
                fields.Date.to_date(record.start_datetime)
                if record.start_datetime
                else False
            )

    @api.depends(
        "task_ids.state",
        "task_ids.due_datetime",
        "checkin_ids.red_flag",
        "escalation_ids.state",
    )
    # Rollups are operational snapshots; Task/Check-in/Escalation records remain the audit source.
    def _compute_metrics(self):
        for record in self:
            tasks = record.task_ids
            completed = tasks.filtered(lambda task: task.state == "completed")
            open_tasks = tasks.filtered(
                lambda task: task.state not in ("completed", "cancelled")
            )
            open_escalations = record.escalation_ids.filtered(
                lambda esc: esc.state not in ("resolved", "cancelled")
            )
            due_values = [task.due_datetime for task in open_tasks if task.due_datetime]

            record.task_count = len(tasks)
            record.completed_task_count = len(completed)
            record.overdue_task_count = len(
                tasks.filtered(lambda task: task.is_overdue)
            )
            record.checkin_count = len(record.checkin_ids)
            record.escalation_count = len(record.escalation_ids)
            record.open_escalation_count = len(open_escalations)
            record.red_flag_count = len(record.checkin_ids.filtered("red_flag"))
            record.progress = (
                (len(completed) / len(tasks)) * 100.0 if tasks else 0.0
            )
            record.next_due_at = min(due_values) if due_values else False

    @api.onchange("protocol_id")
    def _onchange_protocol(self):
        for record in self:
            if not record.protocol_id:
                continue
            protocol = record.protocol_id
            record.company_id = protocol.company_id
            record.responsible_staff_id = (
                protocol.default_assignee_id
                or record.company_id.clinic_postcare_default_assignee_id
            )
            record.instruction_html = protocol.instruction_html
            record.warning_signs_html = protocol.warning_signs_html
            record.emergency_instruction_html = protocol.emergency_instruction_html
            if record.start_datetime and protocol.default_duration_days:
                record.expected_end_date = (
                    fields.Date.to_date(record.start_datetime)
                    + timedelta(days=protocol.default_duration_days)
                )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            protocol = self.env["clinic.postcare.protocol"].browse(vals.get("protocol_id"))
            patient = self.env["clinic.patient"].browse(vals.get("patient_id"))

            if protocol.exists():
                vals.setdefault("company_id", protocol.company_id.id)
                vals.setdefault(
                    "responsible_staff_id",
                    protocol.default_assignee_id.id
                    or protocol.company_id.clinic_postcare_default_assignee_id.id
                    or False,
                )
                vals.setdefault("instruction_html", protocol.instruction_html)
                vals.setdefault("warning_signs_html", protocol.warning_signs_html)
                vals.setdefault("emergency_instruction_html", protocol.emergency_instruction_html)

                start_dt = fields.Datetime.to_datetime(
                    vals.get("start_datetime") or fields.Datetime.now()
                )
                if protocol.default_duration_days and not vals.get("expected_end_date"):
                    vals["expected_end_date"] = (
                        start_dt.date() + timedelta(days=protocol.default_duration_days)
                    )

            if patient.exists():
                vals.setdefault("company_id", patient.company_id.id)

            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.postcare.plan")
                    or "/"
                )
            prepared.append(vals)

        return super().create(prepared)

    @api.constrains(
        "patient_id",
        "company_id",
        "protocol_id",
        "responsible_staff_id",
        "encounter_id",
        "booking_id",
        "care_plan_id",
        "treatment_id",
    )
    def _check_plan_scope(self):
        for record in self:
            if record.patient_id.company_id != record.company_id:
                raise ValidationError(_("Patient and Post-Care Plan company must match."))
            if record.protocol_id.company_id != record.company_id:
                raise ValidationError(_("Post-Care Protocol and Plan company must match."))
            if (
                record.responsible_staff_id
                and record.responsible_staff_id.company_id != record.company_id
            ):
                raise ValidationError(_("Post-Care Coordinator must belong to the Plan company."))

            if record.encounter_id and record.encounter_id.patient_id != record.patient_id:
                raise ValidationError(_("Encounter belongs to a different Patient."))
            if (
                record.booking_id
                and record.booking_id.patient_id != record.partner_id
            ):
                raise ValidationError(_("Booking belongs to a different Patient."))
            if record.care_plan_id and record.care_plan_id.patient_id != record.patient_id:
                raise ValidationError(_("Care Plan belongs to a different Patient."))
            # `clinic.treatment` is the public service/catalog model in the
            # current ClinicOne baseline; it is not a patient treatment episode.
            # Patient consistency is therefore validated through the actual
            # source documents (Encounter, Booking, Care Plan), while
            # treatment_id remains service-context traceability only.

    def write(self, vals):
        workflow_fields = {
            "state",
            "completed_at",
            "closed_at",
            "instruction_acknowledged",
            "acknowledged_at",
            "acknowledged_by_id",
        }
        scope_fields = {
            "patient_id",
            "company_id",
            "branch_id",
            "protocol_id",
            "encounter_id",
            "booking_id",
            "care_plan_id",
            "treatment_id",
        }
        if workflow_fields.intersection(vals) and not self.env.context.get("postcare_transition"):
            raise AccessError(_("Use Post-Care Plan workflow actions to change status/audit fields."))
        if scope_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft",):
                    raise UserError(_("Post-Care source and Patient scope can only be changed in Draft."))
        return super().write(vals)

    # Task generation is idempotent by Protocol Step so retries cannot duplicate scheduled care.
    def action_generate_tasks(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can generate follow-up tasks."),
        )
        Task = self.env["clinic.postcare.task"]
        for record in self:
            if record.state not in ("draft", "active"):
                raise UserError(_("Tasks can only be generated for Draft or Active Plans."))
            start = fields.Datetime.to_datetime(record.start_datetime)
            existing_steps = record.task_ids.mapped("protocol_step_id").ids

            for step in record.protocol_id.step_ids.filtered("active"):
                if step.id in existing_steps:
                    continue
                due = start + timedelta(days=step.delay_days, hours=step.delay_hours)
                response_due = (
                    due + timedelta(hours=step.response_due_hours)
                    if step.requires_response
                    else False
                )
                assignee = (
                    step.assignee_id
                    or record.responsible_staff_id
                    or record.company_id.clinic_postcare_default_assignee_id
                )
                Task.create({
                    "plan_id": record.id,
                    "protocol_step_id": step.id,
                    "assignee_id": assignee.id or False,
                    "name": step.name,
                    "task_type": step.task_type,
                    "channel": step.channel,
                    "priority": step.priority,
                    "due_datetime": due,
                    "response_required": step.requires_response,
                    "response_due_datetime": response_due,
                    "auto_send": step.auto_send,
                    "instruction_html": step.instruction_html,
                    "escalate_if_overdue": step.escalate_if_overdue,
                    "escalation_after_hours": step.escalation_after_hours,
                    "escalation_severity": step.escalation_severity,
                })
        return True

    # Activation starts follow-up work but never mutates the source Encounter/Booking/Care Plan.
    def action_activate(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can activate Plans."),
        )
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft Post-Care Plans can be activated."))
            if record.protocol_id.state != "active":
                raise UserError(_("The selected Post-Care Protocol must be Active."))
            if record.protocol_id.auto_generate_tasks:
                record.action_generate_tasks()
            record.with_context(postcare_transition=True).write({"state": "active"})
            record.message_post(body=_("Post-Care follow-up plan activated."))
        return True

    def action_acknowledge_instructions(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_user",
            _("You do not have permission to acknowledge Post-Care instructions."),
        )
        self.with_context(postcare_transition=True).write({
            "instruction_acknowledged": True,
            "acknowledged_at": fields.Datetime.now(),
            "acknowledged_by_id": self.env.user.id,
        })
        return True

    # Required responses and open escalations are backend completion gates, not merely UI hints.
    def action_complete(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can complete Plans."),
        )
        for record in self:
            if record.open_escalation_count:
                raise UserError(_("Resolve or cancel open Post-Care Escalations before completion."))
            required_open = record.task_ids.filtered(
                lambda task:
                    task.state not in ("completed", "cancelled")
                    and task.response_required
            )
            if required_open:
                raise UserError(_("Required response tasks remain open."))
            record.with_context(postcare_transition=True).write({
                "state": "completed",
                "completed_at": fields.Datetime.now(),
            })
        return True

    def action_close(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can close Plans."),
        )
        for record in self:
            if record.state != "completed":
                raise UserError(_("Complete the Post-Care Plan before closing it."))
            record.with_context(postcare_transition=True).write({
                "state": "closed",
                "closed_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can cancel Plans."),
        )
        for record in self:
            open_tasks = record.task_ids.filtered(
                lambda task: task.state not in ("completed", "cancelled")
            )
            if open_tasks:
                open_tasks.with_context(postcare_transition=True).write({"state": "cancelled"})
            record.with_context(postcare_transition=True).write({"state": "cancelled"})
        return True

    def action_view_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Tasks"),
            "res_model": "clinic.postcare.task",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }

    def action_view_checkins(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Check-ins"),
            "res_model": "clinic.postcare.checkin",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }

    def action_view_escalations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Escalations"),
            "res_model": "clinic.postcare.escalation",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }

    # Source navigation preserves ownership: Post-Care only links back to upstream clinical records.
    def action_open_source(self):
        self.ensure_one()
        source = {
            "encounter": ("clinic.encounter", self.encounter_id),
            "booking": ("booking.booking", self.booking_id),
            "care_plan": ("clinic.care.plan", self.care_plan_id),
            "treatment": ("clinic.treatment", self.treatment_id),
        }.get(self.source_type)
        if not source or not source[1]:
            raise UserError(_("No source record is linked to this Post-Care Plan."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Source"),
            "res_model": source[0],
            "view_mode": "form",
            "res_id": source[1].id,
        }

    def action_print_instructions(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_post_care_followup.action_report_postcare_instructions"
        ).report_action(self)

    def action_print_summary(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_post_care_followup.action_report_postcare_summary"
        ).report_action(self)
