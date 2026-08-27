from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


SESSION_STATES = [
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("ready", "Ready"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
    ("no_show", "No Show"),
]

PROVIDER_MODES = [
    ("manual_url", "Manual HTTPS Meeting URL"),
    ("provider_hook", "Provider Extension Hook"),
]


class ClinicTelemedicineSession(models.Model):
    """Teleconsultation lifecycle without taking ownership of clinical records.

    A Session coordinates patient, doctor, schedule, secure chat and meeting
    provenance. Clinical SOAP/diagnosis/documentation remains in Encounter.
    """

    _name = "clinic.telemedicine.session"
    _description = "Clinic Telemedicine Session"
    _order = "scheduled_start desc, id desc"
    _check_company_auto = True

    _appointment_unique = models.Constraint(
        "UNIQUE(appointment_id)",
        "An Appointment can be linked to only one Telemedicine Session.",
    )
    _booking_unique = models.Constraint(
        "UNIQUE(booking_id)",
        "A Booking can be linked to only one Telemedicine Session.",
    )
    _schedule_window_check = models.Constraint(
        "CHECK(scheduled_end > scheduled_start)",
        "Telemedicine session end time must be later than start time.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, scheduled_start, doctor_id)"
    )

    name = fields.Char(
        string="Session Reference",
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
    host_staff_id = fields.Many2one(
        "clinic.staff",
        string="Session Host / Support Staff",
        ondelete="set null",
        domain="[('company_id', '=', company_id)]",
        index=True,
    )

    booking_id = fields.Many2one(
        "booking.booking",
        ondelete="set null",
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        ondelete="set null",
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        ondelete="set null",
        index=True,
        domain="[('company_id', '=', company_id), ('patient_id', '=', patient_id)]",
    )
    consent_form_id = fields.Many2one(
        "clinic.consent.form",
        string="Telemedicine Consent",
        ondelete="set null",
        domain="[('company_id', '=', company_id), ('patient_id', '=', partner_id)]",
    )

    state = fields.Selection(
        SESSION_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
    )

    scheduled_start = fields.Datetime(required=True, index=True)
    scheduled_end = fields.Datetime(required=True, index=True)
    duration_minutes = fields.Integer(
        compute="_compute_duration_minutes",
        store=True,
    )

    provider_mode = fields.Selection(
        PROVIDER_MODES,
        required=True,
        default=lambda self: self.env.company.clinic_telemedicine_provider_mode,
    )
    meeting_url = fields.Char(
        string="Secure Meeting URL",
        help=(
            "HTTPS meeting URL supplied manually or by a future provider hook. "
            "The base addon does not fabricate a video provider."
        ),
    )
    provider_reference = fields.Char(readonly=True, copy=False)
    meeting_ready = fields.Boolean(compute="_compute_meeting_ready")
    patient_can_join = fields.Boolean(compute="_compute_patient_can_join")

    host_joined_at = fields.Datetime(readonly=True)
    patient_joined_at = fields.Datetime(readonly=True)
    started_at = fields.Datetime(readonly=True)
    ended_at = fields.Datetime(readonly=True)
    cancelled_at = fields.Datetime(readonly=True)
    cancellation_reason = fields.Text(readonly=True)

    thread_ids = fields.One2many(
        "clinic.telemedicine.thread",
        "session_id",
        string="Secure Threads",
        readonly=True,
    )
    thread_count = fields.Integer(compute="_compute_thread_count")

    queue_ids = fields.One2many(
        "clinic.queue",
        "telemedicine_session_id",
        string="Telemedicine Queues",
        readonly=True,
    )
    queue_count = fields.Integer(compute="_compute_queue_count")

    portal_url = fields.Char(compute="_compute_portal_url")

    @api.depends("scheduled_start", "scheduled_end")
    def _compute_duration_minutes(self):
        for record in self:
            if record.scheduled_start and record.scheduled_end:
                record.duration_minutes = max(
                    0,
                    int(
                        (
                            record.scheduled_end - record.scheduled_start
                        ).total_seconds()
                        // 60
                    ),
                )
            else:
                record.duration_minutes = 0

    @api.depends("meeting_url")
    def _compute_meeting_ready(self):
        for record in self:
            record.meeting_ready = bool(record.meeting_url)

    @api.depends(
        "state",
        "scheduled_start",
        "scheduled_end",
        "meeting_url",
        "company_id.clinic_telemedicine_early_join_minutes",
        "company_id.clinic_telemedicine_late_join_minutes",
    )
    def _compute_patient_can_join(self):
        now = fields.Datetime.now()
        for record in self:
            record.patient_can_join = record._patient_join_allowed(now=now)

    def _compute_thread_count(self):
        for record in self:
            record.thread_count = len(record.thread_ids)

    def _compute_queue_count(self):
        for record in self:
            record.queue_count = len(record.queue_ids)

    def _compute_portal_url(self):
        for record in self:
            record.portal_url = (
                f"/my/clinic/telemedicine/{record.id}"
                if record.id
                else False
            )

    @api.model_create_multi
    def create(self, vals_list):
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
                    .next_by_code("clinic.telemedicine.session")
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

            prepared.append(vals)
        records = super().create(prepared)
        records._check_source_consistency()
        return records

    def write(self, vals):
        vals = dict(vals)

        if (
            "state" in vals
            and not self.env.context.get("telemedicine_session_transition")
        ):
            raise AccessError(
                _("Use Telemedicine Session workflow actions to change status.")
            )

        if (
            {"patient_id", "doctor_id", "company_id", "booking_id",
             "appointment_id", "scheduled_start", "scheduled_end"}
            .intersection(vals)
            and self.filtered(
                lambda session: session.state
                in ("ready", "in_progress", "completed")
            )
            and not self.env.context.get("telemedicine_session_transition")
        ):
            raise AccessError(
                _("Session identity and schedule are locked once the session is Ready.")
            )

        join_fields = {"patient_joined_at", "host_joined_at"}
        if join_fields.intersection(vals) and not (
            self.env.context.get("telemedicine_patient_join")
            or self.env.context.get("telemedicine_host_join")
            or self.env.context.get("telemedicine_session_transition")
        ):
            raise AccessError(
                _("Join evidence can only be written by controlled join actions.")
            )

        result = super().write(vals)
        self._check_source_consistency()
        return result

    def unlink(self):
        if not self.env.su:
            self._require_manager()
            if self.filtered(
                lambda session: session.state
                not in ("draft", "cancelled", "no_show")
            ):
                raise UserError(
                    _(
                        "Only Draft, Cancelled, or No-Show sessions may be "
                        "deleted. Preserve consultation evidence otherwise."
                    )
                )
        return super().unlink()

    @api.constrains(
        "company_id",
        "branch_id",
        "patient_id",
        "doctor_id",
        "host_staff_id",
        "booking_id",
        "appointment_id",
        "encounter_id",
        "consent_form_id",
    )
    def _check_source_consistency(self):
        for session in self:
            if session.patient_id.company_id != session.company_id:
                raise ValidationError(
                    _("Patient Card belongs to another company.")
                )
            if session.doctor_id.company_id != session.company_id:
                raise ValidationError(
                    _("Doctor belongs to another company.")
                )
            if not session.patient_id.partner_id:
                raise ValidationError(
                    _("Telemedicine requires a Patient Card linked to a Contact.")
                )
            if (
                session.branch_id
                and session.branch_id.company_id != session.company_id
            ):
                raise ValidationError(
                    _("Session Branch must belong to the Session company.")
                )
            if (
                session.host_staff_id
                and session.host_staff_id.company_id
                and session.host_staff_id.company_id != session.company_id
            ):
                raise ValidationError(
                    _("Session Host belongs to another company.")
                )

            if session.booking_id:
                if session.booking_id.company_id != session.company_id:
                    raise ValidationError(
                        _("Linked Booking belongs to another company.")
                    )
                if session.booking_id.patient_id != session.partner_id:
                    raise ValidationError(
                        _("Linked Booking belongs to another patient.")
                    )
                if (
                    session.booking_id.doctor_id
                    and session.booking_id.doctor_id != session.doctor_id
                ):
                    raise ValidationError(
                        _("Linked Booking belongs to another Doctor.")
                    )

            if session.appointment_id:
                if session.appointment_id.company_id != session.company_id:
                    raise ValidationError(
                        _("Linked Appointment belongs to another company.")
                    )
                if session.appointment_id.partner_id != session.partner_id:
                    raise ValidationError(
                        _("Linked Appointment belongs to another patient.")
                    )
                if session.appointment_id.doctor_id != session.doctor_id:
                    raise ValidationError(
                        _("Linked Appointment belongs to another Doctor.")
                    )

            if session.encounter_id:
                if session.encounter_id.company_id != session.company_id:
                    raise ValidationError(
                        _("Linked Encounter belongs to another company.")
                    )
                if session.encounter_id.patient_id != session.patient_id:
                    raise ValidationError(
                        _("Linked Encounter belongs to another patient.")
                    )

            if session.consent_form_id:
                if (
                    session.consent_form_id.company_id
                    and session.consent_form_id.company_id != session.company_id
                ):
                    raise ValidationError(
                        _("Linked Consent belongs to another company.")
                    )
                if session.consent_form_id.patient_id != session.partner_id:
                    raise ValidationError(
                        _("Linked Consent belongs to another patient.")
                    )

    @api.constrains("meeting_url")
    def _check_meeting_url(self):
        for session in self.filtered("meeting_url"):
            session._validate_https_url(session.meeting_url)

    @api.model
    def _validate_https_url(self, url):
        parsed = urlparse((url or "").strip())
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValidationError(
                _(
                    "Telemedicine meeting URLs must use HTTPS and include "
                    "a valid host name."
                )
            )
        return True

