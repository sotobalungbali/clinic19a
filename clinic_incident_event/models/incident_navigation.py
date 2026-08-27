from odoo import models, _
from odoo.exceptions import UserError


class ClinicIncidentNavigation(models.Model):
    """Human-friendly Incident smart-button and report navigation."""

    _inherit = "clinic.incident"

    def _incident_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Incident"),
            "res_model": "clinic.incident",
            "view_mode": "form",
            "res_id": self.id,
        }

    def _open_related_record(self, record, name):
        self.ensure_one()
        if not record:
            raise UserError(
                _("This Incident has no linked %(name)s.") % {"name": name}
            )
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": record._name,
            "view_mode": "form",
            "res_id": record.id,
        }

    def action_open_patient(self):
        self.ensure_one()
        return self._open_related_record(
            self.patient_id,
            _("Patient Card"),
        )

    def action_open_encounter(self):
        self.ensure_one()
        return self._open_related_record(
            self.encounter_id,
            _("Encounter"),
        )

    def action_open_adverse_event(self):
        self.ensure_one()
        return self._open_related_record(
            self.adverse_event_id,
            _("Adverse Event"),
        )

    def action_open_booking(self):
        self.ensure_one()
        return self._open_related_record(
            self.booking_id,
            _("Booking"),
        )

    def action_open_queue(self):
        self.ensure_one()
        return self._open_related_record(
            self.queue_id,
            _("Queue"),
        )

    def action_open_emar_administration(self):
        self.ensure_one()
        return self._open_related_record(
            self.emar_administration_id,
            _("eMAR Administration"),
        )

    def action_open_telemedicine_session(self):
        self.ensure_one()
        return self._open_related_record(
            self.telemedicine_session_id,
            _("Telemedicine Session"),
        )

    def action_open_secure_thread(self):
        self.ensure_one()
        return self._open_related_record(
            self.telemedicine_thread_id,
            _("Secure Thread"),
        )

    def action_open_feedback_escalation(self):
        self.ensure_one()
        return self._open_related_record(
            self.feedback_escalation_id,
            _("Feedback Escalation"),
        )

    def action_open_investigations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Incident Investigations"),
            "res_model": "clinic.incident.investigation",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    def action_open_actions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Corrective / Preventive Actions"),
            "res_model": "clinic.incident.action",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    def action_open_timeline(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Incident Timeline"),
            "res_model": "clinic.incident.timeline",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
        }

    def action_print_case_summary(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_incident_event.action_report_incident_case"
        ).report_action(self)
