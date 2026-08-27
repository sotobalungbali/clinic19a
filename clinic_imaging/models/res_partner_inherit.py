# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


# =============================================================================
# res.partner — Imaging extensions (Patient profile + smart buttons)
# =============================================================================
class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # Imaging Identifiers & Care Team
    # -------------------------------------------------------------------------
    pacs_patient_id = fields.Char(
        string="PACS Patient ID",
        help="External Patient ID used by PACS/RIS/VNA (if different from MRN)."
    )
    dicom_patient_id = fields.Char(
        string="DICOM Patient ID",
        help="DICOM PatientID tag used during acquisition, if enforced."
    )
    primary_doctor_id = fields.Many2one(
        "hr.employee",
        string="Primary Doctor",
        domain=[("is_doctor", "=", True)],
        help="Patient's primary physician in ClinicOne."
    )

    # -------------------------------------------------------------------------
    # Clinical Safety (Imaging)
    # -------------------------------------------------------------------------
    has_metal_implants = fields.Boolean(
        string="Has Metal Implants",
        help="Patient has metallic implants (e.g., orthopedic hardware)."
    )
    implant_description = fields.Char(
        string="Implant Description",
        help="Short description of implant(s), location, or model."
    )
    has_pacemaker = fields.Boolean(
        string="Has Pacemaker/ICD",
        help="Patient has an implanted pacemaker or defibrillator."
    )
    has_cochlear_implant = fields.Boolean(
        string="Has Cochlear Implant",
        help="Patient has cochlear or other otologic implant."
    )
    pregnancy_status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("no", "Not Pregnant"),
            ("yes", "Pregnant"),
            ("na", "Not Applicable"),
        ],
        string="Pregnancy Status",
        default="unknown",
        help="Relevant for ionizing radiation and MRI safety screening."
    )
    last_menstruation_date = fields.Date(
        string="Last Menstruation Date",
        help="Optional LMP date for pregnancy assessment."
    )

    contrast_allergy = fields.Boolean(
        string="Contrast Allergy",
        help="Known allergy to contrast media (iodinated or gadolinium)."
    )
    contrast_allergy_severity = fields.Selection(
        [
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("anaphylaxis", "Anaphylaxis"),
        ],
        string="Allergy Severity"
    )
    contrast_allergy_notes = fields.Char(
        string="Allergy Notes",
        help="Short notes about the contrast allergy history."
    )
    contrast_premed_required = fields.Boolean(
        string="Premedication Required",
        help="Premedication protocol should be applied before contrast study."
    )
    contrast_premed_protocol = fields.Text(
        string="Premedication Protocol",
        help="Suggested premedication regimen (e.g., steroids/antihistamines)."
    )

    # Renal function (for contrast risk)
    egfr_value = fields.Float(
        string="eGFR (mL/min/1.73m²)",
        help="Latest estimated glomerular filtration rate."
    )
    egfr_date = fields.Date(string="eGFR Date")
    egfr_method = fields.Selection(
        [("ckd_epi", "CKD-EPI"), ("mdrd", "MDRD"), ("other", "Other")],
        string="eGFR Method"
    )
    renal_risk = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        string="Renal Risk",
        compute="_compute_renal_risk",
        store=True,
        help="Automated risk estimation based on eGFR and recency."
    )
    metformin_use = fields.Boolean(
        string="On Metformin",
        help="Patient currently uses metformin (consider hold around iodinated contrast)."
    )
    metformin_instructions = fields.Text(
        string="Metformin Hold Instructions",
        help="Instructions for metformin withholding if applicable."
    )

    # Sedation / ASA (high-level)
    asa_class = fields.Selection(
        [
            ("I", "ASA I"),
            ("II", "ASA II"),
            ("III", "ASA III"),
            ("IV", "ASA IV"),
            ("V", "ASA V"),
            ("VI", "ASA VI"),
        ],
        string="ASA Class",
        help="American Society of Anesthesiologists physical status classification."
    )
    sedation_contraindications = fields.Text(
        string="Sedation Contraindications",
        help="Known issues that increase sedation risk."
    )

    # -------------------------------------------------------------------------
    # Anthropometrics (for imaging limits, dose tracking, coil/table limits)
    # -------------------------------------------------------------------------
    height_cm = fields.Float(string="Height (cm)")
    weight_kg = fields.Float(string="Weight (kg)")
    bmi = fields.Float(
        string="BMI",
        compute="_compute_bmi",
        store=True,
        help="Body Mass Index computed from height and weight."
    )

    # -------------------------------------------------------------------------
    # Privacy / Portal preferences (specific to Imaging)
    # -------------------------------------------------------------------------
    imaging_portal_opt_out = fields.Boolean(
        string="Opt-out of Imaging Portal",
        help="If checked, imaging results/key images will not be shown on the patient portal."
    )
    share_images_on_portal = fields.Boolean(
        string="Share Images on Portal",
        default=True,
        help="Allow key images to be visible to the patient on the portal."
    )

    # -------------------------------------------------------------------------
    # KPI Counters (smart buttons)
    # -------------------------------------------------------------------------
    imaging_request_count = fields.Integer(
        string="Imaging Requests", compute="_compute_imaging_counts", store=False
    )
    imaging_count = fields.Integer(
        string="Imaging Records", compute="_compute_imaging_counts", store=False
    )
    imaging_result_count = fields.Integer(
        string="Imaging Results", compute="_compute_imaging_counts", store=False
    )
    imaging_study_count = fields.Integer(
        string="Studies", compute="_compute_imaging_counts", store=False
    )
    imaging_series_count = fields.Integer(
        string="Series", compute="_compute_imaging_counts", store=False
    )
    imaging_image_count = fields.Integer(
        string="Images", compute="_compute_imaging_counts", store=False
    )
    imaging_finding_count = fields.Integer(
        string="Findings", compute="_compute_imaging_counts", store=False
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS / COMPUTES / ONCHANGE
    # -------------------------------------------------------------------------
    @api.constrains("egfr_value")
    def _check_egfr_range(self):
        for rec in self:
            if rec.egfr_value is not None and (rec.egfr_value < 0 or rec.egfr_value > 200):
                raise ValidationError(_("eGFR must be in a realistic range (0..200)."))

    @api.constrains("height_cm", "weight_kg")
    def _check_anthro_non_negative(self):
        for rec in self:
            if rec.height_cm is not None and rec.height_cm < 0:
                raise ValidationError(_("Height cannot be negative."))
            if rec.weight_kg is not None and rec.weight_kg < 0:
                raise ValidationError(_("Weight cannot be negative."))

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
            # recency within 365 days
            recent = (rec.egfr_date >= (today - fields.Date.to_date("1970-01-01").replace(year=today.year - 1))) \
                if isinstance(today, date) else True
            # Simple heuristic: <30 high, 30-44 moderate, 45-59 low, >=60 low
            if rec.egfr_value < 30:
                risk = "high"
            elif rec.egfr_value < 45:
                risk = "moderate"
            else:
                risk = "low"
            rec.renal_risk = risk if recent else "unknown"

    @api.onchange("contrast_allergy")
    def _onchange_contrast_allergy(self):
        for rec in self:
            if rec.contrast_allergy and rec.contrast_premed_required is False:
                rec.contrast_premed_required = True

    # -------------------------------------------------------------------------
    # COMPUTE COUNTS
    # -------------------------------------------------------------------------
    def _compute_imaging_counts(self):
        Imaging = self.env["clinical.imaging"].sudo()
        Request = self.env["clinical.imaging.request"].sudo()
        Result = self.env["clinical.imaging.result"].sudo()
        Study = self.env["clinical.imaging.study"].sudo()
        Series = self.env["clinical.imaging.series"].sudo()
        Image = self.env["clinical.imaging.image"].sudo()
        Finding = self.env["clinical.imaging.finding"].sudo()
        for rec in self:
            # If partner is not a patient (from clinic_patient), still compute safely
            domain_patient = [("patient_id", "=", rec.id)]
            rec.imaging_count = Imaging.search_count(domain_patient)
            rec.imaging_request_count = Request.search_count(domain_patient)
            rec.imaging_result_count = Result.search_count(domain_patient)
            rec.imaging_study_count = Study.search_count(domain_patient)
            rec.imaging_series_count = Series.search_count(domain_patient)
            rec.imaging_image_count = Image.search_count(domain_patient)
            rec.imaging_finding_count = Finding.search_count(domain_patient)

    # -------------------------------------------------------------------------
    # NAVIGATION ACTIONS (Smart Buttons)
    # -------------------------------------------------------------------------
    def action_open_imaging_requests(self):
        self.ensure_one()
        return {
            "name": _("Imaging Requests"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
            "context": {"default_patient_id": self.id},
        }

    def action_open_imaging(self):
        self.ensure_one()
        return {
            "name": _("Imaging Records"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
            "context": {"default_patient_id": self.id},
        }

    def action_open_imaging_results(self):
        self.ensure_one()
        return {
            "name": _("Imaging Results"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.result",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_studies(self):
        self.ensure_one()
        return {
            "name": _("Studies"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.study",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_series(self):
        self.ensure_one()
        return {
            "name": _("Series"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.series",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_images(self):
        self.ensure_one()
        return {
            "name": _("Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_new_imaging_request(self):
        """Quick create a new Imaging Request for this patient."""
        self.ensure_one()
        return {
            "name": _("New Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": self.id,
                "default_referring_partner_id": self.id,
                "default_primary_doctor_id": self.primary_doctor_id.id if self.primary_doctor_id else False,
            },
        }

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _pacs_patient_id_company_unique = models.Constraint(
        'unique(pacs_patient_id, company_id)',
        'PACS Patient ID must be unique per company.',
    )
    _dicom_patient_id_company_unique = models.Constraint(
        'unique(dicom_patient_id, company_id)',
        'DICOM Patient ID must be unique per company.',
    )
