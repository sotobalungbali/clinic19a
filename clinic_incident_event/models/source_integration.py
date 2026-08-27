from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _open_incident_cases(record, domain, defaults=None, name=None):
    """Reusable standalone Incident action without inheriting fragile views."""
    record.ensure_one()
    context = dict(defaults or {})
    return {
        "type": "ir.actions.act_window",
        "name": name or _("Incident Cases"),
        "res_model": "clinic.incident",
        "view_mode": "kanban,list,form",
        "domain": domain,
        "context": context,
    }


class ClinicIncidentSourceHelpers(models.Model):
    """Normalize source context without moving upstream model ownership."""

    _inherit = "clinic.incident"

    @api.model
    def _category_for_type(self, company, incident_type):
        Category = self.env["clinic.incident.category"]

        category = Category.search([
            ("incident_type", "=", incident_type),
            ("company_id", "=", company.id),
            ("active", "=", True),
        ], limit=1)

        if not category:
            category = Category.search([
                ("incident_type", "=", incident_type),
                ("company_id", "=", False),
                ("active", "=", True),
            ], limit=1)

        if not category:
            raise UserError(
                _(
                    "No active Incident Category exists for type %(type)s."
                ) % {"type": incident_type}
            )
        return category

    @api.onchange("adverse_event_id")
    def _onchange_adverse_event_id(self):
        for incident in self:
            adverse = incident.adverse_event_id
            if not adverse:
                continue

            incident.company_id = adverse.company_id
            incident.patient_id = adverse.patient_id
            incident.doctor_id = adverse.doctor_id
            incident.encounter_id = adverse.encounter_id
            incident.room_id = adverse.room_id
            incident.occurred_at = adverse.date_occurred
            incident.detected_at = adverse.date_detected
            incident.description = adverse.description
            incident.immediate_action = adverse.immediate_action
            incident.patient_impact = adverse.patient_impact
            incident.recurrence_risk = adverse.recurrence_risk
            incident.regulatory_required = bool(
                adverse.needs_reporting
                or adverse.to_regulator
            )
            incident.regulator_body = adverse.regulator_body
            incident.regulator_reference = adverse.regulator_reference
            incident.incident_type = "clinical_adverse"

            severity_map = {
                "none": "low",
                "minor": "low",
                "moderate": "medium",
                "severe": "high",
                "death": "critical",
            }
            incident.severity = severity_map.get(
                adverse.severity,
                "medium",
            )

            classification_map = {
                "near_miss": "near_miss",
                "no_harm": "no_harm",
                "harm": "adverse_event",
                "sentinel": "sentinel",
            }
            incident.classification = classification_map.get(
                adverse.classification,
                "adverse_event",
            )
            incident.harm_level = adverse.severity or "none"

    @api.onchange("telemedicine_session_id")
    def _onchange_telemedicine_session_id(self):
        for incident in self:
            session = incident.telemedicine_session_id
            if not session:
                continue

            incident.company_id = session.company_id
            incident.branch_id = session.branch_id
            incident.patient_id = session.patient_id
            incident.doctor_id = session.doctor_id
            incident.encounter_id = session.encounter_id
            incident.booking_id = session.booking_id
            incident.incident_type = "telemedicine"

            if session.host_staff_id:
                incident.involved_staff_ids = [
                    fields.Command.set([session.host_staff_id.id])
                ]

    @api.onchange("telemedicine_thread_id")
    def _onchange_telemedicine_thread_id(self):
        for incident in self:
            thread = incident.telemedicine_thread_id
            if not thread:
                continue

            incident.company_id = thread.company_id
            incident.branch_id = thread.branch_id
            incident.patient_id = thread.patient_id
            incident.doctor_id = thread.doctor_id
            incident.telemedicine_session_id = thread.session_id
            incident.incident_type = "telemedicine"

            if thread.handler_id:
                incident.involved_staff_ids = [
                    fields.Command.set([thread.handler_id.id])
                ]

            # IMPORTANT: never copy thread message bodies or internal secure
            # notes. The Incident stores only provenance plus a neutral pointer.
            if not incident.description:
                incident.description = _(
                    "Incident reported from Secure Telemedicine Thread "
                    "%(thread)s. Review source content only through the "
                    "authorized Telemedicine owner UI."
                ) % {"thread": thread.display_name}

    @api.onchange("emar_administration_id")
    def _onchange_emar_administration_id(self):
        for incident in self:
            administration = incident.emar_administration_id
            if not administration:
                continue

            incident.company_id = administration.company_id
            incident.patient_id = administration.patient_id
            incident.doctor_id = administration.doctor_id
            incident.incident_type = "medication"

            if not incident.description:
                incident.description = _(
                    "Incident linked to eMAR Administration %(record)s."
                ) % {
                    "record": administration.display_name,
                }

    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        for incident in self:
            booking = incident.booking_id
            if not booking:
                continue

            incident.company_id = booking.company_id
            incident.patient_id = (
                booking.patient_id.patient_id
                if booking.patient_id
                else False
            )
            incident.doctor_id = booking.doctor_id
            incident.occurred_at = (
                booking.start_datetime
                or incident.occurred_at
            )

    @api.onchange("queue_id")
    def _onchange_queue_id(self):
        for incident in self:
            queue = incident.queue_id
            if not queue:
                continue

            incident.company_id = queue.company_id
            incident.patient_id = (
                queue.patient_id.patient_id
                if queue.patient_id
                else False
            )
            incident.room_id = queue.room_id
            incident.occurred_at = (
                queue.checkin_time
                or incident.occurred_at
            )

    @api.onchange("feedback_escalation_id")
    def _onchange_feedback_escalation_id(self):
        for incident in self:
            escalation = incident.feedback_escalation_id
            if not escalation:
                continue

            incident.company_id = escalation.company_id
            incident.branch_id = escalation.branch_id
            incident.patient_id = (
                escalation.patient_id.patient_id
                if escalation.patient_id
                else False
            )

            category_map = {
                "service": "service",
                "doctor": "service",
                "staff": "service",
                "waiting": "service",
                "communication": "service",
                "postcare": "service",
                "facility": "facility",
                "billing": "operational",
                "other": "operational",
            }
            incident.incident_type = category_map.get(
                escalation.category,
                "operational",
            )
            incident.severity = escalation.severity or "medium"


