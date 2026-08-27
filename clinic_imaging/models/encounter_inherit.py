# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers (safe checks so module works even if other addons not yet installed)
# =============================================================================
class _EncounterImagingHelpers(models.AbstractModel):
    _name = "clinical.imaging.encounter.helpers"
    _description = "Encounter Imaging Helpers"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_now(self):
        return fields.Datetime.now()

    def _today_bounds(self):
        start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        end = start + timedelta(days=1, seconds=-1)
        return start, end

    @api.depends("encounter_id")
    def _compute_patient_from_encounter(self):
        """Resolve the patient from the linked encounter for inheriting models.

        Both Screening and Encounter Note use this compute contract.  Keeping
        it on the shared helper prevents a string-based compute reference from
        existing on a model that does not actually implement the method.
        """
        for rec in self:
            patient = False
            encounter = rec.encounter_id
            if encounter:
                if "patient_id" in encounter._fields:
                    patient = encounter.patient_id
                elif "patient_partner_id" in encounter._fields:
                    patient = encounter.patient_partner_id
                elif "partner_id" in encounter._fields:
                    patient = encounter.partner_id
            rec.patient_id = patient


# =============================================================================
# Inherit clinic.encounter — Imaging Integrations
# =============================================================================
class ClinicEncounter(models.Model, _EncounterImagingHelpers):
    _inherit = "clinic.encounter"

    # -------------------------------------------------------------------------
    # Relations to Imaging domain
    # -------------------------------------------------------------------------
    imaging_request_ids = fields.One2many(
        "clinical.imaging.request",
        "encounter_id",
        string="Imaging Requests",
        help="Imaging requests created for this encounter."
    )
    imaging_ids = fields.One2many(
        "clinical.imaging",
        "encounter_id",
        string="Imaging Records",
        help="Imaging records performed under this encounter."
    )
    imaging_screening_id = fields.Many2one(
        "clinical.imaging.encounter.screening",
        string="Imaging Screening",
        help="Pre-imaging screening summary for this encounter (safety/eligibility)."
    )
    imaging_note_ids = fields.One2many(
        "clinical.imaging.encounter.note",
        "encounter_id",
        string="Imaging Notes",
        help="Notes related to imaging for this encounter (pre/intra/post/safety)."
    )

    # -------------------------------------------------------------------------
    # KPI counters (computed on the fly)
    # -------------------------------------------------------------------------
    imaging_request_count = fields.Integer(string="Imaging Requests", compute="_compute_imaging_kpis", store=False)
    imaging_count = fields.Integer(string="Imaging Records", compute="_compute_imaging_kpis", store=False)
    imaging_result_count = fields.Integer(string="Imaging Results", compute="_compute_imaging_kpis", store=False)
    imaging_study_count = fields.Integer(string="Studies", compute="_compute_imaging_kpis", store=False)
    imaging_series_count = fields.Integer(string="Series", compute="_compute_imaging_kpis", store=False)
    imaging_image_count = fields.Integer(string="Images", compute="_compute_imaging_kpis", store=False)
    imaging_finding_count = fields.Integer(string="Findings", compute="_compute_imaging_kpis", store=False)
    imaging_key_image_count = fields.Integer(string="Key Images", compute="_compute_imaging_kpis", store=False)

    has_imaging_pending = fields.Boolean(
        string="Has Pending Imaging",
        compute="_compute_pending_status",
        store=False,
        help="True if there are pending imaging requests or non-final results in this encounter."
    )
    last_imaging_datetime = fields.Datetime(string="Last Imaging Datetime", compute="_compute_last_dates", store=False)
    last_result_datetime = fields.Datetime(string="Last Result Signed", compute="_compute_last_dates", store=False)

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_imaging_kpis(self):
        Request = self.env["clinical.imaging.request"].sudo() if self._has_model("clinical.imaging.request") else None
        Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
        Series = self.env["clinical.imaging.series"].sudo() if self._has_model("clinical.imaging.series") else None
        Image = self.env["clinical.imaging.image"].sudo() if self._has_model("clinical.imaging.image") else None
        Finding = self.env["clinical.imaging.finding"].sudo() if self._has_model("clinical.imaging.finding") else None

        for rec in self:
            rec.imaging_request_count = Request.search_count([("encounter_id", "=", rec.id)]) if Request else 0
            rec.imaging_count = Imaging.search_count([("encounter_id", "=", rec.id)]) if Imaging else 0
            rec.imaging_result_count = Result.search_count([("encounter_id", "=", rec.id)]) if (Result and self._has_field("clinical.imaging.result", "encounter_id")) else (
                Result.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Result else 0
            )
            rec.imaging_study_count = Study.search_count([("encounter_id", "=", rec.id)]) if (Study and self._has_field("clinical.imaging.study", "encounter_id")) else (
                Study.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Study else 0
            )
            rec.imaging_series_count = Series.search_count([("encounter_id", "=", rec.id)]) if (Series and self._has_field("clinical.imaging.series", "encounter_id")) else (
                Series.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Series else 0
            )
            rec.imaging_image_count = Image.search_count([("encounter_id", "=", rec.id)]) if (Image and self._has_field("clinical.imaging.image", "encounter_id")) else (
                Image.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Image else 0
            )
            # Findings (direct link may not exist)
            if Finding and self._has_field("clinical.imaging.finding", "encounter_id"):
                rec.imaging_finding_count = Finding.search_count([("encounter_id", "=", rec.id)])
            elif Finding and Imaging:
                imaging_ids = Imaging.search([("encounter_id", "=", rec.id)]).ids
                rec.imaging_finding_count = Finding.search_count([("imaging_id", "in", imaging_ids)]) if imaging_ids else 0
            else:
                rec.imaging_finding_count = 0

            # Key images
            if Image and Imaging:
                imaging_ids = Imaging.search([("encounter_id", "=", rec.id)]).ids
                rec.imaging_key_image_count = Image.search_count([("imaging_id", "in", imaging_ids), ("is_key", "=", True)]) if imaging_ids and self._has_field("clinical.imaging.image", "is_key") else 0
            else:
                rec.imaging_key_image_count = 0

    def _compute_pending_status(self):
        Request = self.env["clinical.imaging.request"].sudo() if self._has_model("clinical.imaging.request") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        for rec in self:
            pending_req = 0
            pending_res = 0
            if Request and self._has_field("clinical.imaging.request", "state"):
                pending_req = Request.search_count([
                    ("encounter_id", "=", rec.id),
                    ("state", "in", ["draft", "submitted", "approved", "scheduled", "in_progress"])
                ])
            if Result and self._has_field("clinical.imaging.result", "state"):
                if self._has_field("clinical.imaging.result", "encounter_id"):
                    pending_res = Result.search_count([
                        ("encounter_id", "=", rec.id),
                        ("state", "not in", ["final", "amended"])
                    ])
                else:
                    # via imaging
                    pending_res = Result.search_count([
                        ("imaging_id.encounter_id", "=", rec.id),
                        ("state", "not in", ["final", "amended"])
                    ])
            rec.has_imaging_pending = bool(pending_req or pending_res)

    def _compute_last_dates(self):
        Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        for rec in self:
            rec.last_imaging_datetime = False
            rec.last_result_datetime = False
            if Study and Imaging:
                imaging_ids = Imaging.search([("encounter_id", "=", rec.id)]).ids
                if imaging_ids:
                    st = Study.search([("imaging_id", "in", imaging_ids)], limit=1, order="study_datetime desc")
                    rec.last_imaging_datetime = st.study_datetime if st else False
            if Result:
                if self._has_field("clinical.imaging.result", "encounter_id"):
                    rs = Result.search([("encounter_id", "=", rec.id), ("signed_datetime", "!=", False)], limit=1, order="signed_datetime desc")
                else:
                    rs = Result.search([("imaging_id.encounter_id", "=", rec.id), ("signed_datetime", "!=", False)], limit=1, order="signed_datetime desc")
                rec.last_result_datetime = rs.signed_datetime if rs else False

    # -------------------------------------------------------------------------
    # Smart-button actions
    # -------------------------------------------------------------------------
    def _action_window(self, name, model, domain, view_mode="list,form,kanban"):
        self.ensure_one()
        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": model,
            "view_mode": view_mode,
            "domain": domain,
            "target": "current",
            "context": {
                "default_encounter_id": self.id,
                "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
                "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
                "default_treatment_id": getattr(self, "treatment_id", False) and self.treatment_id.id or False,
            },
        }

    def action_open_imaging_requests(self):
        return self._action_window(_("Imaging Requests"), "clinical.imaging.request", [("encounter_id", "=", self.id)])

    def action_open_imaging_records(self):
        return self._action_window(_("Imaging Records"), "clinical.imaging", [("encounter_id", "=", self.id)])

    def action_open_imaging_results(self):
        Result = "clinical.imaging.result"
        domain = [("encounter_id", "=", self.id)] if self._has_field(Result, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
        return self._action_window(_("Imaging Results"), Result, domain, view_mode="list,form")

    def action_open_imaging_studies(self):
        Study = "clinical.imaging.study"
        domain = [("encounter_id", "=", self.id)] if self._has_field(Study, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
        return self._action_window(_("Studies"), Study, domain, view_mode="list,form,kanban")

    def action_open_imaging_series(self):
        Series = "clinical.imaging.series"
        domain = [("encounter_id", "=", self.id)] if self._has_field(Series, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
        return self._action_window(_("Series"), Series, domain, view_mode="list,form,kanban")

    def action_open_imaging_images(self):
        Image = "clinical.imaging.image"
        domain = [("encounter_id", "=", self.id)] if self._has_field(Image, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
        return self._action_window(_("Images"), Image, domain, view_mode="list,form,kanban")

    def action_open_imaging_findings(self):
        Finding = "clinical.imaging.finding"
        domain = [("encounter_id", "=", self.id)] if self._has_field(Finding, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
        return self._action_window(_("Findings"), Finding, domain, view_mode="list,form,kanban")

    def action_open_imaging_screening(self):
        self.ensure_one()
        if self.imaging_screening_id:
            return {
                "name": _("Imaging Screening"),
                "type": "ir.actions.act_window",
                "res_model": "clinical.imaging.encounter.screening",
                "view_mode": "form",
                "res_id": self.imaging_screening_id.id,
                "target": "current",
            }
        # If none, open creation form
        return {
            "name": _("New Imaging Screening"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.encounter.screening",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_encounter_id": self.id,
                "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
                "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
            },
        }

    def action_new_imaging_request(self):
        """Quick-create Imaging Request from this encounter."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.request"):
            raise UserError(_("Imaging Request model is not available."))
        return {
            "name": _("New Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_encounter_id": self.id,
                "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
                "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
                "default_treatment_id": getattr(self, "treatment_id", False) and self.treatment_id.id or False,
                "default_referring_partner_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
            },
        }


# =============================================================================
# clinical.imaging.encounter.screening — Pre-imaging eligibility & safety
# =============================================================================
class ClinicalImagingEncounterScreening(models.Model, _EncounterImagingHelpers):
    _name = "clinical.imaging.encounter.screening"
    _description = "Encounter Imaging Screening"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "encounter_id, create_date desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Ownership
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Screening Number",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        help="Unique identifier generated from sequence at creation."
    )
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Encounter context
    # -------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True
    )
    # patient_id = fields.Many2one(
    #     "res.partner",
    #     string="Patient",
    #     related="encounter_id.patient_id",
    #     store=True,
    #     readonly=True
    # )
    # ganti field related menjadi compute
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        compute="_compute_patient_from_encounter",
        store=True,
        readonly=False,
        help="Resolved from encounter when available."
    )

    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        help="Related appointment for this screening."
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Related treatment plan if applicable."
    )

    # -------------------------------------------------------------------------
    # Vitals & Anthropometrics
    # -------------------------------------------------------------------------
    height_cm = fields.Float(string="Height (cm)")
    weight_kg = fields.Float(string="Weight (kg)")
    bmi = fields.Float(string="BMI", compute="_compute_bmi", store=True)
    systolic_bp = fields.Integer(string="Systolic BP (mmHg)")
    diastolic_bp = fields.Integer(string="Diastolic BP (mmHg)")
    heart_rate_bpm = fields.Integer(string="Heart Rate (bpm)")
    temperature_c = fields.Float(string="Temperature (°C)")
    spo2_percent = fields.Float(string="SpO2 (%)")

    # -------------------------------------------------------------------------
    # Safety (contrast/MRI/radiation)
    # -------------------------------------------------------------------------
    pregnancy_status = fields.Selection(
        [("unknown", "Unknown"), ("no", "Not Pregnant"), ("yes", "Pregnant"), ("na", "Not Applicable")],
        string="Pregnancy Status", default="unknown"
    )
    lmp_date = fields.Date(string="Last Menstruation Date")
    pregnancy_test_done = fields.Boolean(string="Pregnancy Test Done")
    pregnancy_test_result = fields.Selection(
        [("unknown", "Unknown"), ("negative", "Negative"), ("positive", "Positive")],
        string="Pregnancy Test Result", default="unknown"
    )

    contrast_allergy = fields.Boolean(string="Contrast Allergy")
    premed_required = fields.Boolean(string="Premedication Required")
    premed_given = fields.Boolean(string="Premedication Given")
    premed_protocol = fields.Text(string="Premedication Protocol")

    egfr_value = fields.Float(string="eGFR (mL/min/1.73m²)")
    egfr_date = fields.Date(string="eGFR Date")
    egfr_method = fields.Selection([("ckd_epi", "CKD-EPI"), ("mdrd", "MDRD"), ("other", "Other")], string="eGFR Method")
    renal_risk = fields.Selection(
        [("unknown", "Unknown"), ("low", "Low"), ("moderate", "Moderate"), ("high", "High")],
        string="Renal Risk", compute="_compute_renal_risk", store=True
    )

    has_metal_implants = fields.Boolean(string="Metal Implants")
    has_pacemaker = fields.Boolean(string="Pacemaker/ICD")
    has_cochlear_implant = fields.Boolean(string="Cochlear Implant")
    implant_description = fields.Char(string="Implant Description")

    iv_access = fields.Selection(
        [("none", "None"), ("peripheral", "Peripheral IV"), ("central", "Central Line")],
        string="IV Access"
    )
    fasting_hours = fields.Float(string="Fasting Hours")

    # Sedation plan
    sedation_plan = fields.Selection(
        [("none", "None"), ("minimal", "Minimal"), ("conscious", "Conscious Sedation"),
         ("deep", "Deep Sedation"), ("ga", "General Anesthesia")],
        string="Sedation Plan", default="none"
    )
    sedation_notes = fields.Text(string="Sedation Notes")

    @api.depends("encounter_id")
    def _compute_patient_from_encounter(self):
        for rec in self:
            patient = False
            enc = rec.encounter_id
            if enc:
                # Prefer exact patient field names if they exist
                if "patient_id" in enc._fields:
                    patient = enc.patient_id
                elif "patient_partner_id" in enc._fields:
                    patient = enc.patient_partner_id
                elif "partner_id" in enc._fields:
                    patient = enc.partner_id
            rec.patient_id = patient

    # -------------------------------------------------------------------------
    # Consent & Documents
    # -------------------------------------------------------------------------
    consent_id = fields.Many2one("clinic.consent.form", string="Consent", help="Linked consent document for the exam.")
    attachment_count = fields.Integer(string="Attachments", compute="_compute_attachment_count", store=False)

    # -------------------------------------------------------------------------
    # Audit & Verification
    # -------------------------------------------------------------------------
    performed_by_id = fields.Many2one("hr.employee", string="Performed By")
    performed_datetime = fields.Datetime(string="Performed At", default=fields.Datetime.now)
    verified_by_id = fields.Many2one("hr.employee", string="Verified By", domain=[("is_doctor", "=", True)])
    verified_datetime = fields.Datetime(string="Verified At")
    state = fields.Selection(
        [("draft", "Draft"), ("verified", "Verified"), ("cancelled", "Cancelled")],
        string="Status", default="draft", tracking=True, index=True
    )
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # CONSTRAINTS / COMPUTES
    # -------------------------------------------------------------------------
    @api.constrains("height_cm", "weight_kg", "systolic_bp", "diastolic_bp", "heart_rate_bpm", "temperature_c", "spo2_percent", "egfr_value", "fasting_hours")
    def _check_ranges(self):
        for rec in self:
            if rec.height_cm is not None and rec.height_cm < 0:
                raise ValidationError(_("Height cannot be negative."))
            if rec.weight_kg is not None and rec.weight_kg < 0:
                raise ValidationError(_("Weight cannot be negative."))
            if rec.temperature_c is not None and (rec.temperature_c < 30 or rec.temperature_c > 45):
                raise ValidationError(_("Temperature appears out of realistic range."))
            if rec.spo2_percent is not None and (rec.spo2_percent < 0 or rec.spo2_percent > 100):
                raise ValidationError(_("SpO2 must be between 0 and 100%."))
            if rec.egfr_value is not None and (rec.egfr_value < 0 or rec.egfr_value > 200):
                raise ValidationError(_("eGFR must be in a realistic range (0..200)."))
            if rec.fasting_hours is not None and rec.fasting_hours < 0:
                raise ValidationError(_("Fasting Hours cannot be negative."))

    @api.depends("height_cm", "weight_kg")
    def _compute_bmi(self):
        for rec in self:
            if rec.height_cm and rec.weight_kg and rec.height_cm > 0:
                h_m = rec.height_cm / 100.0
                rec.bmi = round(rec.weight_kg / (h_m * h_m), 2)
            else:
                rec.bmi = 0.0

    @api.depends("egfr_value", "egfr_date")
    def _compute_renal_risk(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.egfr_value or not rec.egfr_date:
                rec.renal_risk = "unknown"
                continue
            # simple thresholds
            if rec.egfr_value < 30:
                risk = "high"
            elif rec.egfr_value < 45:
                risk = "moderate"
            else:
                risk = "low"
            # optionally enforce recency window (e.g., last 1 year)
            rec.renal_risk = risk

    @api.onchange("contrast_allergy")
    def _onchange_contrast_allergy(self):
        for rec in self:
            if rec.contrast_allergy and rec.premed_required is False:
                rec.premed_required = True

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.encounter.screening") or _("New")
            # Link back to encounter default field
            if vals.get("encounter_id") and not vals.get("appointment_id"):
                enc = self.env["clinic.encounter"].browse(vals["encounter_id"])
                if enc and hasattr(enc, "appointment_id") and enc.appointment_id:
                    vals["appointment_id"] = enc.appointment_id.id
        recs = super().create(vals_list)
        # If encounter has no screening set, attach the newly created one
        for rec in recs:
            if rec.encounter_id and not rec.encounter_id.imaging_screening_id:
                rec.encounter_id.imaging_screening_id = rec.id
        return recs

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("verified_by_id", False)
        default.setdefault("verified_datetime", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_verify(self):
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cancelled screening cannot be verified."))
            rec.state = "verified"
            rec.verified_by_id = self.env.user.employee_id.id if hasattr(self.env.user, "employee_id") else False
            rec.verified_datetime = fields.Datetime.now()
            rec.message_post(body=_("Screening verified."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "verified":
                raise UserError(_("Verified screening cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body=_("Screening cancelled. %s") % (reason or ""))

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------
    @api.depends("name", "encounter_id")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or _("New")
            if rec.encounter_id:
                label = f"{label} ({rec.encounter_id.display_name})"
            rec.display_name = label

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Screening Number must be unique per company.',
    )


# =============================================================================
# clinical.imaging.encounter.note — Free-form notes tied to encounter
# =============================================================================
class ClinicalImagingEncounterNote(models.Model, _EncounterImagingHelpers):
    _name = "clinical.imaging.encounter.note"
    _description = "Encounter Imaging Note"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "encounter_id, create_date desc"
    _check_company_auto = True

    name = fields.Char(
        string="Note Number",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        help="Unique identifier generated from sequence at creation."
    )
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # TUNGGU addon ACTIVE
    encounter_id = fields.Many2one("clinic.encounter", string="Encounter", required=True, ondelete="cascade", index=True)
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True
    )
    # patient_id = fields.Many2one("res.partner", string="Patient", related="encounter_id.patient_id", store=True, readonly=True)
        
    # ganti related menjadi compute seperti di screening
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        compute="_compute_patient_from_encounter",
        store=True,
        readonly=False
    )

    note_type = fields.Selection(
        [
            ("general", "General"),
            ("pre", "Pre-Imaging"),
            ("intra", "Intra-Procedural"),
            ("post", "Post-Imaging"),
            ("safety", "Safety"),
        ],
        string="Note Type",
        default="general",
        index=True
    )
    content = fields.Text(string="Content", required=True)
    author_user_id = fields.Many2one("res.users", string="Author User", default=lambda s: s.env.user, readonly=True)
    author_employee_id = fields.Many2one("hr.employee", string="Author Employee", compute="_compute_author_employee", store=False)
    pinned = fields.Boolean(string="Pinned")

    attachment_count = fields.Integer(string="Attachments", compute="_compute_attachment_count", store=False)

    # TUNGGU addon ACTIVE
    # @api.depends("encounter_id")
    # def _compute_patient_from_encounter(self):
    #     for rec in self:
    #         patient = False
    #         enc = rec.encounter_id
    #         if enc:
    #             if "patient_id" in enc._fields:
    #                 patient = enc.patient_id
    #             elif "patient_partner_id" in enc._fields:
    #                 patient = enc.patient_partner_id
    #             elif "partner_id" in enc._fields:
    #                 patient = enc.partner_id
    #         rec.patient_id = patient

    def _compute_author_employee(self):
        for rec in self:
            rec.author_employee_id = rec.author_user_id.employee_id if rec.author_user_id and hasattr(rec.author_user_id, "employee_id") else False

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.encounter.note") or _("New")
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        return super().copy(default)

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    @api.depends("name", "note_type", "encounter_id")
    def _compute_display_name(self):
        selection = dict(self._fields["note_type"].selection)
        for rec in self:
            title = rec.name or _("New")
            if rec.note_type:
                title = f"{title} [{selection.get(rec.note_type, rec.note_type)}]"
            if rec.encounter_id:
                title = f"{title} ({rec.encounter_id.display_name})"
            rec.display_name = title

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Note Number must be unique per company.',
    )
