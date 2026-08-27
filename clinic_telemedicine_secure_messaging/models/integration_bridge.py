from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


def _telemedicine_form_action(session):
    return {
        "type": "ir.actions.act_window",
        "name": _("Telemedicine Session"),
        "res_model": "clinic.telemedicine.session",
        "view_mode": "form",
        "res_id": session.id,
    }


class ClinicStaff(models.Model):
    """Fulfil the historical Staff telemedicine Thread contract."""

    _inherit = "clinic.staff"

    telemedicine_thread_ids = fields.One2many(
        "clinic.telemedicine.thread",
        "handler_id",
        string="Telemedicine Threads",
        readonly=True,
    )

    def _compute_counts(self):
        # Preserve every upstream Staff counter, including the repaired
        # Post-Care counter, then replace only the historical Telemedicine zero.
        super()._compute_counts()
        Thread = self.env["clinic.telemedicine.thread"].sudo()
        for staff in self:
            staff.telemed_thread_count = Thread.search_count([
                ("handler_id", "=", staff.id),
                ("state", "!=", "archived"),
            ])

    def action_open_telemedicine_threads(self):
        """Preserve the historical action name with live enterprise behavior."""
        self.ensure_one()
        return {
            "name": _("Telemedicine Threads"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "kanban,list,form",
            "domain": [("handler_id", "=", self.id)],
            "context": {
                "default_handler_id": self.id,
                "default_company_id": self.company_id.id
                if self.company_id
                else self.env.company.id,
            },
        }


class ClinicDoctor(models.Model):
    """Doctor navigation; Doctor capability remains owned by clinic_doctor."""

    _inherit = "clinic.doctor"

    telemedicine_session_ids = fields.One2many(
        "clinic.telemedicine.session",
        "doctor_id",
        string="Telemedicine Sessions",
        readonly=True,
    )
    telemedicine_thread_ids = fields.One2many(
        "clinic.telemedicine.thread",
        "doctor_id",
        string="Secure Threads",
        readonly=True,
    )
    telemedicine_session_count = fields.Integer(
        compute="_compute_telemedicine_counts"
    )
    telemedicine_thread_count = fields.Integer(
        compute="_compute_telemedicine_counts"
    )

    def _compute_telemedicine_counts(self):
        for doctor in self:
            doctor.telemedicine_session_count = len(
                doctor.telemedicine_session_ids
            )
            doctor.telemedicine_thread_count = len(
                doctor.telemedicine_thread_ids.filtered(
                    lambda thread: thread.state != "archived"
                )
            )

    def action_open_telemedicine_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Teleconsultations"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": [("doctor_id", "=", self.id)],
        }

    def action_open_telemedicine_threads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Secure Threads"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "kanban,list,form",
            "domain": [("doctor_id", "=", self.id)],
        }


class ClinicPatient(models.Model):
    """Patient navigation without taking ownership of Patient identity."""

    _inherit = "clinic.patient"

    telemedicine_session_ids = fields.One2many(
        "clinic.telemedicine.session",
        "patient_id",
        string="Telemedicine Sessions",
        readonly=True,
    )
    telemedicine_thread_ids = fields.One2many(
        "clinic.telemedicine.thread",
        "patient_id",
        string="Secure Threads",
        readonly=True,
    )
    telemedicine_session_count = fields.Integer(
        compute="_compute_telemedicine_counts"
    )
    telemedicine_thread_count = fields.Integer(
        compute="_compute_telemedicine_counts"
    )

    def _compute_telemedicine_counts(self):
        for patient in self:
            patient.telemedicine_session_count = len(
                patient.telemedicine_session_ids
            )
            patient.telemedicine_thread_count = len(
                patient.telemedicine_thread_ids.filtered(
                    lambda thread: thread.state != "archived"
                )
            )

    def action_open_telemedicine_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Teleconsultations"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": [("patient_id", "=", self.id)],
        }

    def action_open_telemedicine_threads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Secure Threads"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "kanban,list,form",
            "domain": [("patient_id", "=", self.id)],
        }


