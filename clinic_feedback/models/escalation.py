from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFeedbackEscalation(models.Model):
    """Service-recovery workflow for complaints, low scores and detractors."""

    _name = "clinic.feedback.escalation"
    _description = "Clinic Feedback Service-Recovery Escalation"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.feedback.company.mixin"]
    _order = "severity desc, due_at, id"
    _check_company_auto = True

    _feedback_state_idx = models.Index("(company_id, feedback_id, state, severity)")
    _owner_state_idx = models.Index("(company_id, owner_staff_id, state, due_at)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True)
    feedback_id = fields.Many2one(
        "clinic.feedback",
        required=True,
        ondelete="cascade",
        check_company=True,
        index=True,
        tracking=True,
    )
    request_id = fields.Many2one(
        related="feedback_id.request_id",
        store=True,
        readonly=True,
        index=True,
    )
    patient_id = fields.Many2one(
        related="feedback_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="feedback_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="feedback_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )

    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
        tracking=True,
        index=True,
    )
    category = fields.Selection(
        [
            ("service", "Service Experience"),
            ("doctor", "Doctor / Clinical Communication"),
            ("staff", "Staff Experience"),
            ("waiting", "Waiting Time"),
            ("facility", "Facility"),
            ("communication", "Communication"),
            ("billing", "Billing Experience"),
            ("postcare", "Post-Care"),
            ("other", "Other"),
        ],
        default="service",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("acknowledged", "Acknowledged"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
            ("cancelled", "Cancelled"),
        ],
        default="open",
        required=True,
        tracking=True,
        index=True,
    )

    owner_staff_id = fields.Many2one(
        "clinic.staff",
        string="Service-Recovery Owner",
        ondelete="set null",
        check_company=True,
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    reason = fields.Text(required=True, tracking=True)
    investigation_note = fields.Text()
    recovery_action = fields.Text()
    patient_contact_note = fields.Text()
    resolution_note = fields.Text()

    opened_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    due_at = fields.Datetime(index=True, tracking=True)
    acknowledged_at = fields.Datetime(readonly=True)
    acknowledged_by_id = fields.Many2one("res.users", readonly=True)
    resolved_at = fields.Datetime(readonly=True)
    resolved_by_id = fields.Many2one("res.users", readonly=True)
    overdue_marked_at = fields.Datetime(readonly=True, index=True)
    is_overdue = fields.Boolean(
        compute="_compute_is_overdue",
        store=True,
        index=True,
    )

    @api.depends("state", "overdue_marked_at")
    def _compute_is_overdue(self):
        # Time passage is persisted by the cron in overdue_marked_at; search
        # filters never rely on a wall-clock-only stored compute.
        for record in self:
            record.is_overdue = bool(
                record.state == "in_progress" and record.overdue_marked_at
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            feedback = self.env["clinic.feedback"].browse(vals.get("feedback_id"))
            company = feedback.company_id if feedback.exists() else self.env.company

            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.feedback.escalation")
                    or "/"
                )
            if feedback.exists():
                vals.setdefault(
                    "owner_staff_id",
                    company.clinic_feedback_default_owner_staff_id.id
                    or feedback.staff_id.id
                    or False,
                )
                if not vals.get("due_at"):
                    hours = company.clinic_feedback_escalation_sla_hours or 24
                    vals["due_at"] = fields.Datetime.now() + timedelta(hours=hours)
            prepared.append(vals)

        records = super().create(prepared)
        for record in records:
            record._schedule_owner_activity()
            if record.feedback_id.state not in ("closed", "escalated"):
                record.feedback_id.with_context(feedback_transition=True).write(
                    {"state": "escalated"}
                )
        return records

    @api.constrains("owner_staff_id", "company_id")
    def _check_owner_company(self):
        for record in self:
            if (
                record.owner_staff_id
                and record.owner_staff_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Feedback Escalation owner must belong to the same company.")
                )

    def write(self, vals):
        audit_fields = {
            "state",
            "acknowledged_at",
            "acknowledged_by_id",
            "resolved_at",
            "resolved_by_id",
        }
        if audit_fields.intersection(vals) and not self.env.context.get(
            "feedback_transition"
        ):
            raise AccessError(
                _("Use Feedback Escalation workflow actions to change status/audit evidence.")
            )
        return super().write(vals)

    def _owner_user(self):
        self.ensure_one()
        if self.owner_staff_id and self.owner_staff_id.partner_id:
            user = self.env["res.users"].search(
                [("partner_id", "=", self.owner_staff_id.partner_id.id)],
                limit=1,
            )
            if user:
                return user
        return self.create_uid

    # Every service-recovery case creates accountable internal work for its designated owner.
    def _schedule_owner_activity(self):
        todo = self.env.ref("mail.mail_activity_data_todo")
        for record in self:
            user = record._owner_user()
            existing = record.activity_ids.filtered(
                lambda activity:
                    activity.activity_type_id == todo
                    and activity.user_id == user
            )
            if not existing:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=fields.Date.to_date(
                        record.due_at or fields.Datetime.now()
                    ),
                    user_id=user.id,
                    summary=_("Feedback Service Recovery: %s")
                    % record.feedback_id.name,
                    note=record.reason or "",
                )

    def action_acknowledge(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can acknowledge Escalations."),
        )
        for record in self:
            if record.state != "open":
                raise UserError(_("Only Open Feedback Escalations can be acknowledged."))
            record.with_context(feedback_transition=True).write({
                "state": "acknowledged",
                "acknowledged_at": fields.Datetime.now(),
                "acknowledged_by_id": self.env.user.id,
            })
        return True

    def action_start(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can start service recovery."),
        )
        for record in self:
            if record.state not in ("open", "acknowledged"):
                raise UserError(
                    _("Only Open/Acknowledged Escalations can enter service recovery.")
                )
            record.with_context(feedback_transition=True).write(
                {"state": "in_progress"}
            )
        return True

    # Resolution returns Feedback to review only after the last open escalation has cleared.
    def action_resolve(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can resolve Escalations."),
        )
        for record in self:
            if not record.resolution_note:
                raise UserError(_("Resolution Note is required."))
            record.with_context(feedback_transition=True).write({
                "state": "resolved",
                "resolved_at": fields.Datetime.now(),
                "resolved_by_id": self.env.user.id,
            })
            record.activity_ids.action_done()

            remaining = record.feedback_id.escalation_ids.filtered(
                lambda esc:
                    esc.id != record.id
                    and esc.state not in ("resolved", "cancelled")
            )
            if not remaining and record.feedback_id.state == "escalated":
                record.feedback_id.with_context(feedback_transition=True).write(
                    {"state": "under_review"}
                )
        return True

    def action_cancel(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_manager",
            _("Only a Feedback Manager can cancel Escalations."),
        )
        for record in self:
            record.with_context(feedback_transition=True).write(
                {"state": "cancelled"}
            )
            remaining = record.feedback_id.escalation_ids.filtered(
                lambda escalation:
                    escalation.id != record.id
                    and escalation.state not in ("resolved", "cancelled")
            )
            if not remaining and record.feedback_id.state == "escalated":
                record.feedback_id.with_context(feedback_transition=True).write(
                    {"state": "under_review"}
                )
        return True

    def action_open_feedback(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Feedback"),
            "res_model": "clinic.feedback",
            "view_mode": "form",
            "res_id": self.feedback_id.id,
        }

    def action_open_source(self):
        self.ensure_one()
        return self.feedback_id.action_open_source()

    @api.model
    # SLA watch stamps overdue evidence once; it never invents a hidden parallel workflow state.
    def _cron_mark_overdue(self):
        now = fields.Datetime.now()
        records = self.sudo().search([
            ("state", "=", "in_progress"),
            ("due_at", "!=", False),
            ("due_at", "<", now),
        ])
        # No hidden state is introduced: overdue remains a searchable flag and
        # the workflow stays In Progress until an accountable reviewer resolves it.
        for record in records:
            if not record.overdue_marked_at:
                record.overdue_marked_at = now
                record.message_post(
                    body=_("Feedback service-recovery SLA is overdue.")
                )
            record._schedule_owner_activity()
        return True
