# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re
import json


# =============================================================================
# Tags for Findings (classification)
# =============================================================================
class ClinicalImagingFindingTag(models.Model):
    _name = "clinical.imaging.finding.tag"
    _description = "Clinical Imaging Finding Tag"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Tag Name", required=True)
    color = fields.Integer(string="Color Index", help="Color index for kanban/list chips.")
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Finding Tag must be unique per company.',
    )


# =============================================================================
# Clinical Imaging Finding (structured lesion/observation)
# =============================================================================
class ClinicalImagingFinding(models.Model):
    """
    Structured imaging finding (e.g., pulmonary nodule, hepatic lesion, fracture).
    Links to Imaging/Study/Series/Image for provenance, and to Result for reporting.

    Key features:
      - Standardized categorization (benign/suspicious), risk scores (BI-RADS, LI-RADS, PI-RADS, Lung-RADS)
      - Location & laterality, organ/segment
      - Size measurements (long/short axis) + optional detailed measure lines
      - Evolution/trend tracking vs prior (stable/increase/decrease/resolved)
      - Portal visibility with privacy levels
      - Many2many linkage to Results (bidirectional with clinical.imaging.result.finding_ids)
    """
    _name = "clinical.imaging.finding"
    _description = "Clinical Imaging Finding"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Finding Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence.",
        index=True,
        tracking=True,
    )
    display_name = fields.Char(
        string="Title",
        required=True,
        help="Short title for the finding (e.g., 'Right upper lobe nodule').",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )
    active = fields.Boolean(string="Active", default=True)

    # -------------------------------------------------------------------------
    # Context Links (propagated from imaging/study/series/image)
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        required=False,
        index=True,
        help="Imaging record that this finding is associated with.",
        tracking=True,
    )
    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        index=True,
        help="Study context of this finding (if known).",
    )
    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        index=True,
        help="Series context of this finding (if known).",
    )
    image_ids = fields.Many2many(
        "clinical.imaging.image",
        "clinical_imaging_finding_image_rel",
        "finding_id",
        "image_id",
        string="Related Images",
        help="Reference images for this finding (key slices/frames).",
    )
    annotation_ids = fields.Many2many(
        "clinical.imaging.image.annotation",
        "clinical_imaging_finding_annotation_rel",
        "finding_id",
        "annotation_id",
        string="Linked Annotations",
        help="Annotations (ROIs/measurements) that define or illustrate this finding.",
    )

    # Propagated care context
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="imaging_id.patient_id",
        store=True,
        readonly=True,
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True,
        readonly=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Clinical Encounter",
        related="imaging_id.encounter_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True,
        readonly=True,
    )
    # TUNGGU addon ACTIVE
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Result Link (bidirectional M2M with clinical.imaging.result)
    # -------------------------------------------------------------------------
    result_ids = fields.Many2many(
        "clinical.imaging.result",
        "clinical_imaging_result_finding_rel",
        "finding_id",
        "result_id",
        string="Results",
        help="Results that include this finding.",
    )
    result_count = fields.Integer(
        string="Result Count",
        compute="_compute_counts",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Classification & Risk
    # -------------------------------------------------------------------------
    category = fields.Selection(
        [
            ("benign", "Benign"),
            ("likely_benign", "Likely Benign"),
            ("indeterminate", "Indeterminate"),
            ("suspicious", "Suspicious"),
            ("malignant", "Malignant"),
        ],
        string="Diagnostic Category",
        default="indeterminate",
        help="Overall diagnostic category for the finding.",
        tracking=True,
    )
    tags_ids = fields.Many2many(
        "clinical.imaging.finding.tag",
        "clinical_imaging_finding_tag_rel",
        "finding_id",
        "tag_id",
        string="Tags",
        help="Classification tags for this finding.",
    )

    # RADS scoring (optional)
    birads = fields.Selection(
        [(str(i), f"BI-RADS {i}") for i in range(0, 7)],
        string="BI-RADS",
        help="Breast Imaging-Reporting and Data System category.",
    )
    lirads = fields.Selection(
        [(str(i), f"LI-RADS {i}") for i in range(1, 6)] + [("nc", "LI-RADS NC")],
        string="LI-RADS",
        help="Liver Imaging Reporting and Data System category.",
    )
    pirads = fields.Selection(
        [(str(i), f"PI-RADS {i}") for i in range(1, 6)],
        string="PI-RADS",
        help="Prostate Imaging Reporting and Data System category.",
    )
    lungrads = fields.Selection(
        [(str(i), f"Lung-RADS {i}") for i in range(0, 5)] + [("s", "Lung-RADS S")],
        string="Lung-RADS",
        help="Lung CT Screening Reporting and Data System category.",
    )

    # Clinical severity and trend
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Clinical Severity",
        default="moderate",
        help="Severity used for triage and follow-up urgency.",
        tracking=True,
    )
    trend = fields.Selection(
        [
            ("new", "New"),
            ("stable", "Stable"),
            ("increased", "Increased"),
            ("decreased", "Decreased"),
            ("resolved", "Resolved"),
            ("unknown", "Unknown"),
        ],
        string="Evolution vs Prior",
        default="unknown",
        help="Observed evolution when compared with prior studies.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Location & Description
    # -------------------------------------------------------------------------
    body_region = fields.Char(
        string="Body Region",
        help="General region (e.g., 'Chest', 'Abdomen', 'Pelvis').",
    )
    organ = fields.Char(
        string="Organ",
        help="Organ or structure (e.g., 'Liver', 'Left lung').",
    )
    organ_segment = fields.Char(
        string="Organ Segment",
        help="Segment/lobe (e.g., 'Segment VIII', 'Right upper lobe').",
    )
    side = fields.Selection(
        [("left", "Left"), ("right", "Right"), ("midline", "Midline"), ("bilateral", "Bilateral"), ("unknown", "Unknown")],
        string="Side",
        default="unknown",
        help="Laterality/side of the finding.",
    )
    location_notes = fields.Char(string="Location Notes")

    description = fields.Text(
        string="Description",
        help="Narrative description of the finding.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Size / Measurements (quick fields)
    # -------------------------------------------------------------------------
    long_axis_mm = fields.Float(string="Long Axis (mm)", help="Longest diameter in millimeters.")
    short_axis_mm = fields.Float(string="Short Axis (mm)", help="Shortest diameter in millimeters.")
    volume_mm3 = fields.Float(string="Volume (mm³)", help="Estimated volume, if applicable.")
    density_hu = fields.Float(string="Density (HU)", help="CT attenuation (Hounsfield Units).")
    suv_max = fields.Float(string="SUVmax", help="Peak standardized uptake value (PET).")
    suv_mean = fields.Float(string="SUVmean", help="Mean standardized uptake value (PET).")

    # Detailed measurement lines
    measure_ids = fields.One2many(
        "clinical.imaging.finding.measure", "finding_id",
        string="Measurements",
        help="Structured measurement rows linked to this finding.",
        copy=True,
    )
    measure_count = fields.Integer(string="Measurement Count", compute="_compute_counts", store=False)

    # -------------------------------------------------------------------------
    # Coding (optional SNOMED/ICD/Custom)
    # -------------------------------------------------------------------------
    code_system = fields.Selection(
        [
            ("snomed", "SNOMED CT"),
            ("icd10", "ICD-10"),
            ("local", "Local"),
            ("other", "Other"),
        ],
        string="Code System",
        default="local",
        help="Coding system used for the code below.",
    )
    code = fields.Char(string="Code", help="Code value in the selected coding system.")
    code_desc = fields.Char(string="Code Description", help="Description of the coded concept.")

    # -------------------------------------------------------------------------
    # Attachments & Portal
    # -------------------------------------------------------------------------
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this finding on the portal (subject to rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [("normal", "Normal"), ("restricted", "Restricted"), ("high", "Highly Restricted")],
        string="Privacy Level",
        default="normal",
        help="Controls how widely accessible the finding is to staff and on the portal.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # State & Audit
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_review", "In Review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("resolved", "Resolved"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle state of this finding.",
    )
    author_doctor_id = fields.Many2one(
        "hr.employee",
        string="Authoring Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor who documented this finding (e.g., radiologist).",
        tracking=True,
    )
    created_datetime = fields.Datetime(string="Created At", default=fields.Datetime.now)
    verified_datetime = fields.Datetime(string="Verified At")

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        for rec in self:
            rec.result_count = len(rec.result_ids)
            rec.measure_count = len(rec.measure_ids)

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("series_id")
    def _onchange_series_id(self):
        for rec in self:
            if rec.series_id and not rec.study_id:
                rec.study_id = rec.series_id.study_id.id
            if rec.series_id and not rec.imaging_id:
                rec.imaging_id = rec.series_id.study_id.imaging_id.id

    @api.onchange("study_id")
    def _onchange_study_id(self):
        for rec in self:
            if rec.study_id and not rec.imaging_id:
                rec.imaging_id = rec.study_id.imaging_id.id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("long_axis_mm", "short_axis_mm", "volume_mm3", "density_hu", "suv_max", "suv_mean")
    def _check_non_negative_metrics(self):
        for rec in self:
            for fname in ["long_axis_mm", "short_axis_mm", "volume_mm3", "suv_max", "suv_mean"]:
                val = getattr(rec, fname)
                if val is not None and val < 0:
                    raise ValidationError(_("%s cannot be negative.") % fname)
            # density_hu can be negative (e.g., fat), so no check

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.finding") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe doctor
        for rec in records:
            partner_ids = []
            if rec.author_doctor_id and rec.author_doctor_id.work_contact_id:
                partner_ids.append(rec.author_doctor_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("portal_published", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state in ("approved", "resolved", "archived"):
                raise UserError(_("Approved/Resolved/Archived findings cannot be deleted."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_submit_review(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft findings can be submitted for review."))
            rec.state = "in_review"
            rec.message_post(body=_("Finding submitted for review."))

    def action_approve(self):
        for rec in self:
            if rec.state not in ("in_review",):
                raise UserError(_("Only findings In Review can be approved."))
            if not rec.author_doctor_id:
                raise UserError(_("Please set Authoring Doctor before approval."))
            rec.state = "approved"
            rec.verified_datetime = fields.Datetime.now()
            rec.message_post(body=_("Finding approved."))

    def action_reject(self, reason=None):
        for rec in self:
            if rec.state not in ("in_review",):
                raise UserError(_("Only findings In Review can be rejected."))
            rec.state = "rejected"
            rec.message_post(body=_("Finding rejected. %s") % (reason or ""))

    def action_resolve(self, note=None):
        for rec in self:
            if rec.state not in ("approved", "rejected"):
                raise UserError(_("Only Approved or Rejected findings can be resolved."))
            rec.state = "resolved"
            if note:
                rec.message_post(body=_("Finding resolved. %s") % note)
            else:
                rec.message_post(body=_("Finding resolved."))

    def action_archive(self):
        for rec in self:
            if rec.state not in ("resolved", "rejected"):
                raise UserError(_("Only Resolved/Rejected findings can be archived."))
            rec.state = "archived"
            rec.active = False
            rec.message_post(body=_("Finding archived."))

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    # Linking helpers
    def action_add_to_result(self, result_id=None):
        """
        Add this finding to a Result. If result_id not provided, use latest final/amended result.
        """
        Result = self.env["clinical.imaging.result"]
        for rec in self:
            target = False
            if result_id:
                target = Result.browse(result_id).exists()
            elif rec.imaging_id:
                target = Result.search(
                    [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
                    order="signed_datetime desc, write_date desc, id desc",
                    limit=1,
                )
            if not target:
                raise UserError(_("No target Result found to link this finding."))
            rec.result_ids = [(4, target.id)]
            target.message_post(body=_("Finding %s linked to this Result.") % rec.display_name)

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

    # Display

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Finding Number must be unique per company.',
    )


# =============================================================================
# Measurement lines for Findings
# =============================================================================
class ClinicalImagingFindingMeasure(models.Model):
    _name = "clinical.imaging.finding.measure"
    _description = "Clinical Imaging Finding Measurement"
    _order = "finding_id, sequence, id"
    _check_company_auto = True

    finding_id = fields.Many2one(
        "clinical.imaging.finding",
        string="Finding",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="finding_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    name = fields.Char(
        string="Measurement Name",
        required=True,
        help="Short title (e.g., 'Long-axis', 'Short-axis', 'Attenuation').",
    )
    method = fields.Char(
        string="Method",
        help="Measurement protocol/method (e.g., 'RECIST 1.1', 'Axial plane').",
    )
    value = fields.Float(string="Value")
    unit = fields.Char(string="Unit", help="Unit of the measured value (e.g., 'mm', 'cm³', 'HU').")
    related_image_id = fields.Many2one(
        "clinical.imaging.image",
        string="Related Image",
        help="Specific image used for this measurement.",
    )
    related_annotation_id = fields.Many2one(
        "clinical.imaging.image.annotation",
        string="Related Annotation",
        help="Annotation/ROI corresponding to this measurement.",
    )
    note = fields.Char(string="Notes")

    @api.constrains("value")
    def _check_value_not_nan(self):
        for rec in self:
            # Length/area/volume values should be non-negative; allow negatives for HU/CT numbers.
            if rec.unit and any(u in (rec.unit or "").lower() for u in ["mm", "cm", "m", "px", "²", "3", "³"]):
                if rec.value is not None and rec.value < 0:
                    raise ValidationError(_("Measurement value must be non-negative for length/area/volume units."))

# DIPINDAH KE FILE clinical_imaging_kpi.py
# =============================================================================
# Convenience extensions for navigation from other models
# =============================================================================
# class ClinicalImagingResult(models.Model):
#     _inherit = "clinical.imaging.result"

#     def action_open_findings(self):
#         self.ensure_one()
#         return {
#             "name": _("Findings"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.finding",
#             "view_mode": "list,form,kanban",
#             "domain": [("id", "in", self.finding_ids.ids)],
#             "target": "current",
#         }

#     def action_add_existing_finding(self):
#         """Open a chooser to link existing findings for the same imaging."""
#         self.ensure_one()
#         return {
#             "name": _("Add Existing Finding"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.finding",
#             "view_mode": "list,form",
#             "domain": [("imaging_id", "=", self.imaging_id.id)],
#             "target": "current",
#             "context": {"default_imaging_id": self.imaging_id.id},
#         }


class ClinicalImagingStudy(models.Model):
    _inherit = "clinical.imaging.study"

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings (Study)"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("study_id", "=", self.id)],
            "target": "current",
            "context": {"default_study_id": self.id, "default_imaging_id": self.imaging_id.id},
        }


class ClinicalImagingSeries(models.Model):
    _inherit = "clinical.imaging.series"

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings (Series)"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("series_id", "=", self.id)],
            "target": "current",
            "context": {
                "default_series_id": self.id,
                "default_study_id": self.study_id.id,
                "default_imaging_id": self.imaging_id.id,
            },
        }


class ClinicalImaging(models.Model):
    _inherit = "clinical.imaging"

    finding_count = fields.Integer(
        string="Finding Count",
        compute="_compute_finding_count",
        store=False,
    )

    def _compute_finding_count(self):
        Finding = self.env["clinical.imaging.finding"]
        for rec in self:
            rec.finding_count = Finding.search_count([("imaging_id", "=", rec.id)])

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("imaging_id", "=", self.id)],
            "target": "current",
            "context": {"default_imaging_id": self.id},
        }