class ResPartner(models.Model):
    """Stable native Contact-form bridge for Telemedicine patient navigation.

    The failed 19.0.1.0.0 package inherited a clinic_patient custom form XML ID
    that is present in source but absent from the user's installed database.
    To keep Patient smart navigation without requiring an upstream upgrade,
    addon 33 now extends Odoo's native `res.partner` model/view boundary.
    """

    _inherit = "res.partner"

    clinic_telemedicine_session_count = fields.Integer(
        string="Telemedicine Sessions",
        compute="_compute_clinic_telemedicine_counts",
    )
    clinic_telemedicine_thread_count = fields.Integer(
        string="Secure Threads",
        compute="_compute_clinic_telemedicine_counts",
    )

    def _compute_clinic_telemedicine_counts(self):
        Session = self.env["clinic.telemedicine.session"].sudo()
        Thread = self.env["clinic.telemedicine.thread"].sudo()

        for partner in self:
            patient = partner.patient_id
            if not patient:
                partner.clinic_telemedicine_session_count = 0
                partner.clinic_telemedicine_thread_count = 0
                continue

            partner.clinic_telemedicine_session_count = Session.search_count([
                ("patient_id", "=", patient.id),
                ("company_id", "in", self.env.companies.ids),
            ])
            partner.clinic_telemedicine_thread_count = Thread.search_count([
                ("patient_id", "=", patient.id),
                ("company_id", "in", self.env.companies.ids),
                ("state", "!=", "archived"),
            ])

    def action_open_clinic_telemedicine_sessions(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("This Contact has no linked Patient Card."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Teleconsultations"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": [
                ("patient_id", "=", self.patient_id.id),
                ("company_id", "in", self.env.companies.ids),
            ],
        }

    def action_open_clinic_telemedicine_threads(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("This Contact has no linked Patient Card."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Secure Threads"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "kanban,list,form",
            "domain": [
                ("patient_id", "=", self.patient_id.id),
                ("company_id", "in", self.env.companies.ids),
                ("state", "!=", "archived"),
            ],
        }


class ClinicAppointment(models.Model):
    """Telemedicine Session creation from the Doctor-owned Appointment."""

    _inherit = "clinic.appointment"

    telemedicine_session_ids = fields.One2many(
        "clinic.telemedicine.session",
        "appointment_id",
        string="Telemedicine Sessions",
        readonly=True,
    )
    telemedicine_session_count = fields.Integer(
        compute="_compute_telemedicine_session_count"
    )

    def _compute_telemedicine_session_count(self):
        for appointment in self:
            appointment.telemedicine_session_count = len(
                appointment.telemedicine_session_ids
            )

    def _require_telemedicine_clinician(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
        ):
            raise AccessError(_("Telemedicine Clinician access is required."))
        return True

    def action_create_telemedicine_session(self):
        self.ensure_one()
        self._require_telemedicine_clinician()

        existing = self.telemedicine_session_ids[:1]
        if existing:
            return _telemedicine_form_action(existing)

        if not self.telemedicine:
            raise UserError(
                _("Enable Telemedicine on the Appointment before creating a Session.")
            )
        if self.state in ("done", "canceled", "no_show"):
            raise UserError(
                _("A completed/cancelled/no-show Appointment cannot create a new Session.")
            )
        if not self.doctor_id.telemedicine_enabled:
            raise UserError(
                _("The Appointment Doctor is not enabled for Telemedicine.")
            )

        patient = self.patient_id or self.partner_id.patient_id
        if not patient:
            raise UserError(
                _("The Appointment Patient Contact has no linked Patient Card.")
            )

        booking = self.env["booking.booking"].search([
            ("appointment_id", "=", self.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

        # Reuse a Booking-created Session if it already represents this source.
        if booking and booking.telemedicine_session_ids:
            session = booking.telemedicine_session_ids[:1]
            if not session.appointment_id:
                session.appointment_id = self.id
            return _telemedicine_form_action(session)

        session = self.env["clinic.telemedicine.session"].create({
            "company_id": self.company_id.id,
            "branch_id": patient.partner_id.branch_id.id
            if (
                self.company_id.policy_branch_scope_telemedicine
                and patient.partner_id.branch_id
            )
            else False,
            "patient_id": patient.id,
            "doctor_id": self.doctor_id.id,
            "appointment_id": self.id,
            "booking_id": booking.id if booking else False,
            "scheduled_start": self.start,
            "scheduled_end": self.end,
        })
        return _telemedicine_form_action(session)

    def action_open_telemedicine_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment Telemedicine Sessions"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": [("appointment_id", "=", self.id)],
        }


class BookingBooking(models.Model):
    """Telemedicine Session creation from Booking without changing Booking state."""

    _inherit = "booking.booking"

    telemedicine_session_ids = fields.One2many(
        "clinic.telemedicine.session",
        "booking_id",
        string="Telemedicine Sessions",
        readonly=True,
    )
    telemedicine_session_count = fields.Integer(
        compute="_compute_telemedicine_session_count"
    )

    def _compute_telemedicine_session_count(self):
        for booking in self:
            booking.telemedicine_session_count = len(
                booking.telemedicine_session_ids
            )

    def _require_telemedicine_clinician(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
        ):
            raise AccessError(_("Telemedicine Clinician access is required."))
        return True

    def action_create_telemedicine_session(self):
        self.ensure_one()
        self._require_telemedicine_clinician()

        existing = self.telemedicine_session_ids[:1]
        if existing:
            return _telemedicine_form_action(existing)

        if self.state in ("done", "cancelled"):
            raise UserError(
                _("A completed/cancelled Booking cannot create a new Session.")
            )
        if not self.doctor_id:
            raise UserError(_("Select a Doctor before creating a Telemedicine Session."))
        if not self.doctor_id.telemedicine_enabled:
            raise UserError(
                _("The Booking Doctor is not enabled for Telemedicine.")
            )

        patient = self.patient_id.patient_id
        if not patient:
            raise UserError(
                _("The Booking Patient Contact has no linked Patient Card.")
            )

        appointment = self.appointment_id
        if appointment and appointment.telemedicine_session_ids:
            session = appointment.telemedicine_session_ids[:1]
            if not session.booking_id:
                session.booking_id = self.id
            return _telemedicine_form_action(session)

        values = {
            "company_id": self.company_id.id,
            "branch_id": patient.partner_id.branch_id.id
            if (
                self.company_id.policy_branch_scope_telemedicine
                and patient.partner_id.branch_id
            )
            else False,
            "patient_id": patient.id,
            "doctor_id": self.doctor_id.id,
            "booking_id": self.id,
            "scheduled_start": self.start_datetime,
            "scheduled_end": self.end_datetime,
        }
        if appointment and appointment.telemedicine:
            values["appointment_id"] = appointment.id

        session = self.env["clinic.telemedicine.session"].create(values)
        return _telemedicine_form_action(session)

    def action_open_telemedicine_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking Telemedicine Sessions"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": [("booking_id", "=", self.id)],
        }


class ClinicQueue(models.Model):
    """Activate the historical Queue-to-Telemedicine Session reference."""

    _inherit = "clinic.queue"

    telemedicine_session_id = fields.Many2one(
        "clinic.telemedicine.session",
        string="Telemedicine Session",
        ondelete="set null",
        check_company=True,
        index=True,
        help="Telemedicine Session linked to this Queue, when applicable.",
    )

    def action_open_telemedicine_session(self):
        self.ensure_one()
        if not self.telemedicine_session_id:
            raise UserError(_("This Queue has no linked Telemedicine Session."))
        return _telemedicine_form_action(self.telemedicine_session_id)


class ClinicEncounter(models.Model):
    """Encounter reverse link; clinical documentation remains Encounter-owned."""

    _inherit = "clinic.encounter"

    telemedicine_session_ids = fields.One2many(
        "clinic.telemedicine.session",
        "encounter_id",
        string="Telemedicine Sessions",
        readonly=True,
    )
    telemedicine_session_count = fields.Integer(
        compute="_compute_telemedicine_session_count"
    )

    def _compute_telemedicine_session_count(self):
        for encounter in self:
            encounter.telemedicine_session_count = len(
                encounter.telemedicine_session_ids
            )

    def action_open_telemedicine_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Encounter Telemedicine Sessions"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": [("encounter_id", "=", self.id)],
        }

