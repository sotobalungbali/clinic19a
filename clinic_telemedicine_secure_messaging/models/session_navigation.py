from odoo import models, _
from odoo.exceptions import UserError


class ClinicTelemedicineSessionNavigation(models.Model):
    """Session relationship creation and human-friendly navigation actions."""

    _inherit = "clinic.telemedicine.session"

    def _ensure_secure_thread(self):
        self.ensure_one()
        thread = self.thread_ids[:1]
        if thread:
            return thread

        values = {
            "session_id": self.id,
            "company_id": self.company_id.id,
            "branch_id": self.branch_id.id if self.branch_id else False,
            "patient_id": self.patient_id.id,
            "doctor_id": self.doctor_id.id,
            "handler_id": self.host_staff_id.id if self.host_staff_id else False,
            "subject": _("Teleconsultation %(session)s") % {
                "session": self.name,
            },
            "state": "open",
        }
        return self.env["clinic.telemedicine.thread"].with_context(
            telemedicine_thread_system_create=True
        ).create(values)

    def action_open_thread(self):
        self.ensure_one()
        self._require_clinician()
        thread = self._ensure_secure_thread()
        return {
            "type": "ir.actions.act_window",
            "name": _("Secure Conversation"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "form",
            "res_id": thread.id,
        }

    def action_open_queues(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Telemedicine Queues"),
            "res_model": "clinic.queue",
            "view_mode": "list,form",
            "domain": [("telemedicine_session_id", "=", self.id)],
            "context": {
                "default_telemedicine_session_id": self.id,
                "default_queue_type": "telemedicine",
                "default_channel": "telemedicine",
            },
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

    def action_open_booking(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("This Session is not linked to a Booking."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking"),
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
        }

    def action_open_appointment(self):
        self.ensure_one()
        if not self.appointment_id:
            raise UserError(_("This Session is not linked to an Appointment."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "res_id": self.appointment_id.id,
        }

    def action_open_encounter(self):
        self.ensure_one()
        if not self.encounter_id:
            raise UserError(_("This Session is not linked to an Encounter."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Encounter"),
            "res_model": "clinic.encounter",
            "view_mode": "form",
            "res_id": self.encounter_id.id,
        }

    def action_open_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.portal_url,
            "target": "new",
        }

