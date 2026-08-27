# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re


# =============================================================================
# Clinical Imaging Series
# =============================================================================
class ClinicalImagingSeries(models.Model):
    """
    Represents a DICOM Series inside a Study.
    A Series groups a coherent acquisition set (e.g., 'AX T2', 'Arterial Phase').
    """
    _name = "clinical.imaging.series"
    _description = "Clinical Imaging Series"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "series_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Series Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
        help="Unique identifier generated from sequence at creation time."
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
        help="Uncheck to archive the series from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links & Context
    # -------------------------------------------------------------------------
    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent Study that this series belongs to.",
        tracking=True,
    )
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        related="study_id.imaging_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="study_id.patient_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Series Descriptors (DICOM & Clinical)
    # -------------------------------------------------------------------------
    series_datetime = fields.Datetime(
        string="Series Datetime",
        default=fields.Datetime.now,
        help="Datetime when this series acquisition started (DICOM SeriesTime).",
        tracking=True,
    )
    series_description = fields.Char(
        string="Series Description",
        help="DICOM Series Description or locally curated title (e.g., 'AX T2 FS').",
        tracking=True,
    )
    sequence_name = fields.Char(
        string="Sequence Name",
        help="Scanner sequence name (e.g., 'SE_T2', 'GRE', vendor-specific).",
    )
    body_part = fields.Char(
        string="Body Part",
        help="Anatomical body part examined (e.g., 'Chest', 'L-Spine').",
    )
    laterality = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
            ("bilateral", "Bilateral"),
            ("midline", "Midline"),
            ("unknown", "Unknown"),
        ],
        string="Laterality",
        default="unknown",
        help="Laterality for this series, if applicable.",
    )
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
        string="Modality",
        help="Series modality. Defaults from Study modality.",
        tracking=True,
    )
    plane = fields.Selection(
        [
            ("axial", "Axial"),
            ("coronal", "Coronal"),
            ("sagittal", "Sagittal"),
            ("oblique", "Oblique"),
            ("3d", "3D/Volume"),
            ("unknown", "Unknown"),
        ],
        string="Imaging Plane",
        default="unknown",
        help="Primary acquisition plane for the series.",
    )
    patient_position = fields.Selection(
        [
            ("HFS", "Head First Supine"),
            ("HFP", "Head First Prone"),
            ("HFDR", "Head First Decubitus Right"),
            ("HFDL", "Head First Decubitus Left"),
            ("FFS", "Feet First Supine"),
            ("FFP", "Feet First Prone"),
            ("FFDR", "Feet First Decubitus Right"),
            ("FFDL", "Feet First Decubitus Left"),
            ("SITTING", "Sitting"),
            ("STANDING", "Standing"),
            ("UNKNOWN", "Unknown"),
        ],
        string="Patient Position",
        help="Patient position during acquisition (if available).",
    )

    # Contrast phase & scheduling context
    contrast_phase = fields.Selection(
        [
            ("none", "None"),
            ("arterial", "Arterial"),
            ("venous", "Venous/Portal"),
            ("delayed", "Delayed"),
            ("precontrast", "Pre-Contrast"),
            ("postcontrast", "Post-Contrast"),
            ("dynamic", "Dynamic / Perfusion"),
            ("other", "Other"),
        ],
        string="Contrast Phase",
        default="none",
        help="Contrast phase captured by this series (if applicable).",
    )
    protocol_step_id = fields.Many2one(
        "clinical.imaging.protocol",
        string="Protocol Step",
        help="Protocol step reference linked to this series (if tracked).",
    )

    # -------------------------------------------------------------------------
    # Device & Acquisition Parameters
    # -------------------------------------------------------------------------
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Imaging Device",
        help="Device used to acquire this series.",
        tracking=True,
    )
    manufacturer = fields.Char(string="Manufacturer", help="Device manufacturer (from DICOM).")
    station_name = fields.Char(string="Station Name", help="Acquisition console name (DICOM).")

    # Generic geometry & sampling
    slice_thickness_mm = fields.Float(
        string="Slice Thickness (mm)",
        help="Nominal slice thickness in millimeters."
    )
    spacing_mm = fields.Float(
        string="Spacing (mm)",
        help="Spacing between slices or pixels (average), in millimeters."
    )
    matrix = fields.Char(
        string="Matrix",
        help="Acquisition matrix (e.g., '512x512', '256x320')."
    )
    fov_mm = fields.Char(
        string="Field of View (mm)",
        help="Field of View (e.g., '360x360')."
    )

    # Modality-specific knobs (optional)
    # CT / XR dose & exposure
    kvp = fields.Float(string="kVp", help="Peak kilovoltage.")
    ma = fields.Float(string="mA", help="Tube current (mA).")
    exposure_time_ms = fields.Float(string="Exposure Time (ms)")
    ctdi_vol_mgy = fields.Float(string="CTDIvol (mGy)")
    dlp_mgy_cm = fields.Float(string="DLP (mGy·cm)")
    dap_gy_cm2 = fields.Float(string="DAP (Gy·cm²)")
    fluoro_time_min = fields.Float(string="Fluoroscopy Time (min)")

    # MRI
    tr_ms = fields.Float(string="TR (ms)")
    te_ms = fields.Float(string="TE (ms)")
    ti_ms = fields.Float(string="TI (ms)")
    flip_angle_deg = fields.Float(string="Flip Angle (°)")
    bandwidth_hz = fields.Float(string="Bandwidth (Hz)")
    field_strength_t = fields.Float(string="Field Strength (T)")

    # Ultrasound
    probe = fields.Char(string="Probe", help="Transducer/probe type (e.g., 'C5-2').")
    frequency_mhz = fields.Float(string="Frequency (MHz)")

    # Nuclear Medicine (optional)
    radiotracer = fields.Char(string="Radiotracer")
    tracer_dose_mbq = fields.Float(string="Tracer Dose (MBq)")

    # -------------------------------------------------------------------------
    # DICOM Identifiers
    # -------------------------------------------------------------------------
    dicom_series_uid = fields.Char(
        string="DICOM Series Instance UID",
        copy=False,
        index=True,
        help="Globally unique DICOM Series Instance UID."
    )
    series_number = fields.Integer(
        string="Series Number (DICOM)",
        help="DICOM SeriesNumber integer."
    )
    instance_count = fields.Integer(
        string="Instance Count",
        compute="_compute_counts",
        store=False,
        help="Number of instances/images in this series."
    )

    # -------------------------------------------------------------------------
    # Images (child model defined in clinical_imaging_image.py)
    # -------------------------------------------------------------------------
    image_ids = fields.One2many(
        "clinical.imaging.image",
        "series_id",
        string="Images",
        help="Image instances belonging to this series.",
        copy=True,
    )

    # -------------------------------------------------------------------------
    # Files & Attachments
    # -------------------------------------------------------------------------
    key_image = fields.Binary(
        string="Key Image",
        attachment=True,
        help="Representative image/thumbnail for the series."
    )
    key_image_filename = fields.Char(string="Key Image Name")
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # PACS / Viewer Integration
    # -------------------------------------------------------------------------
    pacs_status = fields.Selection(
        [
            ("none", "None"),
            ("to_send", "Pending Send"),
            ("sent", "Sent"),
            ("received", "Received"),
            ("error", "Error"),
        ],
        string="PACS Status",
        default="none",
        help="Status of PACS/RIS transfer for this series.",
        tracking=True,
    )
    pacs_viewer_url = fields.Char(
        string="Viewer URL",
        help="Link to an external viewer at Series level (optional)."
    )
    pacs_message_last = fields.Text(
        string="Last PACS Message",
        help="Last integration message or error for this series."
    )

    # -------------------------------------------------------------------------
    # Quality & Audit
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
        tracking=True,
        help="Subjective image quality score for QA."
    )
    quality_notes = fields.Text(
        string="Quality Notes",
        help="Artifacts, motion, positioning, or other quality observations."
    )
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("acquired", "Acquired"),
            ("processed", "Processed"),
            ("archived", "Archived"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle status of the series.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        Image = self.env["clinical.imaging.image"]
        for rec in self:
            rec.instance_count = Image.search_count([("series_id", "=", rec.id)])

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("study_id")
    def _onchange_study_defaults(self):
        for rec in self:
            if not rec.study_id:
                continue
            # Default modality and device from Study
            if not rec.modality and rec.study_id.modality:
                rec.modality = rec.study_id.modality
            if rec.study_id.device_id and not rec.device_id:
                rec.device_id = rec.study_id.device_id.id
                if rec.study_id.device_id.manufacturer and not rec.manufacturer:
                    rec.manufacturer = rec.study_id.device_id.manufacturer
            # Default contrast phase None if study not using contrast
            # (left as-is; some series in non-contrast studies may still be marked)

    @api.onchange("device_id")
    def _onchange_device(self):
        for rec in self:
            if rec.device_id and not rec.manufacturer:
                rec.manufacturer = rec.device_id.manufacturer
            # Soft warning if modality mismatch
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                return {
                    "warning": {
                        "title": _("Modality Mismatch"),
                        "message": _(
                            "Device modality (%s) differs from Series modality (%s). "
                            "Please review your selection."
                        ) % (rec.device_id.modality, rec.modality)
                    }
                }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("dicom_series_uid")
    def _check_dicom_series_uid_format(self):
        """
        Basic DICOM UID shape: digits and dots, starts with a digit, no '..'
        """
        uid_re = re.compile(r"^[0-9](?:[0-9]*\.?)*[0-9]?$")
        for rec in self:
            if rec.dicom_series_uid:
                uid = rec.dicom_series_uid.strip()
                if ".." in uid or not uid_re.match(uid):
                    raise ValidationError(_("DICOM Series Instance UID appears invalid."))

    @api.constrains("modality", "device_id")
    def _check_device_modality(self):
        for rec in self:
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                raise ValidationError(_("Device modality must match Series modality."))

    @api.constrains("ctdi_vol_mgy", "dlp_mgy_cm", "dap_gy_cm2", "fluoro_time_min",
                    "kvp", "ma", "exposure_time_ms", "tr_ms", "te_ms", "ti_ms",
                    "flip_angle_deg", "bandwidth_hz", "field_strength_t",
                    "slice_thickness_mm", "spacing_mm", "frequency_mhz", "tracer_dose_mbq")
    def _check_non_negative_params(self):
        for rec in self:
            for field_name in [
                "ctdi_vol_mgy", "dlp_mgy_cm", "dap_gy_cm2", "fluoro_time_min",
                "kvp", "ma", "exposure_time_ms", "tr_ms", "te_ms", "ti_ms",
                "flip_angle_deg", "bandwidth_hz", "field_strength_t",
                "slice_thickness_mm", "spacing_mm", "frequency_mhz", "tracer_dose_mbq"
            ]:
                val = getattr(rec, field_name)
                if val is not None and val < 0:
                    raise ValidationError(_("%s cannot be negative.") % field_name)

    @api.constrains("quality_score")
    def _check_quality_score(self):
        for rec in self:
            if rec.quality_score and rec.quality_score not in ("0", "1", "2", "3", "4", "5"):
                raise ValidationError(_("Invalid Image Quality score."))

    # Unique constraints
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Series Number must be unique per company.',
    )
    _series_uid_company_unique = models.Constraint(
        'unique(dicom_series_uid, company_id)',
        'DICOM Series UID must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.series") or _("New")
            # default modality from study if missing
            if not vals.get("modality") and vals.get("study_id"):
                study = self.env["clinical.imaging.study"].browse(vals["study_id"])
                if study and study.modality:
                    vals["modality"] = study.modality
        records = super().create(vals_list)
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("dicom_series_uid", False)
        default.setdefault("pacs_status", "none")
        default.setdefault("pacs_viewer_url", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state in ("processed",):
                raise UserError(_("Processed series cannot be deleted. Archive instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_mark_acquired(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft series can be marked as Acquired."))
            if not rec.series_datetime:
                rec.series_datetime = fields.Datetime.now()
            rec.state = "acquired"
            rec.message_post(body=_("Series marked as Acquired."))

    def action_mark_processed(self):
        for rec in self:
            if rec.state not in ("acquired",):
                raise UserError(_("Only Acquired series can be marked as Processed."))
            rec.state = "processed"
            rec.message_post(body=_("Series marked as Processed."))

    def action_archive(self):
        for rec in self:
            if rec.state not in ("processed", "cancelled"):
                raise UserError(_("Only Processed or Cancelled series can be archived."))
            rec.active = False
            rec.state = "archived"
            rec.message_post(body=_("Series archived."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "processed":
                raise UserError(_("Processed series cannot be cancelled. Archive instead."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Series cancelled. Reason: %s") % reason)
            else:
                rec.message_post(body=_("Series cancelled."))

    # PACS helpers
    def action_send_to_pacs(self):
        for rec in self:
            rec.pacs_status = "to_send"
            rec.pacs_message_last = _("Queued for PACS transmission.")
            rec.message_post(body=_("Series queued for PACS transmission."))

    def action_mark_sent(self, message=None):
        for rec in self:
            rec.pacs_status = "sent"
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Series marked as Sent to PACS."))

    def action_mark_received(self, viewer_url=None, message=None):
        for rec in self:
            rec.pacs_status = "received"
            if viewer_url:
                rec.pacs_viewer_url = viewer_url
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Series acknowledged by PACS."))

    def action_mark_pacs_error(self, message):
        for rec in self:
            rec.pacs_status = "error"
            rec.pacs_message_last = message or _("Unknown PACS error.")
            rec.message_post(body=_("PACS error on Series: %s") % (message or ""))

    # Navigation
    def action_open_images(self):
        self.ensure_one()
        return {
            "name": _("Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("series_id", "=", self.id)],
            "target": "current",
            "context": {"default_series_id": self.id},
        }

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
    @api.depends("name", "series_description", "study_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _("Series")]
            if rec.series_description:
                parts.append(rec.series_description)
            if rec.study_id:
                parts.append(f"({rec.study_id.display_name})")
            rec.display_name = " - ".join([part for part in parts if part])


# =============================================================================
# Generic key-value parameters attached to a Series (optional)
# =============================================================================
class ClinicalImagingSeriesParam(models.Model):
    _name = "clinical.imaging.series.param"
    _description = "Imaging Series Parameter"
    _order = "series_id, sequence, id"
    _check_company_auto = True

    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="series_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    key = fields.Char(string="Key", required=True, help="Parameter key (e.g., 'EchoTrainLength').")
    value = fields.Char(string="Value", help="Parameter value (string).")
    unit = fields.Char(string="Unit", help="Optional unit (e.g., 'ms', 'mm').")
    note = fields.Char(string="Notes")


# =============================================================================
# Per-Series Dose / Exposure (optional, complementary to Result-level dose)
# =============================================================================
class ClinicalImagingSeriesDose(models.Model):
    _name = "clinical.imaging.series.dose"
    _description = "Imaging Series Dose/Exposure"
    _order = "series_id, sequence, id"
    _check_company_auto = True

    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="series_id.company_id",
        store=True,
        readonly=True,
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
    value = fields.Float(string="Value", required=True)
    unit = fields.Char(string="Unit", help="Unit override if 'Other' metric or custom unit.")
    note = fields.Char(string="Notes")

    @api.constrains("value")
    def _check_value_non_negative(self):
        for rec in self:
            if rec.value is not None and rec.value < 0.0:
                raise ValidationError(_("Dose/Exposure value must be non-negative."))


# =============================================================================
# Soft links on Study to navigate/open Series
# =============================================================================
class ClinicalImagingStudy(models.Model):
    _inherit = "clinical.imaging.study"

    def action_create_series(self):
        """
        Convenience action to create a blank Series from the Study form.
        """
        self.ensure_one()
        series = self.env["clinical.imaging.series"].create({
            "study_id": self.id,
            "company_id": self.company_id.id,
            "modality": self.modality or False,
            "device_id": self.device_id.id if getattr(self, "device_id", False) else False,
        })
        return {
            "name": _("Series"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.series",
            "view_mode": "form",
            "res_id": series.id,
            "target": "current",
        }