class ClinicAdverseEventIncidentBridge(models.Model):
    """Escalate an existing clinical Adverse Event into a central Incident."""

    _inherit = "clinic.adverse.event"

    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        Incident = self.env["clinic.incident"]
        for adverse in self:
            adverse.incident_count = Incident.search_count([
                ("adverse_event_id", "=", adverse.id),
            ])

    def action_create_incident_case(self):
        self.ensure_one()

        existing = self.env["clinic.incident"].search([
            ("adverse_event_id", "=", self.id),
        ], limit=1)
        if existing:
            return existing._incident_form_action()

        Incident = self.env["clinic.incident"]
        category = Incident._category_for_type(
            self.company_id,
            "clinical_adverse",
        )

        severity_map = {
            "none": "low",
            "minor": "low",
            "moderate": "medium",
            "severe": "high",
            "death": "critical",
        }
        classification_map = {
            "near_miss": "near_miss",
            "no_harm": "no_harm",
            "harm": "adverse_event",
            "sentinel": "sentinel",
        }

        staff = self.env["clinic.staff"].search([
            ("partner_id", "=", self.reported_by_id.partner_id.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

        branch = Incident._default_incident_branch(
            self.company_id,
            patient_id=self.patient_id.id,
        )

        incident = Incident.create({
            "company_id": self.company_id.id,
            "branch_id": branch.id if branch else False,
            "category_id": category.id,
            "title": _("Adverse Event %(reference)s") % {
                "reference": self.name,
            },
            "incident_type": "clinical_adverse",
            "classification": classification_map.get(
                self.classification,
                "adverse_event",
            ),
            "severity": severity_map.get(
                self.severity,
                "medium",
            ),
            "harm_level": self.severity or "none",
            "recurrence_risk": self.recurrence_risk or "low",
            "occurred_at": self.date_occurred,
            "detected_at": self.date_detected,
            "patient_id": self.patient_id.id,
            "doctor_id": (
                self.doctor_id.id
                if self.doctor_id
                else False
            ),
            "involved_staff_ids": (
                [fields.Command.set([staff.id])]
                if staff
                else False
            ),
            "room_id": (
                self.room_id.id
                if self.room_id
                else False
            ),
            "encounter_id": self.encounter_id.id,
            "adverse_event_id": self.id,
            "description": self.description,
            "immediate_action": self.immediate_action,
            "patient_impact": self.patient_impact,
            "regulatory_required": bool(
                self.needs_reporting
                or self.to_regulator
            ),
            "regulator_body": self.regulator_body,
            "regulator_reference": self.regulator_reference,
        })
        incident._log_timeline(
            "source",
            _("Created from Adverse Event"),
            self.display_name,
        )
        return incident._incident_form_action()

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("adverse_event_id", "=", self.id)],
            defaults={
                "default_adverse_event_id": self.id,
                "default_company_id": self.company_id.id,
            },
            name=_("Adverse Event Incident Case"),
        )


class ClinicEncounterIncidentBridge(models.Model):
    """Encounter reverse navigation only; Encounter workflow remains upstream."""

    _inherit = "clinic.encounter"

    incident_ids = fields.One2many(
        "clinic.incident",
        "encounter_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for encounter in self:
            encounter.incident_count = len(encounter.incident_ids)

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("encounter_id", "=", self.id)],
            defaults={
                "default_encounter_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_company_id": self.company_id.id,
            },
            name=_("Encounter Incident Cases"),
        )


