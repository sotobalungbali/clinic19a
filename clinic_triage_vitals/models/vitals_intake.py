
# -*- coding: utf-8 -*-
# File: models/vitals_intake.py
#
# ClinicOne - Triage & Vitals Intake
# Model: clinic.vitals.intake
#
# Integrations:
# - Parent session: clinic.triage.session (o2m backref: vitals_ids)
# - Patient/Encounter: related to session fields
# - Queue/Room: optional device/room metadata (clinic.room, clinic.device)
# - Billing/Reports: abnormal flags & KPI fields ready for search/reporting
#
# All UI strings are in English per product requirement.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicVitalsIntake(models.Model):
    _name = "clinic.vitals.intake"
    _description = "Clinic Vitals Intake"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "measure_datetime desc, id desc"

    # -------------------------------------------------------------------------
    # Identity & Ownership
    # -------------------------------------------------------------------------
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, this record will be hidden without being deleted."
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Owning company for this record."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # Links
    # -------------------------------------------------------------------------
    triage_session_id = fields.Many2one(
        "clinic.triage.session",
        string="Triage Session",
        required=True,
        index=True,
        ondelete="cascade",
        help="Triage session to which these vitals belong."
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="triage_session_id.patient_id",
        store=True,
        readonly=True
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     related="triage_session_id.encounter_id",
    #     store=True,
    #     readonly=True
    # )
    triage_level_id = fields.Many2one(
        "clinic.triage.level",
        string="Triage Level",
        related="triage_session_id.triage_level_id",
        store=True,
        readonly=True,
        help="Triage level at the time of measurement (read from the session)."
    )

    # -------------------------------------------------------------------------
    # Measurement Meta
    # -------------------------------------------------------------------------
    measure_datetime = fields.Datetime(
        string="Measured On",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help="Date and time when these vital signs were measured."
    )
    measured_by_id = fields.Many2one(
        "res.users",
        string="Measured By",
        default=lambda self: self.env.user,
        tracking=True,
        help="User who recorded these vital signs."
    )
    source = fields.Selection(
        selection=[
            ("manual", "Manual Entry"),
            ("device", "Connected Device"),
            ("import", "Data Import"),
        ],
        string="Source",
        default="manual",
        help="How these vitals were captured."
    )
    position = fields.Selection(
        selection=[
            ("sitting", "Sitting"),
            ("supine", "Supine"),
            ("standing", "Standing"),
        ],
        string="Patient Position",
        help="Patient position during measurement."
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        help="Room where the measurement was taken."
    )
    room_device_id = fields.Many2one(
        "clinic.device",
        string="Device",
        help="Device used for the measurement (if available)."
    )
    device_serial = fields.Char(
        string="Device Serial",
        help="Optional device serial number for traceability."
    )

    # -------------------------------------------------------------------------
    # Temperature
    # -------------------------------------------------------------------------
    temperature_c = fields.Float(
        string="Temperature (°C)",
        digits=(6, 2),
        help="Body temperature in Celsius."
    )
    temperature_f = fields.Float(
        string="Temperature (°F)",
        compute="_compute_temperature_f",
        inverse="_inverse_temperature_f",
        store=True,
        digits=(6, 2),
        help="Body temperature in Fahrenheit (auto-converted from/to Celsius)."
    )
    temperature_method = fields.Selection(
        selection=[
            ("oral", "Oral"),
            ("tympanic", "Tympanic"),
            ("axillary", "Axillary"),
            ("temporal", "Temporal"),
            ("rectal", "Rectal"),
            ("unspecified", "Unspecified"),
        ],
        string="Temperature Method",
        default="unspecified",
        help="Measurement site/method for temperature."
    )

    # -------------------------------------------------------------------------
    # Cardiopulmonary
    # -------------------------------------------------------------------------
    heart_rate_bpm = fields.Integer(
        string="Heart Rate (bpm)",
        help="Heart rate in beats per minute."
    )
    respiratory_rate_bpm = fields.Integer(
        string="Respiratory Rate (breaths/min)",
        help="Respiratory rate in breaths per minute."
    )
    spo2_percent = fields.Float(
        string="SpO₂ (%)",
        digits=(6, 2),
        help="Oxygen saturation percentage."
    )
    on_oxygen = fields.Boolean(
        string="On Supplemental Oxygen",
        help="Enable if the patient was on supplemental oxygen during SpO₂ measurement."
    )
    o2_flow_l_min = fields.Float(
        string="O₂ Flow (L/min)",
        digits=(6, 2),
        help="Oxygen flow rate if supplemental oxygen was used."
    )

    # -------------------------------------------------------------------------
    # Blood Pressure
    # -------------------------------------------------------------------------
    sbp_mm_hg = fields.Integer(
        string="Systolic BP (mmHg)",
        help="Systolic blood pressure in mmHg."
    )
    dbp_mm_hg = fields.Integer(
        string="Diastolic BP (mmHg)",
        help="Diastolic blood pressure in mmHg."
    )
    map_mm_hg = fields.Float(
        string="MAP (mmHg)",
        compute="_compute_bp_derived",
        store=True,
        digits=(6, 2),
        help="Mean Arterial Pressure (estimated): DBP + 1/3*(SBP - DBP)."
    )
    pulse_pressure_mm_hg = fields.Integer(
        string="Pulse Pressure (mmHg)",
        compute="_compute_bp_derived",
        store=True,
        help="Pulse pressure (SBP - DBP)."
    )
    bp_arm = fields.Selection(
        selection=[("left", "Left"), ("right", "Right")],
        string="BP Arm",
        help="Arm used for blood pressure measurement."
    )
    bp_method = fields.Selection(
        selection=[("auscultatory", "Auscultatory"), ("oscillometric", "Oscillometric"), ("unspecified", "Unspecified")],
        string="BP Method",
        default="unspecified",
        help="Measurement method for blood pressure."
    )
    bp_position = fields.Selection(
        selection=[("sitting", "Sitting"), ("supine", "Supine"), ("standing", "Standing")],
        string="BP Position",
        help="Patient position during blood pressure measurement."
    )

    # -------------------------------------------------------------------------
    # Anthropometrics
    # -------------------------------------------------------------------------
    weight_kg = fields.Float(
        string="Weight (kg)",
        digits=(6, 2),
        help="Body weight in kilograms."
    )
    weight_lb = fields.Float(
        string="Weight (lb)",
        compute="_compute_weight_lb",
        inverse="_inverse_weight_lb",
        store=True,
        digits=(6, 2),
        help="Body weight in pounds (auto-converted from/to kilograms)."
    )
    height_cm = fields.Float(
        string="Height (cm)",
        digits=(6, 2),
        help="Body height in centimeters."
    )
    height_in = fields.Float(
        string="Height (in)",
        compute="_compute_height_in",
        inverse="_inverse_height_in",
        store=True,
        digits=(6, 2),
        help="Body height in inches (auto-converted from/to centimeters)."
    )
    bmi = fields.Float(
        string="BMI",
        compute="_compute_bmi",
        store=True,
        digits=(6, 2),
        help="Body Mass Index computed from weight and height."
    )
    bmi_category = fields.Selection(
        selection=[
            ("underweight", "Underweight"),
            ("normal", "Normal"),
            ("overweight", "Overweight"),
            ("obese", "Obese"),
        ],
        string="BMI Category",
        compute="_compute_bmi_category",
        store=True,
        help="BMI category based on standard adult ranges."
    )
    bsa_m2 = fields.Float(
        string="Body Surface Area (m²)",
        compute="_compute_bsa",
        store=True,
        digits=(6, 3),
        help="Body surface area (Mosteller formula)."
    )

    # -------------------------------------------------------------------------
    # Neurologic & Pain
    # -------------------------------------------------------------------------
    gcs_e = fields.Integer(
        string="GCS (E)",
        help="Glasgow Coma Scale - Eye response (1–4)."
    )
    gcs_v = fields.Integer(
        string="GCS (V)",
        help="Glasgow Coma Scale - Verbal response (1–5)."
    )
    gcs_m = fields.Integer(
        string="GCS (M)",
        help="Glasgow Coma Scale - Motor response (1–6)."
    )
    gcs = fields.Integer(
        string="GCS Total",
        compute="_compute_gcs_total",
        store=True,
        help="Total GCS score (3–15)."
    )
    pain_score = fields.Integer(
        string="Pain Score (0–10)",
        help="Numeric pain rating scale, 0 (no pain) to 10 (worst pain)."
    )

    # -------------------------------------------------------------------------
    # Derived Flags (abnormality & helpers)
    # -------------------------------------------------------------------------
    is_fever = fields.Boolean(
        string="Fever",
        compute="_compute_abnormalities",
        store=True,
        help="Temperature indicates fever (≥ 38.0°C)."
    )
    is_hypothermia = fields.Boolean(
        string="Hypothermia",
        compute="_compute_abnormalities",
        store=True,
        help="Temperature indicates hypothermia (< 35.0°C)."
    )
    is_tachycardia = fields.Boolean(
        string="Tachycardia",
        compute="_compute_abnormalities",
        store=True,
        help="Heart rate above normal adult threshold."
    )
    is_bradycardia = fields.Boolean(
        string="Bradycardia",
        compute="_compute_abnormalities",
        store=True,
        help="Heart rate below normal adult threshold."
    )
    is_tachypnea = fields.Boolean(
        string="Tachypnea",
        compute="_compute_abnormalities",
        store=True,
        help="Respiratory rate above normal adult threshold."
    )
    is_bradypnea = fields.Boolean(
        string="Bradypnea",
        compute="_compute_abnormalities",
        store=True,
        help="Respiratory rate below normal adult threshold."
    )
    is_hypoxia = fields.Boolean(
        string="Hypoxia",
        compute="_compute_abnormalities",
        store=True,
        help="SpO₂ below normal adult threshold."
    )
    is_hypertensive = fields.Boolean(
        string="Hypertension (BP)",
        compute="_compute_abnormalities",
        store=True,
        help="Blood pressure above normal adult threshold."
    )
    is_hypotensive = fields.Boolean(
        string="Hypotension (BP)",
        compute="_compute_abnormalities",
        store=True,
        help="Blood pressure below normal adult threshold."
    )
    is_abnormal = fields.Boolean(
        string="Abnormal",
        compute="_compute_abnormalities",
        store=True,
        help="True if any vital sign is outside the acceptable range."
    )
    abnormal_fields = fields.Char(
        string="Abnormal Fields",
        compute="_compute_abnormalities",
        store=True,
        help="Comma-separated list of fields that are abnormal."
    )

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    notes = fields.Text(
        string="Notes",
        help="Additional notes about the measurement."
    )
    internal_notes = fields.Html(
        string="Internal Notes",
        help="Internal notes for clinical staff; not intended for patient-facing documents."
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------
    _pain_score_bounds = models.Constraint(
        "CHECK(pain_score IS NULL OR (pain_score >= 0 AND pain_score <= 10))",
        "Pain score must be between 0 and 10.",
    )
    _gcs_e_bounds = models.Constraint(
        "CHECK(gcs_e IS NULL OR (gcs_e >= 1 AND gcs_e <= 4))",
        "GCS Eye (E) must be between 1 and 4.",
    )
    _gcs_v_bounds = models.Constraint(
        "CHECK(gcs_v IS NULL OR (gcs_v >= 1 AND gcs_v <= 5))",
        "GCS Verbal (V) must be between 1 and 5.",
    )
    _gcs_m_bounds = models.Constraint(
        "CHECK(gcs_m IS NULL OR (gcs_m >= 1 AND gcs_m <= 6))",
        "GCS Motor (M) must be between 1 and 6.",
    )

    # -------------------------------------------------------------------------
    # Create/Write guards
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
        records = super().create(vals_list)
        for rec in records:
            rec.message_post(
                body=_("Vitals recorded on <b>%s</b>.") % (fields.Datetime.to_string(rec.measure_datetime),),
                subtype_xmlid="mail.mt_note"
            )
        return records

    def write(self, vals):
        res = super().write(vals)
        tracked = {"temperature_c", "heart_rate_bpm", "respiratory_rate_bpm", "spo2_percent", "sbp_mm_hg", "dbp_mm_hg"}
        if tracked.intersection(vals.keys()):
            for rec in self:
                parts = []
                if "temperature_c" in vals:
                    parts.append(_("Temperature: %s °C") % (rec.temperature_c or "-"))
                if "heart_rate_bpm" in vals:
                    parts.append(_("Heart Rate: %s bpm") % (rec.heart_rate_bpm or "-"))
                if "respiratory_rate_bpm" in vals:
                    parts.append(_("Respiratory Rate: %s breaths/min") % (rec.respiratory_rate_bpm or "-"))
                if "spo2_percent" in vals:
                    parts.append(_("SpO₂: %s %%") % (rec.spo2_percent or "-"))
                if "sbp_mm_hg" in vals or "dbp_mm_hg" in vals:
                    parts.append(_("BP: %s/%s mmHg") % (rec.sbp_mm_hg or "-", rec.dbp_mm_hg or "-"))
                if parts:
                    rec.message_post(body="<br/>".join(parts), subtype_xmlid="mail.mt_note")
        return res

    # -------------------------------------------------------------------------
    # Computes: unit conversions & derived metrics
    # -------------------------------------------------------------------------
    @api.depends("temperature_c")
    def _compute_temperature_f(self):
        for rec in self:
            rec.temperature_f = rec.temperature_c * 9.0 / 5.0 + 32.0 if rec.temperature_c not in (None, 0.0) else 0.0

    def _inverse_temperature_f(self):
        for rec in self:
            if rec.temperature_f not in (None, 0.0):
                rec.temperature_c = (rec.temperature_f - 32.0) * 5.0 / 9.0
            else:
                rec.temperature_c = 0.0

    @api.depends("weight_kg")
    def _compute_weight_lb(self):
        for rec in self:
            rec.weight_lb = rec.weight_kg * 2.20462262 if rec.weight_kg not in (None, 0.0) else 0.0

    def _inverse_weight_lb(self):
        for rec in self:
            if rec.weight_lb not in (None, 0.0):
                rec.weight_kg = rec.weight_lb / 2.20462262
            else:
                rec.weight_kg = 0.0

    @api.depends("height_cm")
    def _compute_height_in(self):
        for rec in self:
            rec.height_in = rec.height_cm / 2.54 if rec.height_cm not in (None, 0.0) else 0.0

    def _inverse_height_in(self):
        for rec in self:
            if rec.height_in not in (None, 0.0):
                rec.height_cm = rec.height_in * 2.54
            else:
                rec.height_cm = 0.0

    @api.depends("weight_kg", "height_cm")
    def _compute_bmi(self):
        for rec in self:
            bmi = 0.0
            if rec.weight_kg and rec.height_cm and rec.height_cm > 0:
                h_m = rec.height_cm / 100.0
                bmi = rec.weight_kg / (h_m * h_m) if h_m > 0 else 0.0
            rec.bmi = round(bmi, 2) if bmi else 0.0

    @api.depends("bmi")
    def _compute_bmi_category(self):
        for rec in self:
            cat = False
            if rec.bmi:
                if rec.bmi < 18.5:
                    cat = "underweight"
                elif rec.bmi < 25:
                    cat = "normal"
                elif rec.bmi < 30:
                    cat = "overweight"
                else:
                    cat = "obese"
            rec.bmi_category = cat

    @api.depends("weight_kg", "height_cm")
    def _compute_bsa(self):
        # Mosteller formula: BSA (m²) = sqrt( (height(cm) * weight(kg)) / 3600 )
        for rec in self:
            bsa = 0.0
            if rec.weight_kg and rec.height_cm and rec.weight_kg > 0 and rec.height_cm > 0:
                bsa = ((rec.height_cm * rec.weight_kg) / 3600.0) ** 0.5
            rec.bsa_m2 = round(bsa, 3) if bsa else 0.0

    @api.depends("sbp_mm_hg", "dbp_mm_hg")
    def _compute_bp_derived(self):
        for rec in self:
            pulse = None
            mean_ap = None
            if rec.sbp_mm_hg is not None and rec.dbp_mm_hg is not None:
                try:
                    pulse = int(rec.sbp_mm_hg) - int(rec.dbp_mm_hg)
                    mean_ap = float(rec.dbp_mm_hg) + (pulse / 3.0)
                except Exception:
                    pulse = None
                    mean_ap = None
            rec.pulse_pressure_mm_hg = pulse if pulse is not None else 0
            rec.map_mm_hg = round(mean_ap, 2) if mean_ap is not None else 0.0

    @api.depends("gcs_e", "gcs_v", "gcs_m")
    def _compute_gcs_total(self):
        for rec in self:
            e = rec.gcs_e or 0
            v = rec.gcs_v or 0
            m = rec.gcs_m or 0
            total = e + v + m if (e and v and m) else 0
            rec.gcs = total

    # -------------------------------------------------------------------------
    # Abnormality rules
    # -------------------------------------------------------------------------
    @api.depends(
        "temperature_c",
        "heart_rate_bpm",
        "respiratory_rate_bpm",
        "spo2_percent",
        "sbp_mm_hg",
        "dbp_mm_hg",
        "gcs",
        "triage_level_id.sla_minutes",  # dummy dep to recompute when level changes
        "triage_level_id.temp_min_c", "triage_level_id.temp_max_c",
        "triage_level_id.hr_min_bpm", "triage_level_id.hr_max_bpm",
        "triage_level_id.rr_min_bpm", "triage_level_id.rr_max_bpm",
        "triage_level_id.spo2_min_percent",
        "triage_level_id.sbp_min_mm_hg", "triage_level_id.sbp_max_mm_hg",
        "triage_level_id.dbp_min_mm_hg", "triage_level_id.dbp_max_mm_hg",
        "triage_level_id.gcs_min", "triage_level_id.gcs_max",
    )
    def _compute_abnormalities(self):
        """Compute abnormal flags using triage level thresholds if available,
        otherwise fall back to generic adult thresholds."""
        for rec in self:
            abnormal = set()

            # Convenience getters (prefer level thresholds if defined)
            lvl = rec.triage_level_id

            def _minval(attr, default):
                v = getattr(lvl, attr, None) if lvl else None
                return v if v not in (None, 0) else default

            def _maxval(attr, default):
                v = getattr(lvl, attr, None) if lvl else None
                return v if v not in (None, 0) else default

            # Generic adult thresholds (fallbacks)
            TEMP_LOW = _minval("temp_min_c", 35.0)
            TEMP_HIGH = _maxval("temp_max_c", 38.5)
            HR_LOW = _minval("hr_min_bpm", 50)
            HR_HIGH = _maxval("hr_max_bpm", 110)
            RR_LOW = _minval("rr_min_bpm", 10)
            RR_HIGH = _maxval("rr_max_bpm", 24)
            SPO2_MIN = _minval("spo2_min_percent", 94.0)
            SBP_LOW = _minval("sbp_min_mm_hg", 90)
            SBP_HIGH = _maxval("sbp_max_mm_hg", 180)
            DBP_LOW = _minval("dbp_min_mm_hg", 50)
            DBP_HIGH = _maxval("dbp_max_mm_hg", 120)
            GCS_MIN = _minval("gcs_min", 3)
            GCS_MAX = _maxval("gcs_max", 15)

            # Temperature-based flags
            is_fever = bool(rec.temperature_c and rec.temperature_c >= 38.0)
            is_hypothermia = bool(rec.temperature_c and rec.temperature_c < 35.0)
            if rec.temperature_c not in (None, 0.0):
                if rec.temperature_c < TEMP_LOW or rec.temperature_c > TEMP_HIGH:
                    abnormal.add("temperature_c")

            # HR
            is_tachy = bool(rec.heart_rate_bpm and rec.heart_rate_bpm > HR_HIGH)
            is_brady = bool(rec.heart_rate_bpm and rec.heart_rate_bpm < HR_LOW)
            if rec.heart_rate_bpm is not None:
                if rec.heart_rate_bpm < HR_LOW or rec.heart_rate_bpm > HR_HIGH:
                    abnormal.add("heart_rate_bpm")

            # RR
            is_tachyp = bool(rec.respiratory_rate_bpm and rec.respiratory_rate_bpm > RR_HIGH)
            is_bradyp = bool(rec.respiratory_rate_bpm and rec.respiratory_rate_bpm < RR_LOW)
            if rec.respiratory_rate_bpm is not None:
                if rec.respiratory_rate_bpm < RR_LOW or rec.respiratory_rate_bpm > RR_HIGH:
                    abnormal.add("respiratory_rate_bpm")

            # SpO2
            is_hypoxia = bool(rec.spo2_percent and rec.spo2_percent < SPO2_MIN)
            if rec.spo2_percent not in (None, 0.0):
                if rec.spo2_percent < SPO2_MIN:
                    abnormal.add("spo2_percent")

            # BP
            is_hyper = bool((rec.sbp_mm_hg and rec.sbp_mm_hg > SBP_HIGH) or (rec.dbp_mm_hg and rec.dbp_mm_hg > DBP_HIGH))
            is_hypo = bool((rec.sbp_mm_hg and rec.sbp_mm_hg < SBP_LOW) or (rec.dbp_mm_hg and rec.dbp_mm_hg < DBP_LOW))
            if rec.sbp_mm_hg is not None and (rec.sbp_mm_hg < SBP_LOW or rec.sbp_mm_hg > SBP_HIGH):
                abnormal.add("sbp_mm_hg")
            if rec.dbp_mm_hg is not None and (rec.dbp_mm_hg < DBP_LOW or rec.dbp_mm_hg > DBP_HIGH):
                abnormal.add("dbp_mm_hg")

            # GCS
            if rec.gcs:
                if rec.gcs < GCS_MIN or rec.gcs > GCS_MAX:
                    abnormal.add("gcs")
                # Conventionally, GCS < 15 indicates some impairment
                if rec.gcs < 15:
                    abnormal.add("gcs")

            # Persist computed booleans
            rec.is_fever = is_fever
            rec.is_hypothermia = is_hypothermia
            rec.is_tachycardia = is_tachy
            rec.is_bradycardia = is_brady
            rec.is_tachypnea = is_tachyp
            rec.is_bradypnea = is_bradyp
            rec.is_hypoxia = is_hypoxia
            rec.is_hypertensive = is_hyper
            rec.is_hypotensive = is_hypo
            rec.is_abnormal = bool(abnormal)
            rec.abnormal_fields = ", ".join(sorted(abnormal)) if abnormal else ""

    # -------------------------------------------------------------------------
    # Python Constraints
    # -------------------------------------------------------------------------
    @api.constrains(
        "temperature_c", "temperature_f",
        "heart_rate_bpm", "respiratory_rate_bpm",
        "spo2_percent", "o2_flow_l_min",
        "sbp_mm_hg", "dbp_mm_hg",
        "weight_kg", "height_cm",
        "gcs_e", "gcs_v", "gcs_m",
    )
    def _check_value_ranges(self):
        for rec in self:
            # Temperature
            if rec.temperature_c is not None and rec.temperature_c < 25:
                raise ValidationError(_("Temperature (°C) seems unrealistically low (< 25)."))
            if rec.temperature_c is not None and rec.temperature_c > 45:
                raise ValidationError(_("Temperature (°C) seems unrealistically high (> 45)."))

            # Heart Rate
            if rec.heart_rate_bpm is not None and rec.heart_rate_bpm < 0:
                raise ValidationError(_("Heart rate cannot be negative."))
            if rec.heart_rate_bpm is not None and rec.heart_rate_bpm > 260:
                raise ValidationError(_("Heart rate seems unrealistically high (> 260)."))

            # Respiratory Rate
            if rec.respiratory_rate_bpm is not None and rec.respiratory_rate_bpm < 0:
                raise ValidationError(_("Respiratory rate cannot be negative."))
            if rec.respiratory_rate_bpm is not None and rec.respiratory_rate_bpm > 80:
                raise ValidationError(_("Respiratory rate seems unrealistically high (> 80)."))

            # SpO2
            if rec.spo2_percent is not None and (rec.spo2_percent < 0 or rec.spo2_percent > 100):
                raise ValidationError(_("SpO₂ must be between 0 and 100%."))
            if rec.on_oxygen and (rec.o2_flow_l_min is None or rec.o2_flow_l_min <= 0):
                raise ValidationError(_("Please provide a positive O₂ Flow (L/min) when 'On Supplemental Oxygen' is enabled."))

            # Blood Pressure
            if rec.sbp_mm_hg is not None and rec.sbp_mm_hg <= 0:
                raise ValidationError(_("Systolic BP (mmHg) must be positive."))
            if rec.dbp_mm_hg is not None and rec.dbp_mm_hg <= 0:
                raise ValidationError(_("Diastolic BP (mmHg) must be positive."))
            if rec.sbp_mm_hg is not None and rec.dbp_mm_hg is not None and rec.sbp_mm_hg <= rec.dbp_mm_hg:
                raise ValidationError(_("Systolic BP must be greater than Diastolic BP."))

            # Anthropometrics
            if rec.weight_kg is not None and rec.weight_kg < 0:
                raise ValidationError(_("Weight (kg) cannot be negative."))
            if rec.height_cm is not None and rec.height_cm < 0:
                raise ValidationError(_("Height (cm) cannot be negative."))

    # -------------------------------------------------------------------------
    # UI helpers
    # -------------------------------------------------------------------------
    @api.depends(
        "measure_datetime",
        "temperature_c",
        "heart_rate_bpm",
        "sbp_mm_hg",
        "dbp_mm_hg",
        "spo2_percent",
    )
    def _compute_display_name(self):
        """Build a concise Odoo 19 display label for a vitals measurement."""
        for rec in self:
            label_parts = []
            if rec.measure_datetime:
                label_parts.append(fields.Datetime.to_string(rec.measure_datetime))
            if rec.temperature_c:
                label_parts.append(_("Temp %s°C") % rec.temperature_c)
            if rec.heart_rate_bpm:
                label_parts.append(_("HR %sbpm") % rec.heart_rate_bpm)
            if rec.sbp_mm_hg and rec.dbp_mm_hg:
                label_parts.append(_("BP %s/%s") % (rec.sbp_mm_hg, rec.dbp_mm_hg))
            if rec.spo2_percent:
                label_parts.append(_("SpO₂ %s%%") % rec.spo2_percent)
            rec.display_name = " | ".join(label_parts) if label_parts else _("Vitals")

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    def action_open_triage_session(self):
        """Open the parent triage session from a vitals record."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "clinic.triage.session",
            "res_id": self.triage_session_id.id,
            "view_mode": "form",
            "target": "current",
        }
