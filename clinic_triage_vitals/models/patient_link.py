
# -*- coding: utf-8 -*-
# File: models/patient_link.py
#
# ClinicOne - Triage & Vitals Intake
# Extension: clinic.patient (links to triage sessions & vitals)
#
# Purpose:
# - Provide quick access from Patient to all Triage Sessions and Vitals Intake.
# - Expose latest vitals snapshot and useful counters (open/completed sessions).
# - Offer helper actions (view sessions, view latest vitals, start new triage).
#
# All UI strings are in English.

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicPatient(models.Model):
    _inherit = "clinic.patient"

    # -------------------------------------------------------------------------
    # Links to Triage & Vitals (relational fields)
    # -------------------------------------------------------------------------
    triage_session_ids = fields.One2many(
        "clinic.triage.session",
        "patient_id",
        string="Triage Sessions",
        help="All triage sessions that belong to this patient."
    )
    vitals_ids = fields.One2many(
        "clinic.vitals.intake",
        "patient_id",
        string="Vitals Intake",
        help="All vital sign measurements recorded for this patient."
    )

    # -------------------------------------------------------------------------
    # Counters & Status
    # -------------------------------------------------------------------------
    triage_session_count = fields.Integer(
        string="Triage Sessions Count",
        compute="_compute_triage_metrics",
        help="Total number of triage sessions for this patient."
    )
    triage_session_open_count = fields.Integer(
        string="Open Triage Sessions",
        compute="_compute_triage_metrics",
        help="Number of triage sessions not in Completed/Cancelled state."
    )
    latest_triage_session_id = fields.Many2one(
        "clinic.triage.session",
        string="Latest Triage Session",
        compute="_compute_latest_links",
        help="The most recent triage session of this patient."
    )
    latest_vitals_id = fields.Many2one(
        "clinic.vitals.intake",
        string="Latest Vitals",
        compute="_compute_latest_links",
        help="The most recent vital sign measurement of this patient."
    )
    has_recent_abnormal_vitals = fields.Boolean(
        string="Latest Vitals Abnormal",
        compute="_compute_latest_vitals_snapshot",
        help="True when the latest vitals are marked abnormal."
    )

    # -------------------------------------------------------------------------
    # Latest Vitals Snapshot (read-only convenience fields)
    # -------------------------------------------------------------------------
    last_measure_on = fields.Datetime(
        string="Latest Measured On",
        compute="_compute_latest_vitals_snapshot",
        help="Timestamp when the latest vitals were measured."
    )
    last_temp_c = fields.Float(
        string="Latest Temp (°C)",
        compute="_compute_latest_vitals_snapshot",
        digits=(6, 2),
        help="Latest measured body temperature in Celsius."
    )
    last_hr_bpm = fields.Integer(
        string="Latest HR (bpm)",
        compute="_compute_latest_vitals_snapshot",
        help="Latest measured heart rate."
    )
    last_rr_bpm = fields.Integer(
        string="Latest RR (breaths/min)",
        compute="_compute_latest_vitals_snapshot",
        help="Latest measured respiratory rate."
    )
    last_spo2_pct = fields.Float(
        string="Latest SpO₂ (%)",
        compute="_compute_latest_vitals_snapshot",
        digits=(6, 2),
        help="Latest measured oxygen saturation percentage."
    )
    last_bp_systolic = fields.Integer(
        string="Latest SBP (mmHg)",
        compute="_compute_latest_vitals_snapshot",
        help="Latest measured systolic blood pressure."
    )
    last_bp_diastolic = fields.Integer(
        string="Latest DBP (mmHg)",
        compute="_compute_latest_vitals_snapshot",
        help="Latest measured diastolic blood pressure."
    )
    last_bmi = fields.Float(
        string="Latest BMI",
        compute="_compute_latest_vitals_snapshot",
        digits=(6, 2),
        help="Latest computed BMI."
    )
    last_vitals_summary = fields.Char(
        string="Latest Vitals Summary",
        compute="_compute_latest_vitals_snapshot",
        help="Short text summarizing the latest vitals (for quick glance)."
    )

    # -------------------------------------------------------------------------
    # Company Safety (optional consistency hint)
    # -------------------------------------------------------------------------
    @api.constrains("company_id")
    def _check_company_consistency_with_sessions(self):
        """Ensure patient & sessions company match (defensive; sessions guard too)."""
        Session = self.env["clinic.triage.session"]
        for patient in self:
            if not patient.company_id:
                continue
            # Only check a few to avoid heavy scans (defensive; triage session already validates on its side)
            any_mismatch = Session.search_count([
                ("patient_id", "=", patient.id),
                ("company_id", "!=", patient.company_id.id)
            ], limit=1)
            if any_mismatch:
                raise ValidationError(_("There are triage sessions with a different company than the patient."))

    # -------------------------------------------------------------------------
    # Compute: metrics (counts) using read_group for performance
    # -------------------------------------------------------------------------
    @api.depends("triage_session_ids", "triage_session_ids.state")
    def _compute_triage_metrics(self):
        """Compute counts in batch with the Odoo 19 backend aggregation API."""
        self.triage_session_count = 0
        self.triage_session_open_count = 0

        if not self.ids:
            return

        Session = self.env["clinic.triage.session"]

        # Total count per patient.
        data_total = Session._read_group(
            [("patient_id", "in", self.ids)],
            groupby=["patient_id"],
            aggregates=["__count"],
        )
        total_map = {
            patient.id: count
            for patient, count in data_total
            if patient
        }

        # Open count per patient (not completed/cancelled).
        data_open = Session._read_group(
            [
                ("patient_id", "in", self.ids),
                ("state", "not in", ["completed", "cancelled"]),
            ],
            groupby=["patient_id"],
            aggregates=["__count"],
        )
        open_map = {
            patient.id: count
            for patient, count in data_open
            if patient
        }

        for rec in self:
            rec.triage_session_count = int(total_map.get(rec.id, 0))
            rec.triage_session_open_count = int(open_map.get(rec.id, 0))

    # -------------------------------------------------------------------------
    # Compute: latest session & latest vitals (batch-friendly)
    # -------------------------------------------------------------------------
    @api.depends(
        "triage_session_ids",
        "triage_session_ids.arrival_datetime",
        "triage_session_ids.end_datetime",
        "triage_session_ids.write_date",
        "vitals_ids",
        "vitals_ids.measure_datetime",
        "vitals_ids.write_date",
    )
    def _compute_latest_links(self):
        """Find latest triage session and latest vitals per patient in batch."""
        self.latest_triage_session_id = False
        self.latest_vitals_id = False

        if not self.ids:
            return

        Session = self.env["clinic.triage.session"]
        Vitals = self.env["clinic.vitals.intake"]

        # Latest session per patient by arrival/end/write_date
        latest_session_map = {}
        sessions = Session.search(
            [("patient_id", "in", self.ids)],
            order="arrival_datetime desc, end_datetime desc, write_date desc, id desc",
        )
        for s in sessions:
            pid = s.patient_id.id
            if pid not in latest_session_map:
                latest_session_map[pid] = s

        # Latest vitals per patient by measure/write_date
        latest_vitals_map = {}
        vitals = Vitals.search(
            [("patient_id", "in", self.ids)],
            order="measure_datetime desc, write_date desc, id desc",
        )
        for v in vitals:
            pid = v.patient_id.id
            if pid not in latest_vitals_map:
                latest_vitals_map[pid] = v

        for rec in self:
            rec.latest_triage_session_id = latest_session_map.get(rec.id, False)
            rec.latest_vitals_id = latest_vitals_map.get(rec.id, False)

    # -------------------------------------------------------------------------
    # Compute: latest vitals snapshot & abnormal flag
    # -------------------------------------------------------------------------
    @api.depends(
        "latest_vitals_id",
        "latest_vitals_id.measure_datetime",
        "latest_vitals_id.temperature_c",
        "latest_vitals_id.heart_rate_bpm",
        "latest_vitals_id.respiratory_rate_bpm",
        "latest_vitals_id.spo2_percent",
        "latest_vitals_id.sbp_mm_hg",
        "latest_vitals_id.dbp_mm_hg",
        "latest_vitals_id.bmi",
        "latest_vitals_id.is_abnormal",
    )
    def _compute_latest_vitals_snapshot(self):
        for rec in self:
            v = rec.latest_vitals_id
            if not v:
                rec.last_measure_on = False
                rec.last_temp_c = 0.0
                rec.last_hr_bpm = 0
                rec.last_rr_bpm = 0
                rec.last_spo2_pct = 0.0
                rec.last_bp_systolic = 0
                rec.last_bp_diastolic = 0
                rec.last_bmi = 0.0
                rec.has_recent_abnormal_vitals = False
                rec.last_vitals_summary = False
                continue

            rec.last_measure_on = v.measure_datetime
            rec.last_temp_c = v.temperature_c or 0.0
            rec.last_hr_bpm = v.heart_rate_bpm or 0
            rec.last_rr_bpm = v.respiratory_rate_bpm or 0
            rec.last_spo2_pct = v.spo2_percent or 0.0
            rec.last_bp_systolic = v.sbp_mm_hg or 0
            rec.last_bp_diastolic = v.dbp_mm_hg or 0
            rec.last_bmi = v.bmi or 0.0
            rec.has_recent_abnormal_vitals = bool(v.is_abnormal)

            # Build short, human-friendly summary
            parts = []
            if v.temperature_c:
                parts.append(_("Temp %s°C") % v.temperature_c)
            if v.heart_rate_bpm:
                parts.append(_("HR %sbpm") % v.heart_rate_bpm)
            if v.respiratory_rate_bpm:
                parts.append(_("RR %s") % v.respiratory_rate_bpm)
            if v.sbp_mm_hg and v.dbp_mm_hg:
                parts.append(_("BP %s/%s") % (v.sbp_mm_hg, v.dbp_mm_hg))
            if v.spo2_percent:
                parts.append(_("SpO₂ %s%%") % v.spo2_percent)
            if v.bmi:
                parts.append(_("BMI %s") % v.bmi)
            rec.last_vitals_summary = " | ".join(parts) if parts else False

    # -------------------------------------------------------------------------
    # Actions (for smart buttons / patient form)
    # -------------------------------------------------------------------------
    def action_view_triage_sessions(self):
        """Open all triage sessions of this patient."""
        self.ensure_one()
        action = self.env.ref("clinic_triage_vitals.action_clinic_triage_session").read()[0]
        action["domain"] = [("patient_id", "=", self.id)]
        action["context"] = dict(self.env.context or {}, default_patient_id=self.id)
        return action

    def action_view_latest_vitals(self):
        """Open the latest vitals record for this patient, or list if none."""
        self.ensure_one()
        if self.latest_vitals_id:
            # Open specific record in form view
            return {
                "type": "ir.actions.act_window",
                "res_model": "clinic.vitals.intake",
                "res_id": self.latest_vitals_id.id,
                "view_mode": "form",
                "target": "current",
            }
        # Fallback to list
        action = self.env.ref("clinic_triage_vitals.action_clinic_vitals_intake").read()[0]
        action["domain"] = [("patient_id", "=", self.id)]
        action["context"] = dict(self.env.context or {}, default_patient_id=self.id)
        return action

    def action_new_triage_session(self):
        """Create a new triage session pre-filled for this patient and open it."""
        self.ensure_one()
        # Optional access guard: user must be able to create triage sessions
        if not self.env["clinic.triage.session"].browse().has_access("create"):
            raise AccessError(_("You do not have the rights to create triage sessions."))

        vals = {
            "patient_id": self.id,
            "company_id": self.company_id.id if self.company_id else self.env.company.id,
        }
        session = self.env["clinic.triage.session"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "clinic.triage.session",
            "res_id": session.id,
            "view_mode": "form",
            "target": "current",
            "context": dict(self.env.context or {}, default_patient_id=self.id),
        }
