from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


THREAD_STATES = [
    ("open", "Open"),
    ("closed", "Closed"),
    ("archived", "Archived"),
]

PRIORITIES = [
    ("routine", "Routine"),
    ("priority", "Priority"),
    ("urgent", "Urgent"),
]


class ClinicTelemedicineThread(models.Model):
    """Exact-patient secure messaging scope.

    This is the historical technical contract already anticipated by
    `clinic_staff`: `clinic.telemedicine.thread` with `handler_id`.
    """

    _name = "clinic.telemedicine.thread"
    _description = "Clinic Telemedicine Secure Thread"
    _order = "attention_required desc, priority desc, last_message_at desc, id desc"
    _check_company_auto = True

    _session_unique = models.Constraint(
        "UNIQUE(session_id)",
        "A Telemedicine Session can have only one Secure Conversation.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, handler_id, attention_required)"
    )

    name = fields.Char(
        string="Thread Reference",
        default="/",
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
    )

    session_id = fields.Many2one(
        "clinic.telemedicine.session",
        ondelete="set null",
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        required=True,
        ondelete="restrict",
        index=True,
    )
    partner_id = fields.Many2one(
        related="patient_id.partner_id",
        string="Patient Contact",
        store=True,
        readonly=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="restrict",
        index=True,
    )
    handler_id = fields.Many2one(
        "clinic.staff",
        string="Assigned Staff Handler",
        ondelete="set null",
        domain="[('company_id', '=', company_id)]",
        index=True,
        help=(
            "Operational support/clinical staff responsible for this thread. "
            "The exact field name preserves the historical clinic_staff contract."
        ),
    )

    subject = fields.Char(required=True, index=True)
    priority = fields.Selection(
        PRIORITIES,
        default="routine",
        required=True,
        index=True,
    )
    state = fields.Selection(
        THREAD_STATES,
        default="open",
        required=True,
        readonly=True,
        index=True,
    )

    patient_can_reply = fields.Boolean(default=True)
    patient_can_upload = fields.Boolean(default=True)
    attention_required = fields.Boolean(
        default=False,
        index=True,
        help=(
            "Operational attention flag only. It is not a diagnosis or Incident "
            "record and does not replace the later clinic_incident_event addon."
        ),
    )
    internal_note = fields.Text(
        help="Internal coordination note. Never rendered in the patient portal."
    )

    message_ids = fields.One2many(
        "clinic.telemedicine.message",
        "thread_id",
        string="Secure Messages",
        readonly=True,
    )
    attachment_ids = fields.One2many(
        "clinic.telemedicine.attachment",
        "thread_id",
        string="Shared Files",
        readonly=True,
    )

    message_count = fields.Integer(compute="_compute_counts", store=True)
    attachment_count = fields.Integer(compute="_compute_counts", store=True)
    patient_unread_count = fields.Integer(compute="_compute_counts", store=True)
    clinic_unread_count = fields.Integer(compute="_compute_counts", store=True)

    first_patient_message_at = fields.Datetime(readonly=True, index=True)
    first_response_on = fields.Datetime(
        readonly=True,
        index=True,
        help=(
            "First Doctor/Staff response after the first Patient message. "
            "Preserves the historical Clinic Staff telemedicine KPI contract."
        ),
    )
    first_response_minutes = fields.Float(
        compute="_compute_first_response_minutes",
        store=True,
    )
    last_message_at = fields.Datetime(readonly=True, index=True)

    closed_at = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True)
    portal_url = fields.Char(compute="_compute_portal_url")

    @api.depends(
        "message_ids",
        "message_ids.author_kind",
        "message_ids.patient_read_at",
        "message_ids.clinic_read_at",
        "attachment_ids",
    )
    def _compute_counts(self):
        for thread in self:
            thread.message_count = len(thread.message_ids)
            thread.attachment_count = len(thread.attachment_ids)
            thread.patient_unread_count = len(
                thread.message_ids.filtered(
                    lambda message:
                    message.author_kind != "patient"
                    and not message.patient_read_at
                )
            )
            thread.clinic_unread_count = len(
                thread.message_ids.filtered(
                    lambda message:
                    message.author_kind == "patient"
                    and not message.clinic_read_at
                )
            )

    @api.depends("first_patient_message_at", "first_response_on")
    def _compute_first_response_minutes(self):
        for thread in self:
            if thread.first_patient_message_at and thread.first_response_on:
                thread.first_response_minutes = max(
                    0.0,
                    (
                        thread.first_response_on
                        - thread.first_patient_message_at
                    ).total_seconds()
                    / 60.0,
                )
            else:
                thread.first_response_minutes = 0.0

    def _compute_portal_url(self):
        for thread in self:
            thread.portal_url = (
                f"/my/clinic/messages/{thread.id}"
                if thread.id
                else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        portal_patient = self.env.context.get(
            "telemedicine_portal_patient_create"
        )
        portal_partner_id = self.env.context.get(
            "telemedicine_portal_partner_id"
        )
        system_create = self.env.context.get(
            "telemedicine_thread_system_create"
        )

        if not self.env.su and not system_create:
            if not self.env.user.has_group(
                "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
            ):
                raise AccessError(
                    _("Telemedicine Clinician access is required to create a Thread.")
                )

        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company

            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.telemedicine.thread")
                    or "/"
                )

            patient = self.env["clinic.patient"].browse(
                vals.get("patient_id")
            )
            if (
                patient
                and company.policy_branch_scope_telemedicine
                and not vals.get("branch_id")
                and patient.partner_id.branch_id
                and patient.partner_id.branch_id.company_id == company
            ):
                vals["branch_id"] = patient.partner_id.branch_id.id

            if portal_patient:
                if not patient or patient.partner_id.id != portal_partner_id:
                    raise AccessError(
                        _("Portal Thread creation does not match the signed-in patient.")
                    )

            prepared.append(vals)

        records = super().create(prepared)
        records._check_scope_consistency()
        return records

    def write(self, vals):
        vals = dict(vals)

        if (
            "state" in vals
            and not self.env.context.get("telemedicine_thread_transition")
        ):
            raise AccessError(
                _("Use Secure Thread workflow actions to change status.")
            )

        metric_fields = {
            "first_patient_message_at",
            "first_response_on",
            "last_message_at",
        }
        if metric_fields.intersection(vals) and not self.env.context.get(
            "telemedicine_thread_metrics"
        ):
            raise AccessError(
                _("Thread communication metrics are system-managed evidence.")
            )

        if self.filtered(lambda thread: thread.state == "archived") and not (
            self.env.context.get("telemedicine_thread_transition")
            or self.env.context.get("telemedicine_thread_metrics")
        ):
            raise AccessError(_("Archived Secure Threads are read-only."))

        result = super().write(vals)
        self._check_scope_consistency()
        return result

    def unlink(self):
        if not self.env.su:
            self._require_manager()
            if self.mapped("message_ids"):
                raise UserError(
                    _(
                        "A Secure Thread with message evidence cannot be deleted. "
                        "Archive it instead."
                    )
                )
        return super().unlink()

    @api.constrains(
        "company_id",
        "branch_id",
        "session_id",
        "patient_id",
        "doctor_id",
        "handler_id",
    )
    def _check_scope_consistency(self):
        for thread in self:
            if thread.patient_id.company_id != thread.company_id:
                raise ValidationError(_("Thread Patient belongs to another company."))
            if not thread.patient_id.partner_id:
                raise ValidationError(
                    _("Secure Messaging requires a Patient Card linked to a Contact.")
                )
            if thread.doctor_id.company_id != thread.company_id:
                raise ValidationError(_("Thread Doctor belongs to another company."))
            if (
                thread.branch_id
                and thread.branch_id.company_id != thread.company_id
            ):
                raise ValidationError(_("Thread Branch belongs to another company."))
            if (
                thread.handler_id
                and thread.handler_id.company_id
                and thread.handler_id.company_id != thread.company_id
            ):
                raise ValidationError(_("Thread Handler belongs to another company."))

            if thread.session_id:
                if thread.session_id.company_id != thread.company_id:
                    raise ValidationError(
                        _("Linked Session belongs to another company.")
                    )
                if thread.session_id.patient_id != thread.patient_id:
                    raise ValidationError(
                        _("Linked Session belongs to another patient.")
                    )
                if thread.session_id.doctor_id != thread.doctor_id:
                    raise ValidationError(
                        _("Linked Session belongs to another Doctor.")
                    )

    def _require_clinician(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
        ):
            raise AccessError(_("Telemedicine Clinician access is required."))
        return True

    def _require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_manager"
        ):
            raise AccessError(_("Telemedicine Manager access is required."))
        return True

    def _record_message_metrics(self, message):
        self.ensure_one()
        now = message.sent_at or fields.Datetime.now()
        vals = {"last_message_at": now}

        if message.author_kind == "patient":
            if not self.first_patient_message_at:
                vals["first_patient_message_at"] = now
        elif self.first_patient_message_at and not self.first_response_on:
            vals["first_response_on"] = now

        self.sudo().with_context(
            telemedicine_thread_metrics=True
        ).write(vals)
        return True

    def action_assign_to_me(self):
        self._require_clinician()
        if self.filtered(lambda thread: thread.state != "open"):
            raise UserError(
                _("Only an Open Secure Thread can be assigned.")
            )
        Staff = self.env["clinic.staff"]
        for thread in self:
            staff = Staff.search([
                ("partner_id", "=", self.env.user.partner_id.id),
                ("company_id", "in", (False, thread.company_id.id)),
            ], limit=1)
            if not staff:
                raise UserError(
                    _(
                        "Your user is not linked to a Clinic Staff record in "
                        "this company."
                    )
                )
            thread.handler_id = staff.id
        return True

    def action_close(self):
        self._require_clinician()
        self.with_context(telemedicine_thread_transition=True).write({
            "state": "closed",
            "closed_at": fields.Datetime.now(),
            "closed_by_id": self.env.user.id,
            "patient_can_reply": False,
            "patient_can_upload": False,
        })
        return True

    def action_reopen(self):
        self._require_clinician()
        self.with_context(telemedicine_thread_transition=True).write({
            "state": "open",
            "closed_at": False,
            "closed_by_id": False,
            "patient_can_reply": True,
        })
        return True

    def action_archive(self):
        self._require_manager()
        self.with_context(telemedicine_thread_transition=True).write({
            "state": "archived",
            "patient_can_reply": False,
            "patient_can_upload": False,
        })
        return True

    def action_mark_clinic_read(self):
        self._require_clinician()
        messages = self.message_ids.filtered(
            lambda message:
            message.author_kind == "patient"
            and not message.clinic_read_at
        )
        if messages:
            messages.sudo().with_context(
                telemedicine_message_read=True
            ).write({"clinic_read_at": fields.Datetime.now()})
        return True

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            raise UserError(_("This Secure Thread is not linked to a Session."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Telemedicine Session"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "form",
            "res_id": self.session_id.id,
        }

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Card"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

    def action_open_doctor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor"),
            "res_model": "clinic.doctor",
            "view_mode": "form",
            "res_id": self.doctor_id.id,
        }

    def action_open_messages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Secure Messages"),
            "res_model": "clinic.telemedicine.message",
            "view_mode": "list,form",
            "domain": [("thread_id", "=", self.id)],
            "context": {"default_thread_id": self.id},
        }

    def action_open_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Shared Files"),
            "res_model": "clinic.telemedicine.attachment",
            "view_mode": "list,form",
            "domain": [("thread_id", "=", self.id)],
            "context": {"default_thread_id": self.id},
        }

    def action_open_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.portal_url,
            "target": "new",
        }

