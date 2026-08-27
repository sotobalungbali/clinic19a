from odoo import fields, models, _

from .source_integration import _open_incident_cases


class ClinicEmarAdministrationIncidentBridge(models.Model):
    """Medication administration provenance; eMAR remains source owner."""

    _inherit = "clinic.emar.administration"

    incident_ids = fields.One2many(
        "clinic.incident",
        "emar_administration_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for administration in self:
            administration.incident_count = len(
                administration.incident_ids
            )

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("emar_administration_id", "=", self.id)],
            defaults={
                "default_emar_administration_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_doctor_id": (
                    self.doctor_id.id
                    if self.doctor_id
                    else False
                ),
                "default_company_id": self.company_id.id,
            },
            name=_("eMAR Incident Cases"),
        )


class ClinicFeedbackEscalationIncidentBridge(models.Model):
    """Promote service-recovery escalation into compliance Incident context."""

    _inherit = "clinic.feedback.escalation"

    incident_ids = fields.One2many(
        "clinic.incident",
        "feedback_escalation_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for escalation in self:
            escalation.incident_count = len(
                escalation.incident_ids
            )

    def action_open_incident_cases(self):
        patient = (
            self.patient_id.patient_id
            if self.patient_id
            else False
        )
        return _open_incident_cases(
            self,
            [("feedback_escalation_id", "=", self.id)],
            defaults={
                "default_feedback_escalation_id": self.id,
                "default_patient_id": patient.id if patient else False,
                "default_company_id": self.company_id.id,
                "default_branch_id": (
                    self.branch_id.id
                    if self.branch_id
                    else False
                ),
            },
            name=_("Feedback Incident Cases"),
        )


class ClinicTelemedicineSessionIncidentBridge(models.Model):
    """Telemedicine provenance without copying Secure Messaging content."""

    _inherit = "clinic.telemedicine.session"

    incident_ids = fields.One2many(
        "clinic.incident",
        "telemedicine_session_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for session in self:
            session.incident_count = len(session.incident_ids)

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("telemedicine_session_id", "=", self.id)],
            defaults={
                "default_telemedicine_session_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_doctor_id": self.doctor_id.id,
                "default_company_id": self.company_id.id,
                "default_branch_id": (
                    self.branch_id.id
                    if self.branch_id
                    else False
                ),
            },
            name=_("Telemedicine Incident Cases"),
        )


class ClinicTelemedicineThreadIncidentBridge(models.Model):
    """Secure Thread provenance; Secure content remains in addon 33."""

    _inherit = "clinic.telemedicine.thread"

    incident_ids = fields.One2many(
        "clinic.incident",
        "telemedicine_thread_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count"
    )

    def _compute_incident_count(self):
        for thread in self:
            thread.incident_count = len(thread.incident_ids)

    def action_open_incident_cases(self):
        return _open_incident_cases(
            self,
            [("telemedicine_thread_id", "=", self.id)],
            defaults={
                "default_telemedicine_thread_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_doctor_id": self.doctor_id.id,
                "default_company_id": self.company_id.id,
                "default_branch_id": (
                    self.branch_id.id
                    if self.branch_id
                    else False
                ),
            },
            name=_("Secure Thread Incident Cases"),
        )


class ResPartnerIncidentBridge(models.Model):
    """Stable native Contact-form navigation through Patient Card ownership."""

    _inherit = "res.partner"

    clinic_incident_count = fields.Integer(
        compute="_compute_clinic_incident_count"
    )

    def _compute_clinic_incident_count(self):
        Incident = self.env["clinic.incident"].sudo()
        for partner in self:
            partner.clinic_incident_count = 0
            if not partner.patient_id:
                continue

            partner.clinic_incident_count = Incident.search_count([
                ("patient_id", "=", partner.patient_id.id),
                ("company_id", "in", self.env.companies.ids),
            ])

    def action_open_clinic_incidents(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(
                _("This Contact has no linked Patient Card.")
            )
        return _open_incident_cases(
            self,
            [
                ("patient_id", "=", self.patient_id.id),
                ("company_id", "in", self.env.companies.ids),
            ],
            name=_("Patient Incident Cases"),
        )


class ClinicStaffIncidentBridge(models.Model):
    """Activate the historical Staff Incident smart-counter contract."""

    _inherit = "clinic.staff"

    def _compute_counts(self):
        # Preserve every upstream/post-care/telemedicine counter first.
        super()._compute_counts()

        Incident = self.env["clinic.incident"].sudo()
        for staff in self:
            staff.incident_count = Incident.search_count([
                ("company_id", "=", staff.company_id.id),
                ("involved_staff_ids", "in", staff.id),
                ("state", "!=", "cancelled"),
            ])


class ClinicStaffKPIIncidentBridge(models.Model):
    """Activate historical Staff Incident KPI fields without redesigning KPI."""

    _inherit = "clinic.staff.kpi"

    def _aggregate_from_incidents_live(self):
        Incident = self.env["clinic.incident"].sudo()

        for snapshot in self:
            if not snapshot.company_id.clinic_incident_staff_kpi_enabled:
                snapshot.incidents_count = 0
                snapshot.incidents_rate_per_100_assign = 0.0
                continue

            start_dt, end_dt = snapshot._dt_range()
            incidents = Incident.search([
                ("company_id", "=", snapshot.company_id.id),
                ("occurred_at", ">=", start_dt),
                ("occurred_at", "<=", end_dt),
                ("involved_staff_ids", "in", snapshot.staff_id.id),
                ("state", "!=", "cancelled"),
            ])

            snapshot.incidents_count = len(incidents)
            snapshot.incidents_rate_per_100_assign = (
                snapshot.incidents_count
                / snapshot.assignments_count
                * 100.0
                if snapshot.assignments_count
                else 0.0
            )

    def recompute_snapshot(
        self,
        generate_lines=True,
        replace_lines=True,
    ):
        result = super().recompute_snapshot(
            generate_lines=generate_lines,
            replace_lines=replace_lines,
        )
        self._aggregate_from_incidents_live()
        return result

    def action_open_incidents(self):
        self.ensure_one()
        start_dt, end_dt = self._dt_range()
        return {
            "name": _("Staff KPI Incident Cases"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.incident",
            "view_mode": "kanban,list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("occurred_at", ">=", start_dt),
                ("occurred_at", "<=", end_dt),
                ("involved_staff_ids", "in", self.staff_id.id),
                ("state", "!=", "cancelled"),
            ],
        }
