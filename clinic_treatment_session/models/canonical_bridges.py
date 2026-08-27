# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ClinicPatientTreatmentSessionBridge(models.Model):
    """Canonical Patient 360 counters for Treatment Sessions."""

    _inherit = "clinic.patient"

    treatment_session_count = fields.Integer(
        compute="_compute_treatment_session_bridge_counts"
    )
    active_treatment_session_count = fields.Integer(
        compute="_compute_treatment_session_bridge_counts"
    )

    def _compute_treatment_session_bridge_counts(self):
        Session = self.env["clinic.treatment.session"]
        for patient in self:
            partner = patient.partner_id
            if not partner:
                patient.treatment_session_count = 0
                patient.active_treatment_session_count = 0
                continue

            domain = [("patient_id", "=", partner.id)]
            patient.treatment_session_count = Session.search_count(domain)
            patient.active_treatment_session_count = Session.search_count(
                domain
                + [
                    (
                        "state",
                        "in",
                        ("draft", "confirmed", "in_progress"),
                    )
                ]
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Sessions"),
            "res_model": "clinic.treatment.session",
            "view_mode": "list,kanban,form",
            "domain": [("clinic_patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.partner_id.id,
            },
        }


class ClinicDoctorTreatmentSessionBridge(models.Model):
    """Canonical Clinic Doctor operational counters."""

    _inherit = "clinic.doctor"

    treatment_session_count = fields.Integer(
        compute="_compute_treatment_session_bridge_counts"
    )
    treatment_session_in_progress_count = fields.Integer(
        compute="_compute_treatment_session_bridge_counts"
    )

    def _compute_treatment_session_bridge_counts(self):
        Session = self.env["clinic.treatment.session"]
        for doctor in self:
            domain = [("doctor_id", "=", doctor.id)]
            doctor.treatment_session_count = Session.search_count(domain)
            doctor.treatment_session_in_progress_count = Session.search_count(
                domain + [("state", "=", "in_progress")]
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Sessions"),
            "res_model": "clinic.treatment.session",
            "view_mode": "list,calendar,form",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
        }


class ClinicEncounterTreatmentSessionBridge(models.Model):
    """Encounter bridge kept distinct from legacy Procedure Session fields."""

    _inherit = "clinic.encounter"

    treatment_session_ids = fields.One2many(
        "clinic.treatment.session",
        "encounter_id",
        string="Treatment Sessions",
        readonly=True,
    )
    treatment_session_count = fields.Integer(
        compute="_compute_treatment_session_count"
    )

    @api.depends("treatment_session_ids")
    def _compute_treatment_session_count(self):
        for encounter in self:
            encounter.treatment_session_count = len(
                encounter.treatment_session_ids
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Encounter Treatment Sessions"),
            "res_model": "clinic.treatment.session",
            "view_mode": "list,kanban,form",
            "domain": [("encounter_id", "=", self.id)],
            "context": {
                "default_encounter_id": self.id,
                "default_booking_id": self.appointment_id.id,
                "default_patient_id": self.partner_id.id,
                "default_doctor_id": self.doctor_id.id,
            },
        }


class ClinicBranchTreatmentSessionBridge(models.Model):
    """Branch workload bridge."""

    _inherit = "clinic.branch"

    treatment_session_count = fields.Integer(
        compute="_compute_treatment_session_count"
    )
    treatment_session_today_count = fields.Integer(
        compute="_compute_treatment_session_count"
    )

    def _compute_treatment_session_count(self):
        Session = self.env["clinic.treatment.session"]
        today = fields.Date.context_today(self)
        start = fields.Datetime.to_datetime(today)
        end = fields.Datetime.add(start, days=1)

        for branch in self:
            domain = [("branch_id", "=", branch.id)]
            branch.treatment_session_count = Session.search_count(domain)
            branch.treatment_session_today_count = Session.search_count(
                domain
                + [
                    ("start_datetime", ">=", start),
                    ("start_datetime", "<", end),
                ]
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Branch Treatment Sessions"),
            "res_model": "clinic.treatment.session",
            "view_mode": "list,calendar,form",
            "domain": [("branch_id", "=", self.id)],
            "context": {
                "default_branch_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }
