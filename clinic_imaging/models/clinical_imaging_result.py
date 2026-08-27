# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Clinical Imaging Result (header)
# =============================================================================
class ClinicalImagingResult(models.Model):
    """
    Structured result/report for a clinical imaging record.

    Key goals:
    - Support draft → preliminary → final (signed) → amended lifecycles.
    - Keep strong links to the core imaging record and patient context.
    - Allow structured content (technique, findings, impression, recommendations).
    - Store quality/dose info and reference key images.
    - Integrate with Portal, Activities, Billing (indirect via imaging), and QWeb reports.
    """
    _name = "clinical.imaging.result"
    _description = "Clinical Imaging Result"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Result Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence when created.",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the result is archived from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        required=True,
        ondelete="cascade",
        index=True,
        help="The imaging record that this result/report belongs to.",
        tracking=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="imaging_id.patient_id",
        store=True,
        readonly=True,
        help="Patient (readonly, propagated from the imaging record).",
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True,
        readonly=True,
        help="Appointment context (readonly, from imaging).",
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Clinical Encounter",
        related="imaging_id.encounter_id",
        store=True,
        readonly=True,
        help="Encounter context (readonly, from imaging).",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True,
        readonly=True,
        help="Treatment plan context (readonly, from imaging).",
    )
    # TUNGGU Addon ACTIVE
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True,
        readonly=True,
        help="Procedure session context (readonly, from imaging).",
    )
    prescription_order_id = fields.Many2one(
        "clinic.emar.order",
        string="Prescription/Order (eMAR)",
        related="imaging_id.prescription_order_id",
        store=True,
        readonly=True,
        help="Prescription/order context (readonly, from imaging).",
    )
    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        related="imaging_id.consent_id",
        store=True,
        readonly=True,
        help="Consent record (readonly, from imaging).",
    )

    # -------------------------------------------------------------------------
    # Authors & Sign-off
    # -------------------------------------------------------------------------
    author_doctor_id = fields.Many2one(
        "hr.employee",
        string="Authoring Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor (e.g., radiologist) who authored this result.",
        tracking=True,
    )
    co_signer_id = fields.Many2one(
        "hr.employee",
        string="Co-signer",
        domain=[("is_doctor", "=", True)],
        help="Optional co-signer doctor if double sign-off is required.",
        tracking=True,
    )
    signed_datetime = fields.Datetime(
        string="Signed At",
        help="Datetime when the result was finalized and signed.",
        tracking=True,
    )
    amended_datetime = fields.Datetime(
        string="Amended At",
        help="Datetime when an addendum/amendment was recorded.",
        tracking=True,
    )
    version = fields.Integer(
        string="Version",
        default=1,
        help="Monotonic version number: 1 for first final, increments on amendments.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Result Lifecycle
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("preliminary", "Preliminary"),
            ("final", "Final (Signed)"),
            ("amended", "Amended"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the imaging result.",
    )
    result_datetime = fields.Datetime(
        string="Result Datetime",
        default=fields.Datetime.now,
        help="Datetime when the result content was completed.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Structured Content
    # -------------------------------------------------------------------------
    technique = fields.Text(
        string="Technique / Protocol",
        help="Acquisition technique and protocol details.",
        tracking=True,
    )
    comparison = fields.Text(
        string="Comparison",
        help="Comparison to prior studies (dates, modalities, findings).",
        tracking=True,
    )
    findings = fields.Text(
        string="Findings",
        help="Detailed findings and observations.",
        tracking=True,
    )
    impression = fields.Text(
        string="Impression",
        help="Concise diagnostic impression / conclusion.",
        tracking=True,
    )
    recommendations = fields.Text(
        string="Recommendations",
        help="Clinical recommendations or next steps.",
        tracking=True,
    )

    # External structured links (defined in other files)
    finding_ids = fields.Many2many(
        "clinical.imaging.finding",
        "clinical_imaging_result_finding_rel",
        "result_id",
        "finding_id",
        string="Structured Findings",
        help="Linked structured findings (lesions, measurements, categorizations).",
    )
    finding_count = fields.Integer(
        string="Finding Count",
        compute="_compute_finding_count",
        store=False,
    )

    # Key Images (optional; defined in clinical_imaging_image.py)
    key_image_ids = fields.Many2many(
        "clinical.imaging.image",
        "clinical_imaging_result_key_image_rel",
        "result_id",
        "image_id",
        string="Key Images",
        help="Representative images bookmarked for this result.",
    )
    key_image_count = fields.Integer(
        string="Key Image Count",
        compute="_compute_key_image_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Quality & Dose
    # -------------------------------------------------------------------------
    quality_score = fields.Selection(
        [
            ("0", "0 - Uninterpretable"),
            ("1", "1 - Poor"),
            ("2", "2 - Fair"),
            ("3", "3 - Good"),
            ("4", "4 - Very Good"),
            ("5", "5 - Excellent"),
        ],
        string="Image Quality",
        default="3",
        help="Subjective image quality score for audit and QA.",
        tracking=True,
    )
    quality_notes = fields.Text(
        string="Quality Notes",
        help="Notes about artifacts, positioning, motion, or other quality issues.",
    )
    dose_line_ids = fields.One2many(
        "clinical.imaging.result.dose",
        "result_id",
        string="Dose / Exposure Lines",
        help="Radiation or exposure metrics (e.g., CTDIvol, DLP, DAP, Fluoro Time).",
        copy=True,
    )

    # -------------------------------------------------------------------------
    # Files & Output
    # -------------------------------------------------------------------------
    report_file = fields.Binary(
        string="Rendered Report (PDF)",
        attachment=True,
        help="Optional stored PDF of the rendered report for archival or external sharing.",
    )
    report_filename = fields.Char(
        string="Report File Name",
        help="Filename for the rendered report (PDF).",
    )
    dicom_bundle = fields.Binary(
        string="DICOM Bundle (ZIP)",
        attachment=True,
        help="Optional ZIP archive of related DICOM exports or secondary captures.",
    )
    dicom_bundle_filename = fields.Char(
        string="DICOM Bundle Name",
        help="Filename for the DICOM bundle ZIP.",
    )
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Portal & Privacy
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this result on the portal (subject to rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("restricted", "Restricted"),
            ("high", "Highly Restricted"),
        ],
        string="Privacy Level",
        default="normal",
        help="Controls how widely accessible the result is to staff and on the portal.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Report Template (optional integration with clinical_imaging_report.py)
    # -------------------------------------------------------------------------
    report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Report Template",
        help="Optional template to render this result.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    def _compute_finding_count(self):
        for rec in self:
            rec.finding_count = len(rec.finding_ids)

    def _compute_key_image_count(self):
        for rec in self:
            rec.key_image_count = len(rec.key_image_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_id")
    def _onchange_imaging_id_defaults(self):
        """Prefill author from imaging's responsible doctor and propagate patient."""
        for rec in self:
            if rec.imaging_id and not rec.author_doctor_id:
                if rec.imaging_id.doctor_id:
                    rec.author_doctor_id = rec.imaging_id.doctor_id.id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("patient_id", "imaging_id")
    def _check_patient_matches_imaging(self):
        for rec in self:
            if rec.imaging_id and rec.patient_id and rec.imaging_id.patient_id != rec.patient_id:
                raise ValidationError(_("Patient on Result must match the Imaging's patient."))

    @api.constrains("state", "impression", "author_doctor_id")
    def _check_required_on_finalize(self):
        for rec in self:
            if rec.state in ("final", "amended"):
                if not rec.impression and not rec.findings:
                    raise ValidationError(_("Please fill at least Findings or Impression before finalizing."))
                if not rec.author_doctor_id:
                    raise ValidationError(_("Authoring Doctor is required for final/amended results."))

    @api.constrains("quality_score")
    def _check_quality_score_range(self):
        for rec in self:
            if rec.quality_score and rec.quality_score not in ("0", "1", "2", "3", "4", "5"):
                raise ValidationError(_("Invalid Image Quality score."))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.result") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe author/co-signer to chatter
        for rec in records:
            partner_ids = []
            for emp in (rec.author_doctor_id, rec.co_signer_id):
                if emp and emp.work_contact_id:
                    partner_ids.append(emp.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        # Prevent company change after creation
        if "company_id" in vals:
            for rec in self:
                if rec.company_id.id != vals["company_id"]:
                    raise UserError(_("You cannot change Company on a result."))
        return super().write(vals)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("version", 1)
        default.setdefault("signed_datetime", False)
        default.setdefault("amended_datetime", False)
        default.setdefault("portal_published", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_set_preliminary(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft results can be set to Preliminary."))
            rec.state = "preliminary"
            rec.message_post(body=_("Result set to Preliminary."))

    def action_finalize_and_sign(self):
        for rec in self:
            if rec.state not in ("draft", "preliminary"):
                raise UserError(_("Only Draft/Preliminary results can be finalized."))
            if not rec.author_doctor_id:
                raise UserError(_("Please set the Authoring Doctor before finalizing."))
            if not rec.impression and not rec.findings:
                raise UserError(_("Please provide Findings or Impression before finalizing."))
            if not rec.signed_datetime:
                rec.signed_datetime = fields.Datetime.now()
            rec.state = "final"
            rec.version = max(1, rec.version or 1)
            rec.message_post(body=_("Result finalized and signed."))

    def action_amend(self, addendum_text=None):
        for rec in self:
            if rec.state not in ("final", "amended"):
                raise UserError(_("Only Final/Amended results can be amended again."))
            rec.state = "amended"
            rec.version = (rec.version or 1) + 1
            rec.amended_datetime = fields.Datetime.now()
            body = _("Result amended. Version: %s") % rec.version
            if addendum_text:
                # Append the addendum text to recommendations by default
                rec.recommendations = (rec.recommendations or "") + ("\n" if rec.recommendations else "") + addendum_text
                body += " " + _("Addendum added.")
            rec.message_post(body=body)

    def action_cancel(self):
        for rec in self:
            if rec.state == "final" and rec.imaging_id and rec.imaging_id.invoice_id and rec.imaging_id.invoice_id.state == "posted":
                raise UserError(_("Final results linked to billed imaging cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body=_("Result cancelled."))

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    # -------------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------------
    def action_print_report(self):
        """
        Render the QWeb PDF. Requires report/action XML IDs:
          - clinic_imaging.report_clinical_imaging_result (ir.actions.report)
        """
        self.ensure_one()
        report = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
        if not report:
            raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
        return report.report_action(self)

    def action_send_result_email(self):
        """
        Send the result via email using a Mail Template, if configured:
          - clinic_imaging.mail_template_clinical_imaging_result
        """
        self.ensure_one()
        template = self.env.ref("clinic_imaging.mail_template_clinical_imaging_result", raise_if_not_found=False)
        if not template:
            raise UserError(_("Mail template 'clinic_imaging.mail_template_clinical_imaging_result' not found."))
        return template.send_mail(self.id, force_send=True)

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
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

    @api.depends("name", "imaging_id", "patient_id", "state")
    def _compute_display_name(self):
        for rec in self:
            display = rec.name or _("Result")
            if rec.imaging_id:
                display = f"{display} - {rec.imaging_id.display_name}"
            if rec.patient_id:
                display = f"{display} - {rec.patient_id.display_name}"
            if rec.state:
                display = f"{display} [{rec.state}]"
            rec.display_name = display

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Result Number must be unique per company.',
    )


# =============================================================================
# Dose / Exposure lines (child)
# =============================================================================
class ClinicalImagingResultDose(models.Model):
    """
    Radiation/exposure metrics captured for the result.
    Not all modalities use all fields (e.g., CT uses CTDIvol/DLP).
    """
    _name = "clinical.imaging.result.dose"
    _description = "Clinical Imaging Result Dose/Exposure"
    _order = "sequence, id"

    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Result",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    metric = fields.Selection(
        [
            ("ctdi_vol", "CTDIvol (mGy)"),
            ("dlp", "DLP (mGy·cm)"),
            ("dap", "Dose Area Product (Gy·cm²)"),
            ("fluoro_time", "Fluoroscopy Time (min)"),
            ("exposure", "Exposure (mAs/kVp)"),
            ("other", "Other"),
        ],
        string="Metric",
        required=True,
        help="Dose/exposure metric type.",
    )
    value = fields.Float(
        string="Value",
        required=True,
        help="Numeric value for the metric.",
    )
    unit = fields.Char(
        string="Unit",
        help="Unit override if 'Other' metric or custom unit.",
    )
    series_ref = fields.Char(
        string="Series Reference",
        help="Optional series identifier/reference within the study.",
    )
    note = fields.Char(
        string="Notes",
        help="Optional short note/remark for this metric.",
    )

    @api.constrains("value")
    def _check_value_non_negative(self):
        for rec in self:
            if rec.value is not None and rec.value < 0.0:
                raise ValidationError(_("Dose/Exposure value must be non-negative."))


# =============================================================================
# Optional: Measurements table (child)
# =============================================================================
class ClinicalImagingResultMeasure(models.Model):
    """
    Generic measurement rows (e.g., lesion sizes, organ dimensions, indices).
    For specialized measurements, consider dedicated models in future expansions.
    """
    _name = "clinical.imaging.result.measure"
    _description = "Clinical Imaging Result Measurement"
    _order = "sequence, id"

    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Result",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    name = fields.Char(
        string="Measurement Name",
        required=True,
        help="Short title for the measurement (e.g., 'Lesion A long-axis').",
    )
    region = fields.Char(
        string="Region",
        help="Anatomical region or description (e.g., 'Right lobe liver').",
    )
    method = fields.Char(
        string="Method",
        help="Measurement method/protocol (e.g., 'RECIST 1.1', 'Axial plane').",
    )
    value = fields.Float(
        string="Value",
        help="Measured value (numeric).",
    )
    unit = fields.Char(
        string="Unit",
        help="Unit of the measured value (e.g., 'mm', 'cm', 'HU').",
    )
    note = fields.Char(
        string="Notes",
        help="Optional remark about the measurement.",
    )

    @api.constrains("value")
    def _check_value_not_nan(self):
        for rec in self:
            # No NaN check needed explicitly in Odoo, but ensure not absurd.
            if rec.value is not None and rec.value < 0 and rec.unit in ("mm", "cm"):
                # Negative length is usually invalid; allow negatives for HU, etc.
                raise ValidationError(_("Length/size measurements should not be negative."))


# =============================================================================
# Hooks: keep imaging header aware of latest final result (optional convenience)
# =============================================================================
class ClinicalImaging(models.Model):
    _inherit = "clinical.imaging"

    latest_result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Latest Result",
        compute="_compute_latest_result",
        store=False,
        help="Convenience link to the most recent final/amended result for quick access.",
    )
    result_count = fields.Integer(
        string="Result Count",
        compute="_compute_result_stats",
        store=False,
    )

    def _compute_result_stats(self):
        for rec in self:
            rec.result_count = self.env["clinical.imaging.result"].search_count([("imaging_id", "=", rec.id)])

    def _compute_latest_result(self):
        for rec in self:
            latest = self.env["clinical.imaging.result"].search(
                [("imaging_id", "=", rec.id), ("state", "in", ["final", "amended"])],
                order="signed_datetime desc, write_date desc, id desc",
                limit=1,
            )
            rec.latest_result_id = latest.id if latest else False

    def action_open_results(self):
        self.ensure_one()
        return {
            "name": _("Imaging Results"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.result",
            "view_mode": "list,form,kanban",
            "domain": [("imaging_id", "=", self.id)],
            "target": "current",
            "context": {"default_imaging_id": self.id},
        }
