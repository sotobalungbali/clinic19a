# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# TAGS - For classifying imaging types (e.g., "Musculoskeletal", "Cardiac")
# =============================================================================
class ClinicalImagingTypeTag(models.Model):
    _name = "clinical.imaging.type.tag"
    _description = "Clinical Imaging Type Tag"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Tag Name", required=True, translate=False)
    color = fields.Integer(string="Color Index", help="Color index for kanban/list chips.")
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company",
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Imaging Type Tag must be unique per company.',
    )


# =============================================================================
# MASTER - Clinical Imaging Type
# =============================================================================
class ClinicalImagingType(models.Model):
    """
    Master data for clinical imaging types (XR/CT/MR/US, etc.).
    Drives default billing, scheduling, device preference, consent, and reporting.
    """
    _name = "clinical.imaging.type"
    _description = "Clinical Imaging Type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name", required=True, tracking=True,
        help="Display name of the imaging type (e.g., 'Chest X-Ray PA', 'Brain MRI with Contrast')."
    )
    code = fields.Char(
        string="Code", tracking=True, index=True,
        help="Short code for the imaging type (e.g., XR-CH-PA, CT-ABD, MR-BRAIN-CE)."
    )
    sequence = fields.Integer(string="Sequence", default=10,
                              help="Ordering helper in lists and menus.")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
    modality = fields.Selection(
        [
            ("XR", "X-Ray"),
            ("CT", "CT"),
            ("MR", "MRI"),
            ("US", "Ultrasound"),
            ("DX", "Digital Radiography"),
            ("MG", "Mammography"),
            ("NM", "Nuclear Medicine"),
            ("OT", "Other"),
        ],
        string="Modality", required=True, tracking=True,
        help="Primary modality category for this imaging type."
    )
    category = fields.Selection(
        [
            ("diagnostic", "Diagnostic"),
            ("interventional", "Interventional"),
            ("screening", "Screening"),
            ("therapy", "Therapeutic/Procedure Guidance"),
        ],
        string="Category", default="diagnostic", tracking=True,
        help="Clinical intent category for this imaging type."
    )
    tag_ids = fields.Many2many(
        "clinical.imaging.type.tag",
        "clinical_imaging_type_tag_rel",
        "imaging_type_id", "tag_id",
        string="Tags",
        help="Optional tags to classify and search imaging types."
    )
    description = fields.Text(string="Description",
                              help="Additional notes about indication, protocol variants, caveats.")

    # -------------------------------------------------------------------------
    # Billing Defaults (integration with accounting/product)
    # -------------------------------------------------------------------------
    default_product_id = fields.Many2one(
        "product.product",
        string="Default Billable Service",
        domain=[("type", "=", "service")],
        help="Default service product used when creating requests or imaging records."
    )
    default_price_unit = fields.Monetary(
        string="Default Unit Price",
        currency_field="currency_id",
        help="Suggested price if no product is selected; falls back to product list price."
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda self: self.env.company.currency_id.id
    )
    default_tax_ids = fields.Many2many(
        "account.tax",
        "clinical_imaging_type_tax_rel",
        "imaging_type_id", "tax_id",
        string="Default Taxes",
        help="Default taxes; will be mapped by fiscal position on the patient."
    )
    is_billable = fields.Boolean(
        string="Billable by Default", default=True,
        help="If checked, generated imaging is billable by default."
    )

    # -------------------------------------------------------------------------
    # Scheduling Defaults
    # -------------------------------------------------------------------------
    default_duration_minutes = fields.Integer(
        string="Default Duration (min)", tracking=True,
        help="Typical duration to perform this imaging; used for scheduling/SLA."
    )
    default_device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Preferred Device",
        help="Default/primary device to allocate when available."
    )
    device_ids = fields.Many2many(
        "clinical.imaging.device",
        "clinical_imaging_type_device_rel",
        "imaging_type_id", "device_id",
        string="Allowed Devices",
        help="List of devices considered suitable for this imaging type."
    )

    # -------------------------------------------------------------------------
    # Consent & Safety
    # -------------------------------------------------------------------------
    require_consent = fields.Boolean(
        string="Consent Required", default=False,
        help="If checked, a patient consent is required before acquisition."
    )
    consent_note = fields.Text(
        string="Consent Note",
        help="Instructions/policy notes for consent (template mapping handled by consent module)."
    )
    safety_risk = fields.Selection(
        [
            ("none", "None"),
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        string="Safety Risk Level", default="low", tracking=True,
        help="Generalized risk for triage and scheduling allocation."
    )
    require_pregnancy_check = fields.Boolean(
        string="Pregnancy Check Required", default=False,
        help="If checked, pregnancy status must be verified per policy before acquisition."
    )
    require_creatinine_check = fields.Boolean(
        string="Creatinine/eGFR Required", default=False,
        help="If checked, recent renal function labs required (contrast or specific modalities)."
    )
    creatinine_max_value = fields.Float(
        string="Max Creatinine (mg/dL)",
        help="If set, creatinine must be ≤ this value; used for validation prompts."
    )

    # -------------------------------------------------------------------------
    # Contrast / Medication Policies
    # -------------------------------------------------------------------------
    contrast_required = fields.Boolean(
        string="Contrast Required", default=False,
        help="If checked, contrast administration is required by default."
    )
    contrast_agent_product_id = fields.Many2one(
        "product.product", string="Contrast Agent",
        domain=[("type", "in", ["consu"])],
        help="Default contrast agent product (stockable or consumable)."
    )
    contrast_dose_mg_per_kg = fields.Float(
        string="Contrast Dose (mg/kg)",
        help="Suggested dose per kg body weight; final dose calculated at acquisition."
    )
    sedation_required = fields.Boolean(
        string="Sedation Required", default=False,
        help="If checked, sedation/anxiolysis is required by default (e.g., pediatric MRI)."
    )
    fasting_hours = fields.Integer(
        string="Fasting Hours",
        help="Recommended fasting hours prior to the procedure (if applicable)."
    )

    # -------------------------------------------------------------------------
    # Reporting Defaults (optional)
    # -------------------------------------------------------------------------
    report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Default Report Template",
        help="Optional default report template for results of this imaging type."
    )

    # -------------------------------------------------------------------------
    # Statistics / Helpers
    # -------------------------------------------------------------------------
    protocol_step_count = fields.Integer(
        string="Protocol Steps",
        compute="_compute_counts", store=False
    )
    prep_count = fields.Integer(
        string="Preparation Items",
        compute="_compute_counts", store=False
    )
    contra_count = fields.Integer(
        string="Contraindications",
        compute="_compute_counts", store=False
    )
    device_count = fields.Integer(
        string="Devices",
        compute="_compute_counts", store=False
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        for rec in self:
            rec.protocol_step_count = self.env["clinical.imaging.protocol"].search_count([("imaging_type_id", "=", rec.id)])
            rec.prep_count = self.env["clinical.imaging.type.prep"].search_count([("imaging_type_id", "=", rec.id)])
            rec.contra_count = self.env["clinical.imaging.type.contra"].search_count([("imaging_type_id", "=", rec.id)])
            rec.device_count = len(rec.device_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("default_product_id")
    def _onchange_default_product_id(self):
        for rec in self:
            if rec.default_product_id:
                if not rec.default_price_unit or rec.default_price_unit == 0.0:
                    rec.default_price_unit = rec.default_product_id.lst_price
                # Suggest taxes from product
                taxes = rec.default_product_id.taxes_id
                rec.default_tax_ids = [(6, 0, taxes.ids)] if taxes else [(6, 0, [])]

    @api.onchange("modality", "default_device_id")
    def _onchange_device_modality_guard(self):
        """
        Soft guard: if preferred device has different modality, warn user.
        Hard checks are enforced in constraints.
        """
        for rec in self:
            if rec.modality and rec.default_device_id and rec.default_device_id.modality and \
               rec.default_device_id.modality != rec.modality:
                return {
                    "warning": {
                        "title": _("Modality Mismatch"),
                        "message": _(
                            "Preferred Device modality (%s) differs from Imaging Type modality (%s). "
                            "Please review your selection."
                        ) % (rec.default_device_id.modality, rec.modality)
                    }
                }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code_upper(self):
        for rec in self:
            if rec.code and rec.code.strip() != rec.code.strip().upper():
                # Normalize silently instead of blocking
                rec.code = rec.code.strip().upper()

    @api.constrains("fasting_hours")
    def _check_fasting_non_negative(self):
        for rec in self:
            if rec.fasting_hours is not None and rec.fasting_hours < 0:
                raise ValidationError(_("Fasting Hours must be greater than or equal to zero."))

    @api.constrains("contrast_dose_mg_per_kg")
    def _check_contrast_dose_positive(self):
        for rec in self:
            if rec.contrast_required and (rec.contrast_dose_mg_per_kg or 0.0) <= 0.0:
                raise ValidationError(_("Contrast dose (mg/kg) must be positive when contrast is required."))

    @api.constrains("default_device_id", "modality")
    def _check_device_modality(self):
        for rec in self:
            if rec.default_device_id and rec.default_device_id.modality and rec.modality:
                if rec.default_device_id.modality != rec.modality:
                    raise ValidationError(_("Preferred Device modality must match Imaging Type modality."))

    @api.constrains("require_creatinine_check", "creatinine_max_value")
    def _check_creatinine_threshold(self):
        for rec in self:
            if rec.require_creatinine_check and (rec.creatinine_max_value or 0.0) <= 0.0:
                raise ValidationError(_("Max Creatinine must be set to a positive value when renal check is required."))

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.depends("name", "code", "modality")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _("Imaging Type")]
            if rec.code:
                parts.append("[%s]" % rec.code)
            if rec.modality:
                parts.append("(%s)" % rec.modality)
            rec.display_name = " ".join(parts)

    def action_open_devices(self):
        self.ensure_one()
        return {
            "name": _("Allowed Devices"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device",
            "view_mode": "list,form",
            "domain": [("id", "in", self.device_ids.ids)],
            "target": "current",
        }

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Imaging Type code must be unique per company.',
    )


# =============================================================================
# PROTOCOL - Step-by-step acquisition guide per imaging type
# =============================================================================
class ClinicalImagingProtocol(models.Model):
    _name = "clinical.imaging.protocol"
    _description = "Clinical Imaging Protocol"
    _order = "imaging_type_id, sequence, id"
    _check_company_auto = True

    imaging_type_id = fields.Many2one(
        "clinical.imaging.type", string="Imaging Type",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="imaging_type_id.company_id", store=True, readonly=True
    )
    sequence = fields.Integer(string="Sequence", default=10)
    title = fields.Char(string="Step Title", required=True,
                        help="Short title of the protocol step (e.g., 'Positioning', 'Scout/Localizer').")
    instruction = fields.Text(
        string="Detailed Instruction", required=True,
        help="Detailed instructions for the technician/operator."
    )
    expected_duration_minutes = fields.Integer(
        string="Expected Duration (min)",
        help="Expected duration for this specific step."
    )
    requires_contrast = fields.Boolean(
        string="Requires Contrast", default=False,
        help="Check if this step includes contrast administration."
    )
    requires_sedation = fields.Boolean(
        string="Requires Sedation", default=False,
        help="Check if this step requires sedation or anxiolysis."
    )
    note = fields.Char(string="Notes")

    @api.constrains("expected_duration_minutes")
    def _check_step_duration_non_negative(self):
        for rec in self:
            if rec.expected_duration_minutes is not None and rec.expected_duration_minutes < 0:
                raise ValidationError(_("Expected duration must be non-negative."))


# =============================================================================
# PREPARATION - Pre-procedure preparation items per imaging type
# =============================================================================
class ClinicalImagingTypePrep(models.Model):
    _name = "clinical.imaging.type.prep"
    _description = "Clinical Imaging Type Preparation"
    _order = "imaging_type_id, sequence, id"
    _check_company_auto = True

    imaging_type_id = fields.Many2one(
        "clinical.imaging.type", string="Imaging Type",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="imaging_type_id.company_id", store=True, readonly=True
    )
    sequence = fields.Integer(string="Sequence", default=10)
    title = fields.Char(string="Preparation Title", required=True,
                        help="Short title (e.g., 'Fasting', 'Remove metallic objects').")
    instruction = fields.Text(
        string="Preparation Instruction", required=True,
        help="Plain-language instruction for patients or staff."
    )
    responsible = fields.Selection(
        [
            ("patient", "Patient"),
            ("staff", "Staff"),
            ("doctor", "Doctor"),
        ],
        string="Responsible", default="patient",
        help="Who is responsible to perform/ensure this preparation."
    )
    min_hours_before = fields.Float(
        string="Min Hours Before",
        help="Minimum hours before procedure when this preparation must be completed."
    )
    note = fields.Char(string="Notes")

    @api.constrains("min_hours_before")
    def _check_min_hours_before_non_negative(self):
        for rec in self:
            if rec.min_hours_before is not None and rec.min_hours_before < 0.0:
                raise ValidationError(_("Minimal hours before must be non-negative."))


# =============================================================================
# CONTRAINDICATIONS - Safety checklist per imaging type
# =============================================================================
class ClinicalImagingTypeContra(models.Model):
    _name = "clinical.imaging.type.contra"
    _description = "Clinical Imaging Type Contraindication"
    _order = "imaging_type_id, severity desc, name"
    _check_company_auto = True

    imaging_type_id = fields.Many2one(
        "clinical.imaging.type", string="Imaging Type",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="imaging_type_id.company_id", store=True, readonly=True
    )
    name = fields.Char(
        string="Contraindication", required=True,
        help="Short title (e.g., 'Pacemaker', 'Severe renal impairment', 'Pregnancy')."
    )
    severity = fields.Selection(
        [
            ("info", "Info / Caution"),
            ("relative", "Relative"),
            ("absolute", "Absolute"),
        ],
        string="Severity", default="relative",
        help="Severity level for this contraindication."
    )
    guidance = fields.Text(
        string="Guidance",
        help="Guidance on how to proceed (e.g., 'Use non-MR conditional device', 'Delay until postpartum')."
    )
    require_doctor_approval = fields.Boolean(
        string="Requires Doctor Approval", default=False,
        help="If checked, explicit doctor approval is required to proceed."
    )
    require_lab_check = fields.Boolean(
        string="Requires Lab Check", default=False,
        help="If checked, additional lab verification is required before proceeding."
    )