class ClinicPatientIncidentBridge(models.Model):
    """Patient Card reverse navigation without taking Patient ownership."""

    _inherit = "clinic.patient"

    incident_ids = fields.One2many(
        "clinic.incident",
        "patient_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for patient in self:
            patient.incident_count = len(patient.incident_ids)

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("patient_id", "=", self.id)],
            defaults={
                "default_patient_id": self.id,
                "default_company_id": self.company_id.id,
            },
            name=_("Patient Incident Cases"),
        )


class ClinicDoctorIncidentBridge(models.Model):
    """Doctor reverse navigation without modifying Doctor workflow."""

    _inherit = "clinic.doctor"

    incident_ids = fields.One2many(
        "clinic.incident",
        "doctor_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for doctor in self:
            doctor.incident_count = len(doctor.incident_ids)

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("doctor_id", "=", self.id)],
            defaults={
                "default_doctor_id": self.id,
                "default_company_id": self.company_id.id,
            },
            name=_("Doctor Incident Cases"),
        )


class BookingIncidentBridge(models.Model):
    """Booking provenance only; booking state remains untouched."""

    _inherit = "booking.booking"

    incident_ids = fields.One2many(
        "clinic.incident",
        "booking_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for booking in self:
            booking.incident_count = len(booking.incident_ids)

    def action_open_incident_cases(self):
        patient = self.patient_id.patient_id if self.patient_id else False
        return _open_incident_cases(
            self,
            [("booking_id", "=", self.id)],
            defaults={
                "default_booking_id": self.id,
                "default_patient_id": patient.id if patient else False,
                "default_doctor_id": self.doctor_id.id,
                "default_company_id": self.company_id.id,
            },
            name=_("Booking Incident Cases"),
        )


class ClinicQueueIncidentBridge(models.Model):
    """Queue provenance only; Queue doctor remains hr.employee upstream."""

    _inherit = "clinic.queue"

    incident_ids = fields.One2many(
        "clinic.incident",
        "queue_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for queue in self:
            queue.incident_count = len(queue.incident_ids)

    def action_open_incident_cases(self):
        patient = self.patient_id.patient_id if self.patient_id else False
        return _open_incident_cases(
            self,
            [("queue_id", "=", self.id)],
            defaults={
                "default_queue_id": self.id,
                "default_patient_id": patient.id if patient else False,
                "default_company_id": self.company_id.id,
            },
            name=_("Queue Incident Cases"),
        )


