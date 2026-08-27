# -*- coding: utf-8 -*-
"""
patient_vital.py

Model:
- clinic.patient.vital : catatan ringan tanda-tanda vital per pasien
  (ringkas dan cepat, tidak menggantikan modul detail seperti clinic_triage_vitals)

Fitur:
- Perhitungan BMI (kg/m^2), BSA (Mosteller), Mean Arterial Pressure (MAP), GCS total
- Penanda abnormal (ringan) untuk BP/HR/RR/Temp/SpO2/Glukosa
- Integrasi opsional ke encounter/booking (smart button + domain aman)
- Attachment counter & action
- is_latest (berdasar measured_datetime) per record

Catatan:
- Semua integrasi lintas-modul dicek aman via _has_model() & env.ref(..., raise_if_not_found=False)
- Tidak mengubah clinic.patient secara langsung (low coupling)
"""
from math import sqrt
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =========================================================
# Helper: cek model ada/tidak di registry
# =========================================================
def _has_model(env, model_name):
    try:
        env[model_name]
        return True
    except KeyError:
        return False


# =========================================================
# Vitals (ringkas) per pasien
# =========================================================
class ClinicPatientVital(models.Model):
    _name = "clinic.patient.vital"
    _description = "Patient Vital (Lightweight)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "measured_datetime DESC, id DESC"

    # -----------------------------------
    # Scope & relasi utama
    # -----------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="patient_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    # TEMPORARILY DISABLED
    # Opsional tautan ke encounter/booking (jika modul aktif)
    # Catatan: tidak memaksa dependensi. Action akan aman jika modul belum terpasang.
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Encounter",
    #     help="Link to encounter if module 'clinic_encounter' is installed.",
    # )
    # booking_id = fields.Many2one(
    #     "booking.booking",
    #     string="Booking",
    #     help="Link to booking/check-in if module 'clinic_booking' is installed.",
    # )

    # -----------------------------------
    # Pengukuran & turunan
    # -----------------------------------
    measured_datetime = fields.Datetime(
        string="Measured On",
        required=True,
        default=lambda self: fields.Datetime.now(),
        tracking=True,
        help="Date/time when vitals were measured."
    )
    measured_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        string="Measured By",
        tracking=True,
    )
    device_name = fields.Char(string="Device Name/Model")
    device_serial = fields.Char(string="Device Serial")
    device_type = fields.Selection(
        [
            ("manual", "Manual"),
            ("monitor", "Patient Monitor"),
            ("bp_meter", "BP Meter"),
            ("thermometer", "Thermometer"),
            ("oximeter", "Pulse Oximeter"),
            ("glucometer", "Glucometer"),
            ("scale", "Scale"),
            ("stadiometer", "Stadiometer"),
            ("other", "Other"),
        ],
        default="manual",
    )

    # Tekanan darah (mmHg)
    bp_systolic = fields.Float(string="Systolic (mmHg)", digits=(10, 2), tracking=True)
    bp_diastolic = fields.Float(string="Diastolic (mmHg)", digits=(10, 2), tracking=True)
    bp_map = fields.Float(
        string="MAP (mmHg)",
        compute="_compute_derivatives",
        digits=(10, 2),
        store=True,
        help="Mean Arterial Pressure = Diastolic + (Systolic - Diastolic)/3",
    )

    # Nadi, napas, suhu, SpO2
    heart_rate = fields.Float(string="Heart Rate (bpm)", digits=(10, 2), tracking=True)
    respiratory_rate = fields.Float(string="Respiratory Rate (/min)", digits=(10, 2), tracking=True)
    temperature_c = fields.Float(string="Temperature (°C)", digits=(10, 2), tracking=True)
    spo2 = fields.Float(string="SpO₂ (%)", digits=(10, 2), tracking=True)

    # Tinggi/berat & turunan
    height_cm = fields.Float(string="Height (cm)", digits=(10, 2), tracking=True)
    weight_kg = fields.Float(string="Weight (kg)", digits=(10, 3), tracking=True)
    bmi = fields.Float(
        string="BMI (kg/m²)",
        compute="_compute_derivatives",
        store=True,
        digits=(10, 2),
        help="Body Mass Index = kg / (m²).",
    )
    bsa = fields.Float(
        string="BSA (m²)",
        compute="_compute_derivatives",
        store=True,
        digits=(10, 3),
        help="Mosteller BSA = sqrt((cm * kg) / 3600).",
    )

    # Lain-lain
    muac_cm = fields.Float(string="MUAC (cm)", digits=(10, 2), help="Mid-Upper Arm Circumference.")
    head_circumference_cm = fields.Float(string="Head Circumference (cm)", digits=(10, 2))
    pain_scale = fields.Integer(string="Pain (0–10)", help="Numeric pain scale (0–10).")

    # GCS
    gcs_eye = fields.Selection(
        [(str(i), str(i)) for i in range(1, 5)], string="GCS Eye", help="1–4"
    )
    gcs_verbal = fields.Selection(
        [(str(i), str(i)) for i in range(1, 6)], string="GCS Verbal", help="1–5"
    )
    gcs_motor = fields.Selection(
        [(str(i), str(i)) for i in range(1, 7)], string="GCS Motor", help="1–6"
    )
    gcs_total = fields.Integer(
        string="GCS Total",
        compute="_compute_derivatives",
        store=True,
        help="Sum of E+V+M (3–15).",
    )

    # Glukosa darah (mg/dL)
    blood_glucose_mgdl = fields.Float(string="Blood Glucose (mg/dL)", digits=(10, 1))

    # -----------------------------------
    # Flags ringkas & tampilan
    # -----------------------------------
    is_latest = fields.Boolean(
        compute="_compute_is_latest",
        string="Is Latest",
        store=False,
        help="True if this is the latest vital record for the patient.",
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)
    notes = fields.Text()
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    # Abnormal flags (heuristik ringan, dewasa umum — dapat disesuaikan)
    bp_flag = fields.Selection(
        [
            ("low", "Low"),
            ("high", "High"),
            ("borderline", "Borderline"),
            ("normal", "Normal"),
            ("unknown", "Unknown"),
        ],
        compute="_compute_flags",
        store=True,
    )
    hr_flag = fields.Selection(
        [("low", "Low"), ("high", "High"), ("normal", "Normal"), ("unknown", "Unknown")],
        compute="_compute_flags",
        store=True,
    )
    rr_flag = fields.Selection(
        [("low", "Low"), ("high", "High"), ("normal", "Normal"), ("unknown", "Unknown")],
        compute="_compute_flags",
        store=True,
    )
    temp_flag = fields.Selection(
        [("low", "Low/Hypothermia"), ("high", "Fever"), ("normal", "Normal"), ("unknown", "Unknown")],
        compute="_compute_flags",
        store=True,
    )
    spo2_flag = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("unknown", "Unknown")],
        compute="_compute_flags",
        store=True,
    )
    glucose_flag = fields.Selection(
        [("low", "Hypoglycemia"), ("high", "Hyperglycemia"), ("normal", "Normal"), ("unknown", "Unknown")],
        compute="_compute_flags",
        store=True,
    )

    # -----------------------------------
    # SQL constraints
    # -----------------------------------
    _constraint_unique_patient_datetime = models.Constraint(
        'unique(patient_id, measured_datetime)',
        'A vital record for this patient at the same time already exists.',
    )

    # =========================================================
    # COMPUTE
    # =========================================================
    @api.depends(
        "bp_systolic",
        "bp_diastolic",
        "height_cm",
        "weight_kg",
        "gcs_eye",
        "gcs_verbal",
        "gcs_motor",
    )
    def _compute_derivatives(self):
        for rec in self:
            # MAP
            if rec.bp_systolic and rec.bp_diastolic:
                rec.bp_map = rec.bp_diastolic + (rec.bp_systolic - rec.bp_diastolic) / 3.0
            else:
                rec.bp_map = 0.0

            # BMI & BSA
            try:
                h_m = (rec.height_cm or 0.0) / 100.0
                if rec.weight_kg and h_m > 0:
                    rec.bmi = rec.weight_kg / (h_m * h_m)
                    rec.bsa = sqrt(((rec.height_cm or 0.0) * rec.weight_kg) / 3600.0)
                else:
                    rec.bmi = 0.0
                    rec.bsa = 0.0
            except Exception:
                rec.bmi = 0.0
                rec.bsa = 0.0

            # GCS total
            e = int(rec.gcs_eye) if rec.gcs_eye else 0
            v = int(rec.gcs_verbal) if rec.gcs_verbal else 0
            m = int(rec.gcs_motor) if rec.gcs_motor else 0
            rec.gcs_total = e + v + m if (e and v and m) else 0

    @api.depends(
        "bp_systolic",
        "bp_diastolic",
        "heart_rate",
        "respiratory_rate",
        "temperature_c",
        "spo2",
        "blood_glucose_mgdl",
    )
    def _compute_flags(self):
        """Heuristik dewasa umum:
        - BP normal kira-kira < 120/80; borderline 120–129/<80; high >= 130/80; low < 90/60
        - HR normal 60–100 bpm
        - RR normal 12–20 /min
        - Temp normal 36.1–37.2 °C; fever >= 38.0; low < 35.0
        - SpO2 normal >= 95%; low < 95%
        - Glukosa puasa: normal ~70–99 mg/dL; low < 70; high >= 126 (heuristik)
        """
        for rec in self:
            # BP
            if rec.bp_systolic and rec.bp_diastolic:
                if rec.bp_systolic < 90 or rec.bp_diastolic < 60:
                    rec.bp_flag = "low"
                elif rec.bp_systolic >= 130 or rec.bp_diastolic >= 80:
                    rec.bp_flag = "high"
                elif 120 <= rec.bp_systolic < 130 and rec.bp_diastolic < 80:
                    rec.bp_flag = "borderline"
                else:
                    rec.bp_flag = "normal"
            else:
                rec.bp_flag = "unknown"

            # HR
            if rec.heart_rate:
                rec.hr_flag = "normal" if 60 <= rec.heart_rate <= 100 else ("low" if rec.heart_rate < 60 else "high")
            else:
                rec.hr_flag = "unknown"

            # RR
            if rec.respiratory_rate:
                rec.rr_flag = "normal" if 12 <= rec.respiratory_rate <= 20 else ("low" if rec.respiratory_rate < 12 else "high")
            else:
                rec.rr_flag = "unknown"

            # Temperature
            if rec.temperature_c:
                if rec.temperature_c < 35.0:
                    rec.temp_flag = "low"
                elif rec.temperature_c >= 38.0:
                    rec.temp_flag = "high"
                elif 36.1 <= rec.temperature_c <= 37.2:
                    rec.temp_flag = "normal"
                else:
                    rec.temp_flag = "normal"  # borderline dianggap normal
            else:
                rec.temp_flag = "unknown"

            # SpO2
            if rec.spo2:
                rec.spo2_flag = "normal" if rec.spo2 >= 95 else "low"
            else:
                rec.spo2_flag = "unknown"

            # Glucose
            if rec.blood_glucose_mgdl:
                if rec.blood_glucose_mgdl < 70:
                    rec.glucose_flag = "low"
                elif rec.blood_glucose_mgdl >= 126:
                    rec.glucose_flag = "high"
                else:
                    rec.glucose_flag = "normal"
            else:
                rec.glucose_flag = "unknown"

    @api.depends("patient_id", "measured_datetime")
    def _compute_is_latest(self):
        """True bila record ini adalah vital terbaru untuk patient terkait."""
        for rec in self:
            if not rec.patient_id:
                rec.is_latest = False
                continue
            latest = self.search(
                [("patient_id", "=", rec.patient_id.id)],
                order="measured_datetime DESC, id DESC",
                limit=1,
            )
            rec.is_latest = (latest.id == rec.id) if latest else False

    @api.depends(
        "measured_datetime",
        "bp_systolic",
        "bp_diastolic",
        "heart_rate",
        "respiratory_rate",
        "temperature_c",
        "spo2",
        "bmi",
    )
    def _compute_display_name(self):
        for rec in self:
            dt = fields.Datetime.context_timestamp(rec, rec.measured_datetime) if rec.measured_datetime else None
            dt_txt = dt.strftime("%Y-%m-%d %H:%M") if dt else "—"
            bp_txt = f"{int(rec.bp_systolic)}/{int(rec.bp_diastolic)}" if (rec.bp_systolic and rec.bp_diastolic) else "--/--"
            hr = f"{int(rec.heart_rate)}" if rec.heart_rate else "--"
            rr = f"{int(rec.respiratory_rate)}" if rec.respiratory_rate else "--"
            t = f"{rec.temperature_c:.1f}" if rec.temperature_c else "--"
            s = f"{int(rec.spo2)}%" if rec.spo2 else "--"
            bmi = f"{rec.bmi:.1f}" if rec.bmi else "--"
            rec.display_name = f"{dt_txt} • BP {bp_txt} • HR {hr} • RR {rr} • T {t} • SpO₂ {s} • BMI {bmi}"

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachment_count = Attachment.search_count([
                ("res_model", "=", self._name),
                ("res_id", "=", rec.id),
            ])

    # =========================================================
    # CONSTRAINTS
    # =========================================================
    @api.constrains(
        "bp_systolic",
        "bp_diastolic",
        "heart_rate",
        "respiratory_rate",
        "temperature_c",
        "spo2",
        "height_cm",
        "weight_kg",
        "pain_scale",
        "blood_glucose_mgdl",
    )
    def _check_plausible_ranges(self):
        for rec in self:
            # Non negatif & wajar (batas longgar agar tidak mengganggu data real)
            if rec.bp_systolic and rec.bp_systolic < 40:
                raise ValidationError(_("Systolic seems too low."))
            if rec.bp_systolic and rec.bp_systolic > 300:
                raise ValidationError(_("Systolic seems too high."))
            if rec.bp_diastolic and rec.bp_diastolic < 20:
                raise ValidationError(_("Diastolic seems too low."))
            if rec.bp_diastolic and rec.bp_diastolic > 200:
                raise ValidationError(_("Diastolic seems too high."))
            if rec.heart_rate and (rec.heart_rate < 20 or rec.heart_rate > 250):
                raise ValidationError(_("Heart Rate out of plausible range."))
            if rec.respiratory_rate and (rec.respiratory_rate < 5 or rec.respiratory_rate > 80):
                raise ValidationError(_("Respiratory Rate out of plausible range."))
            if rec.temperature_c and (rec.temperature_c < 30 or rec.temperature_c > 45):
                raise ValidationError(_("Temperature (°C) out of plausible range."))
            if rec.spo2 and (rec.spo2 < 50 or rec.spo2 > 100):
                raise ValidationError(_("SpO₂ out of plausible range (50–100)."))
            if rec.height_cm and (rec.height_cm < 20 or rec.height_cm > 260):
                raise ValidationError(_("Height (cm) out of plausible range."))
            if rec.weight_kg and (rec.weight_kg < 1 or rec.weight_kg > 500):
                raise ValidationError(_("Weight (kg) out of plausible range."))
            if rec.pain_scale and (rec.pain_scale < 0 or rec.pain_scale > 10):
                raise ValidationError(_("Pain scale must be between 0 and 10."))
            if rec.blood_glucose_mgdl and (rec.blood_glucose_mgdl < 20 or rec.blood_glucose_mgdl > 1000):
                raise ValidationError(_("Blood glucose (mg/dL) out of plausible range."))

            # Konsistensi BP
            if rec.bp_systolic and rec.bp_diastolic and rec.bp_systolic <= rec.bp_diastolic:
                raise ValidationError(_("Systolic must be greater than Diastolic."))

    # =========================================================
    # CRUD OVERRIDES
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        # Standarisasi minimal: measured_by & measured_datetime
        for vals in vals_list:
            vals.setdefault("measured_by", self.env.user.id)
            vals.setdefault("measured_datetime", fields.Datetime.now())

        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        res = super().write(vals)
        return res

    # =========================================================
    # SMART ACTIONS
    # =========================================================
    def _action_open_generic(self, xmlid_candidates, domain, name, res_model, context_add=None):
        self.ensure_one()
        action = False
        for xmlid in xmlid_candidates:
            if not xmlid:
                continue
            act = self.env.ref(xmlid, raise_if_not_found=False)
            if act:
                action = act.read()[0]
                break
        if not action:
            action = {
                "type": "ir.actions.act_window",
                "name": name,
                "res_model": res_model,
                "view_mode": "list,form,kanban,calendar,graph,pivot",
                "target": "current",
                "domain": domain,
                "context": {},
            }
        ctx = action.get("context", {}) or {}
        ctx.update({
            "search_default_patient_id": self.patient_id.id,
            "default_patient_id": self.patient_id.id,
        })
        if context_add:
            ctx.update(context_add)
        action["context"] = ctx
        action["domain"] = domain
        return action

    def action_open_patient(self):
        """Buka form pasien terkait."""
        self.ensure_one()
        act = self.env.ref("clinic_patient.action_clinic_patient", raise_if_not_found=False)
        if act:
            action = act.read()[0]
            action.update({
                "res_id": self.patient_id.id,
                "view_mode": "form",
                "views": False,
            })
            return action
        # fallback
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "clinic.patient",
            "res_id": self.patient_id.id,
            "view_mode": "form",
            "target": "current",
        }
    # TEMPORARILY DISABLED
    # def action_open_related_encounters(self):
    #     """Buka encounter terkait pasien (atau langsung record yang ditaut jika ada)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.encounter"):
    #         raise UserError(_("Module 'clinic_encounter' is not installed."))
    #     if self.encounter_id:
    #         # buka form encounter spesifik
    #         act = self.env.ref("clinic_encounter.action_clinic_encounter", raise_if_not_found=False)
    #         if act:
    #             action = act.read()[0]
    #             action.update({"res_id": self.encounter_id.id, "view_mode": "form"})
    #             return action
    #         return {
    #             "type": "ir.actions.act_window",
    #             "name": _("Encounter"),
    #             "res_model": "clinic.encounter",
    #             "res_id": self.encounter_id.id,
    #             "view_mode": "form",
    #         }
    #     # buka daftar encounter pasien
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_encounter.action_clinic_encounter_from_patient",
    #             "clinic_encounter.action_clinic_encounter",
    #         ],
    #         domain=domain,
    #         name=_("Encounters"),
    #         res_model="clinic.encounter",
    #     )
    # TEMPORARILY DISABLED
    # def action_open_related_bookings(self):
    #     """Buka booking terkait pasien (atau form booking jika ada tautan)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "booking.booking"):
    #         raise UserError(_("Module 'clinic_booking' is not installed."))
    #     if self.booking_id:
    #         act = self.env.ref("clinic_booking.action_clinic_booking", raise_if_not_found=False)
    #         if act:
    #             action = act.read()[0]
    #             action.update({"res_id": self.booking_id.id, "view_mode": "form"})
    #             return action
    #         return {
    #             "type": "ir.actions.act_window",
    #             "name": _("Booking"),
    #             "res_model": "booking.booking",
    #             "res_id": self.booking_id.id,
    #             "view_mode": "form",
    #         }
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_booking.action_clinic_booking_from_patient",
    #             "clinic_booking.action_clinic_booking",
    #         ],
    #         domain=domain,
    #         name=_("Bookings"),
    #         res_model="booking.booking",
    #     )

    def action_open_attachments(self):
        """Smart button lampiran pada catatan vital."""
        self.ensure_one()
        action = self.env.ref("base.action_attachment", raise_if_not_found=False)
        result = action and action.read()[0] or {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
        result["domain"] = [("res_model", "=", self._name), ("res_id", "=", self.id)]
        return result

    # =========================================================
    # NAME GET / SEARCH
    # =========================================================
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or _("Vital")
            res.append((rec.id, name))
        return res

    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Search vital records by patient name or clinical notes."""
        domain = domain or []
        search_domain = []
        if name:
            search_domain = [
                "|",
                ("patient_id.name", operator, name),
                ("notes", operator, name),
            ]

        records = self.search(search_domain + domain, limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]

