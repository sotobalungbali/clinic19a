
# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ClinicPatientTreatmentSessionBridge(models.Model):
    """Canonical Patient 360 Treatment Session counters."""

    _inherit = "clinic.patient"

    treatment_session_count = fields.Integer(compute="_compute_treatment_session_bridge_counts")
    active_treatment_session_count = fields.Integer(compute="_compute_treatment_session_bridge_counts")

    def _compute_treatment_session_bridge_counts(self):
        Session = self.env["clinic.treatment.session"]
        for rec in self:
            partner = rec.partner_id if "partner_id" in rec._fields else False
            domain = [("patient_id", "=", partner.id)] if partner else [("id", "=", 0)]
            rec.treatment_session_count = Session.search_count(domain)
            rec.active_treatment_session_count = Session.search_count(
                domain + [("state", "in", ("draft", "confirmed", "in_progress"))]
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Treatment Sessions"),
            "res_model": "clinic.treatment.session", "view_mode": "list,kanban,form",
            "domain": [("clinic_patient_id", "=", self.id)],
        }


class ClinicDoctorTreatmentSessionBridge(models.Model):
    """Canonical Clinic Doctor Treatment Session counters."""

    _inherit = "clinic.doctor"

    treatment_session_count = fields.Integer(compute="_compute_treatment_session_bridge_counts")
    treatment_session_in_progress_count = fields.Integer(compute="_compute_treatment_session_bridge_counts")

    def _compute_treatment_session_bridge_counts(self):
        Session = self.env["clinic.treatment.session"]
        for rec in self:
            domain = [("doctor_id", "=", rec.id)]
            rec.treatment_session_count = Session.search_count(domain)
            rec.treatment_session_in_progress_count = Session.search_count(
                domain + [("state", "=", "in_progress")]
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Treatment Sessions"),
            "res_model": "clinic.treatment.session", "view_mode": "list,calendar,form",
            "domain": [("doctor_id", "=", self.id)],
        }


class ClinicEncounterTreatmentSessionBridge(models.Model):
    """Encounter → Treatment Session bridge."""

    _inherit = "clinic.encounter"

    treatment_session_ids = fields.One2many(
        "clinic.treatment.session", "encounter_id", readonly=True,
    )
    treatment_session_count = fields.Integer(compute="_compute_treatment_session_count")

    def _compute_treatment_session_count(self):
        for rec in self:
            rec.treatment_session_count = len(rec.treatment_session_ids)

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Treatment Sessions"),
            "res_model": "clinic.treatment.session", "view_mode": "list,kanban,form",
            "domain": [("encounter_id", "=", self.id)],
        }


class ClinicBranchTreatmentSessionBridge(models.Model):
    """Branch workload bridge."""

    _inherit = "clinic.branch"

    treatment_session_count = fields.Integer(compute="_compute_treatment_session_count")
    treatment_session_today_count = fields.Integer(compute="_compute_treatment_session_count")

    def _compute_treatment_session_count(self):
        Session = self.env["clinic.treatment.session"]
        today = fields.Date.context_today(self)
        start = fields.Datetime.to_datetime(today)
        end = fields.Datetime.add(start, days=1)
        for rec in self:
            domain = [("branch_id", "=", rec.id)]
            rec.treatment_session_count = Session.search_count(domain)
            rec.treatment_session_today_count = Session.search_count(
                domain + [("start_datetime", ">=", start), ("start_datetime", "<", end)]
            )

    def action_view_treatment_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Branch Treatment Sessions"),
            "res_model": "clinic.treatment.session", "view_mode": "list,calendar,form",
            "domain": [("branch_id", "=", self.id)],
        }
