
# -*- coding: utf-8 -*-
# File: models/encounter_link.py
#
# ClinicOne - Triage & Vitals Intake
# Extension: clinic.encounter (links to triage sessions & vitals)
#
# Purpose:
# - Provide quick access from Encounter to all Triage Sessions and Vitals Intake.
# - Expose current (latest) triage snapshot and vitals snapshot for the encounter.
# - Provide counters & simple KPI (avg wait, avg duration, SLA breach count).
# - Offer helper actions (view sessions, view latest vitals, start new triage).
#
# All UI strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicEncounter(models.Model):
    _inherit = "clinic.encounter"

    # -------------------------------------------------------------------------
    # Links to Triage & Vitals
    # -------------------------------------------------------------------------
    triage_session_ids = fields.One2many(
        "clinic.triage.session",
        "encounter_id",
        string="Triage Sessions",
        help="All triage sessions associated with this encounter."
    )
    triage_session_count = fields.Integer(
        string="Triage Sessions Count",
        compute="_compute_triage_metrics",
        help="Total number of triage sessions for this encounter."
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
        help="The most recent triage session linked to this encounter."
    )
    latest_vitals_id = fields.Many2one(
        "clinic.vitals.intake",
        string="Latest Vitals",
        compute="_compute_latest_links",
        help="The most recent vital sign measurement in sessions under this encounter."
    )

    # -------------------------------------------------------------------------
    # Current Triage Snapshot (derived from latest session)
    # -------------------------------------------------------------------------
    current_triage_level_id = fields.Many2one(
        "clinic.triage.level",
        string="Current Triage Level",
        related="latest_triage_session_id.triage_level_id",
        store=True,
        readonly=True,
        help="Triage level of the latest triage session."
    )
    current_sla_target_datetime = fields.Datetime(
        string="Current SLA Target Time",
        related="latest_triage_session_id.sla_target_datetime",
        store=True,
        readonly=True,
        help="SLA target (arrival + SLA minutes) of the latest triage session."
    )
    current_sla_breached = fields.Boolean(
        string="Current SLA Breached",
        related="latest_triage_session_id.sla_breached",
        store=True,
        readonly=True,
        help="True if the latest triage session started after its SLA target."
    )
    current_queue_stage_id = fields.Many2one(
        "clinic.queue.stage",
        string="Current Queue Stage",
        related="latest_triage_session_id.queue_stage_id",
        store=True,
        readonly=True,
        help="Queue stage referenced by the latest triage session."
    )
    current_recommended_room_type_id = fields.Many2one(
        "clinic.room.type",
        string="Recommended Room Type",
        related="latest_triage_session_id.recommended_room_type_id",
        store=True,
        readonly=True,
        help="Recommended room type suggested by the latest triage session."
    )

    # -------------------------------------------------------------------------
    # Current Vitals Snapshot (derived from latest_vitals_id)
    # -------------------------------------------------------------------------
    last_measure_on = fields.Datetime(
        string="Latest Measured On",
        compute="_compute_latest_vitals_snapshot",
        help="Timestamp of the most recent vitals measurement in this encounter."
    )
    last_temp_c = fields.Float(
        string="Latest Temp (°C)",
        compute="_compute_latest_vitals_snapshot",
        digits=(6, 2)
    )
    last_hr_bpm = fields.Integer(
        string="Latest HR (bpm)",
        compute="_compute_latest_vitals_snapshot"
    )
    last_rr_bpm = fields.Integer(
        string="Latest RR (breaths/min)",
        compute="_compute_latest_vitals_snapshot"
    )
    last_spo2_pct = fields.Float(
        string="Latest SpO₂ (%)",
        compute="_compute_latest_vitals_snapshot",
        digits=(6, 2)
    )
    last_bp_systolic = fields.Integer(
        string="Latest SBP (mmHg)",
        compute="_compute_latest_vitals_snapshot"
    )
    last_bp_diastolic = fields.Integer(
        string="Latest DBP (mmHg)",
        compute="_compute_latest_vitals_snapshot"
    )
    last_bmi = fields.Float(
        string="Latest BMI",
        compute="_compute_latest_vitals_snapshot",
        digits=(6, 2)
    )
    has_recent_abnormal_vitals = fields.Boolean(
        string="Latest Vitals Abnormal",
        compute="_compute_latest_vitals_snapshot",
        help="True when the latest vitals are marked abnormal."
    )
    last_vitals_summary = fields.Char(
        string="Latest Vitals Summary",
        compute="_compute_latest_vitals_snapshot",
        help="Short text summarizing the latest vitals for quick glance."
    )

    # -------------------------------------------------------------------------
    # KPI (aggregate across sessions in this encounter)
    # -------------------------------------------------------------------------
    avg_wait_time_minutes = fields.Float(
        string="Avg Waiting Time (min)",
        compute="_compute_kpi",
        digits=(6, 2),
        help="Average minutes from arrival to triage start across sessions."
    )
    avg_triage_duration_minutes = fields.Float(
        string="Avg Triage Duration (min)",
        compute="_compute_kpi",
        digits=(6, 2),
        help="Average minutes from triage start to end across sessions."
    )
    sla_breached_count = fields.Integer(
        string="SLA Breached Sessions",
        compute="_compute_kpi",
        help="Number of sessions where SLA was breached."
    )

    # -------------------------------------------------------------------------
    # Consistency Guards
    # -------------------------------------------------------------------------
    @api.constrains("company_id")
    def _check_company_consistency_with_sessions(self):
        """Defensive guard: encounter & sessions must share the same company."""
        Session = self.env["clinic.triage.session"]
        for enc in self:
            if not enc.company_id:
                continue
            any_mismatch = Session.search_count([
                ("encounter_id", "=", enc.id),
                ("company_id", "!=", enc.company_id.id),
            ], limit=1)
            if any_mismatch:
                raise ValidationError(_("There are triage sessions with a different company than the encounter."))

    @api.constrains("patient_id")
    def _check_patient_consistency_with_sessions(self):
        """Defensive guard: encounter & sessions must refer to the same patient."""
        Session = self.env["clinic.triage.session"]
        for enc in self:
            if not enc.patient_id:
                continue
            mismatch = Session.search_count([
                ("encounter_id", "=", enc.id),
                ("patient_id", "!=", enc.patient_id.id),
            ], limit=1)
            if mismatch:
                raise ValidationError(_("There are triage sessions with a different patient than the encounter."))

    # -------------------------------------------------------------------------
    # Compute: metrics (counts) using read_group
    # -------------------------------------------------------------------------
    def _compute_triage_metrics(self):
        self.triage_session_count = 0
        self.triage_session_open_count = 0

        if not self.ids:
            return

        Session = self.env["clinic.triage.session"]

        # Total count per encounter (Odoo 19 backend aggregation API).
        data_total = Session._read_group(
            [("encounter_id", "in", self.ids)],
            groupby=["encounter_id"],
            aggregates=["__count"],
        )
        total_map = {
            encounter.id: count
            for encounter, count in data_total
            if encounter
        }

        # Open sessions (not completed/cancelled).
        data_open = Session._read_group(
            [
                ("encounter_id", "in", self.ids),
                ("state", "not in", ["completed", "cancelled"]),
            ],
            groupby=["encounter_id"],
            aggregates=["__count"],
        )
        open_map = {
            encounter.id: count
            for encounter, count in data_open
            if encounter
        }

        for rec in self:
            rec.triage_session_count = int(total_map.get(rec.id, 0))
            rec.triage_session_open_count = int(open_map.get(rec.id, 0))

    # -------------------------------------------------------------------------
    # Compute: latest session & latest vitals
    # -------------------------------------------------------------------------
    def _compute_latest_links(self):
        self.latest_triage_session_id = False
        self.latest_vitals_id = False

        if not self.ids:
            return

        Session = self.env["clinic.triage.session"]
        Vitals = self.env["clinic.vitals.intake"]

        # Latest triage session per encounter (arrival/end/write_date)
        latest_session_map = {}
        sessions = Session.search(
            [("encounter_id", "in", self.ids)],
            order="arrival_datetime desc, end_datetime desc, write_date desc, id desc",
            limit=len(self.ids) * 3,
        )
        for s in sessions:
            eid = s.encounter_id.id
            if eid not in latest_session_map:
                latest_session_map[eid] = s

        # Latest vitals per encounter (measure/write_date)
        latest_vitals_map = {}
        vitals = Vitals.search(
            [("triage_session_id.encounter_id", "in", self.ids)],
            order="measure_datetime desc, write_date desc, id desc",
            limit=len(self.ids) * 3,
        )
        for v in vitals:
            eid = v.triage_session_id.encounter_id.id if v.triage_session_id and v.triage_session_id.encounter_id else False
            if eid and eid not in latest_vitals_map:
                latest_vitals_map[eid] = v

        for rec in self:
            rec.latest_triage_session_id = latest_session_map.get(rec.id, False)
            rec.latest_vitals_id = latest_vitals_map.get(rec.id, False)

    # -------------------------------------------------------------------------
    # Compute: current vitals snapshot
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
    # Compute: KPI (avg wait/duration, SLA breach count)
    # -------------------------------------------------------------------------
    def _compute_kpi(self):
        self.avg_wait_time_minutes = 0.0
        self.avg_triage_duration_minutes = 0.0
        self.sla_breached_count = 0

        if not self.ids:
            return

        Session = self.env["clinic.triage.session"]

        # Average wait/duration via the Odoo 19 backend aggregation API.
        data = Session._read_group(
            [("encounter_id", "in", self.ids)],
            groupby=["encounter_id"],
            aggregates=["wait_time_minutes:sum", "triage_duration_minutes:sum", "__count"],
        )
        aggregate_map = {
            encounter.id: (wait_sum or 0.0, duration_sum or 0.0, count or 0)
            for encounter, wait_sum, duration_sum, count in data
            if encounter
        }

        # SLA breach count.
        breach_data = Session._read_group(
            [("encounter_id", "in", self.ids), ("sla_breached", "=", True)],
            groupby=["encounter_id"],
            aggregates=["__count"],
        )
        breach_map = {
            encounter.id: count
            for encounter, count in breach_data
            if encounter
        }

        for rec in self:
            wait_sum, dur_sum, count = aggregate_map.get(rec.id, (0.0, 0.0, 0))
            cnt = float(count or 0)
            rec.avg_wait_time_minutes = round(float(wait_sum) / cnt, 2) if cnt else 0.0
            rec.avg_triage_duration_minutes = round(float(dur_sum) / cnt, 2) if cnt else 0.0
            rec.sla_breached_count = int(breach_map.get(rec.id, 0) or 0)

    # -------------------------------------------------------------------------
    # Actions (for smart buttons / encounter form)
    # -------------------------------------------------------------------------
    def action_view_triage_sessions(self):
        """Open all triage sessions linked to this encounter."""
        self.ensure_one()
        action = self.env.ref("clinic_triage_vitals.action_clinic_triage_session").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        ctx = dict(self.env.context or {})
        ctx.update(default_encounter_id=self.id, default_patient_id=self.patient_id.id if self.patient_id else False)
        action["context"] = ctx
        return action

    def action_view_latest_vitals(self):
        """Open the latest vitals record under this encounter, or list if none."""
        self.ensure_one()
        if self.latest_vitals_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "clinic.vitals.intake",
                "res_id": self.latest_vitals_id.id,
                "view_mode": "form",
                "target": "current",
            }
        action = self.env.ref("clinic_triage_vitals.action_clinic_vitals_intake").read()[0]
        action["domain"] = [("triage_session_id.encounter_id", "=", self.id)]
        ctx = dict(self.env.context or {})
        if self.patient_id:
            ctx.setdefault("default_patient_id", self.patient_id.id)
        action["context"] = ctx
        return action

    def action_new_triage_session(self):
        """Create a new triage session pre-filled for this encounter and open it."""
        self.ensure_one()
        if not self.env["clinic.triage.session"].browse().has_access("create"):
            raise AccessError(_("You do not have the rights to create triage sessions."))

        vals = {
            "encounter_id": self.id,
            "patient_id": self.patient_id.id if self.patient_id else False,
            "company_id": self.company_id.id if self.company_id else self.env.company.id,
        }
        # Guard: patient should exist; triage requires patient
        if not vals.get("patient_id"):
            raise ValidationError(_("Cannot create a triage session without a patient on the encounter."))

        session = self.env["clinic.triage.session"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "clinic.triage.session",
            "res_id": session.id,
            "view_mode": "form",
            "target": "current",
            "context": dict(self.env.context or {}, default_encounter_id=self.id, default_patient_id=vals["patient_id"]),
        }
