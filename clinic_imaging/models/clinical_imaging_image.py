# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re
import json


# =============================================================================
# Image Tag (classification)
# =============================================================================
class ClinicalImagingImageTag(models.Model):
    _name = "clinical.imaging.image.tag"
    _description = "Clinical Imaging Image Tag"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Tag Name", required=True)
    color = fields.Integer(string="Color Index", help="Color index for kanban/list chips.")
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Image Tag must be unique per company.',
    )


# =============================================================================
# Clinical Imaging Image (DICOM Instance / Rendered Image)
# =============================================================================
class ClinicalImagingImage(models.Model):
    """
    Represents a single DICOM SOP Instance (or a rendered image file) inside a Series.
    Stores DICOM identifiers (SOP Instance UID, SOP Class UID), key pixel metadata,
    display parameters, and binary content (thumbnail/preview and/or original file).

    Integrations:
      - Patient, Appointment, Encounter, Treatment: propagated via Series -> Study -> Imaging.
      - Device/Room: indirect via Study/Series -> Device.
      - Result: images can be marked as key and linked from results.
      - Portal: optional publishing with privacy level.
      - PACS/Viewer: endpoint URL and status hooks.
    """
    _name = "clinical.imaging.image"
    _description = "Clinical Imaging Image"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "instance_number asc, id asc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Image Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
        help="Unique identifier generated from sequence at creation time.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="series_id.study_id.company_id",
        store=True,
        readonly=True,
        help="Company derived from the parent Study.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive the image from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links & Context (propagated)
    # -------------------------------------------------------------------------
    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent Series that this image belongs to.",
        tracking=True,
    )
    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        related="series_id.study_id",
        store=True,
        readonly=True,
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
    # DICOM Identifiers & Ordering
    # -------------------------------------------------------------------------
    dicom_instance_uid = fields.Char(
        string="DICOM SOP Instance UID",
        copy=False,
        index=True,
        help="Globally unique DICOM SOP Instance UID.",
        tracking=True,
    )
    dicom_sop_class_uid = fields.Char(
        string="DICOM SOP Class UID",
        help="Indicates the SOP Class (e.g., CT Image Storage).",
    )
    instance_number = fields.Integer(
        string="Instance Number (DICOM)",
        help="DICOM InstanceNumber (ordering within the series).",
        index=True,
    )
    frame_count = fields.Integer(
        string="Frame Count",
        help="Number of frames if multi-frame (0/1 for single-frame).",
    )
    acquisition_datetime = fields.Datetime(
        string="Acquisition Datetime",
        help="Acquisition date/time of this image (DICOM AcquisitionDate/Time).",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Pixel / Geometry Metadata
    # -------------------------------------------------------------------------
    rows = fields.Integer(string="Rows", help="Number of rows (pixel height).")
    columns = fields.Integer(string="Columns", help="Number of columns (pixel width).")
    pixel_spacing_mm = fields.Char(
        string="Pixel Spacing (mm)",
        help="DICOM PixelSpacing as 'row_spacing\\column_spacing' or JSON array.",
    )
    slice_thickness_mm = fields.Float(string="Slice Thickness (mm)")
    slice_location_mm = fields.Float(string="Slice Location (mm)")
    image_position_patient = fields.Char(
        string="Image Position (Patient)",
        help="DICOM (x\\y\\z) position of the first pixel in mm.",
    )
    image_orientation_patient = fields.Char(
        string="Image Orientation (Patient)",
        help="DICOM orientation (6 values: row and column direction cosines).",
    )
    photometric_interpretation = fields.Selection(
        [
            ("MONOCHROME1", "MONOCHROME1"),
            ("MONOCHROME2", "MONOCHROME2"),
            ("RGB", "RGB"),
            ("YBR_FULL", "YBR_FULL"),
            ("PALETTE_COLOR", "PALETTE_COLOR"),
            ("HSV", "HSV"),
            ("LAB", "LAB"),
        ],
        string="Photometric Interpretation",
        help="DICOM Photometric Interpretation of the pixel data.",
    )
    bits_allocated = fields.Integer(string="Bits Allocated")
    bits_stored = fields.Integer(string="Bits Stored")
    high_bit = fields.Integer(string="High Bit")
    rescale_intercept = fields.Float(string="Rescale Intercept")
    rescale_slope = fields.Float(string="Rescale Slope")
    window_center = fields.Float(string="Window Center")
    window_width = fields.Float(string="Window Width")
    resolution = fields.Char(
        string="Resolution",
        compute="_compute_resolution",
        store=False,
        help="Convenience string 'WIDTH x HEIGHT'.",
    )

    # -------------------------------------------------------------------------
    # Files & Attachments
    # -------------------------------------------------------------------------
    file_thumbnail = fields.Binary(
        string="Thumbnail",
        attachment=True,
        help="Small preview thumbnail for fast listing.",
    )
    file_thumbnail_filename = fields.Char(string="Thumbnail File Name")
    file_image = fields.Binary(
        string="Rendered Image (e.g., JPEG/PNG)",
        attachment=True,
        help="Rendered image for quick viewing when original is DICOM.",
    )
    file_image_filename = fields.Char(string="Image File Name")
    file_dicom = fields.Binary(
        string="Original DICOM",
        attachment=True,
        help="Original DICOM instance file, if stored.",
    )
    file_dicom_filename = fields.Char(string="DICOM File Name")
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Quality & Flags
    # -------------------------------------------------------------------------
    is_key = fields.Boolean(
        string="Key Image",
        help="Mark as key/representative image for series/result.",
        tracking=True,
    )
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
    )
    quality_notes = fields.Text(string="Quality Notes")
    notes = fields.Text(string="Internal Notes")

    # Tags / labels
    tag_ids = fields.Many2many(
        "clinical.imaging.image.tag",
        "clinical_imaging_image_tag_rel",
        "image_id",
        "tag_id",
        string="Tags",
        help="Classification tags for this image.",
    )
    tag_count = fields.Integer(string="Tag Count", compute="_compute_tag_count", store=False)

    # Annotations (child model)
    annotation_ids = fields.One2many(
        "clinical.imaging.image.annotation",
        "image_id",
        string="Annotations",
        help="Structured annotations (ROIs, measurements, comments) for this image.",
        copy=True,
    )
    annotation_count = fields.Integer(
        string="Annotation Count",
        compute="_compute_annotation_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Portal & Privacy
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this image in the portal (subject to rules).",
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
        help="Controls how widely accessible the image is to staff and on the portal.",
        tracking=True,
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
        help="Status of PACS/VNA transfer for this image.",
        tracking=True,
    )
    pacs_viewer_url = fields.Char(
        string="Viewer URL",
        help="Link to an external PACS/Web viewer at image level (optional).",
    )
    pacs_message_last = fields.Text(
        string="Last PACS Message",
        help="Last integration message or error for this image.",
    )

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
        help="Lifecycle status of the image.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_resolution(self):
        for rec in self:
            if rec.columns and rec.rows:
                rec.resolution = f"{int(rec.columns)} x {int(rec.rows)}"
            else:
                rec.resolution = False

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    def _compute_tag_count(self):
        for rec in self:
            rec.tag_count = len(rec.tag_ids)

    def _compute_annotation_count(self):
        for rec in self:
            rec.annotation_count = len(rec.annotation_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("series_id")
    def _onchange_series_defaults(self):
        """Default ordering and timestamps from Series, if empty."""
        for rec in self:
            if not rec.series_id:
                continue
            if not rec.acquisition_datetime and rec.series_id.series_datetime:
                rec.acquisition_datetime = rec.series_id.series_datetime
            # Suggest next instance number
            if not rec.instance_number:
                existing = self.search_read(
                    [("series_id", "=", rec.series_id.id)],
                    fields=["instance_number"],
                    limit=0,
                )
                used = [e["instance_number"] or 0 for e in existing]
                next_no = (max(used) + 1) if used else 1
                rec.instance_number = next_no

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("dicom_instance_uid")
    def _check_dicom_instance_uid_format(self):
        """
        Basic DICOM UID shape: digits and dots, starts with digit, no double dots.
        """
        uid_re = re.compile(r"^[0-9](?:[0-9]*\.?)*[0-9]?$")
        for rec in self:
            if rec.dicom_instance_uid:
                uid = rec.dicom_instance_uid.strip()
                if ".." in uid or not uid_re.match(uid):
                    raise ValidationError(_("DICOM SOP Instance UID appears invalid."))

    @api.constrains("window_width")
    def _check_window_width_positive(self):
        for rec in self:
            if rec.window_width is not None and rec.window_width <= 0:
                raise ValidationError(_("Window Width must be positive when set."))

    @api.constrains("bits_stored", "bits_allocated", "high_bit")
    def _check_bits_relations(self):
        for rec in self:
            if rec.bits_stored and rec.bits_allocated and rec.bits_stored > rec.bits_allocated:
                raise ValidationError(_("Bits Stored cannot exceed Bits Allocated."))
            if rec.high_bit and rec.bits_stored and rec.high_bit != rec.bits_stored - 1:
                # Do not hard-block if vendor-specific, but prefer warning; keep as constraint for data quality
                raise ValidationError(_("High Bit should be Bits Stored - 1."))

    @api.constrains(
        "rows", "columns", "frame_count", "instance_number",
        "slice_thickness_mm", "slice_location_mm", "rescale_slope"
    )
    def _check_non_negative_numeric(self):
        for rec in self:
            for fname in ["rows", "columns", "frame_count", "instance_number"]:
                val = getattr(rec, fname)
                if val is not None and val < 0:
                    raise ValidationError(_("%s cannot be negative.") % fname)
            for fname in ["slice_thickness_mm", "slice_location_mm"]:
                # Slice location can be negative (position), so skip; only thickness must be non-negative
                pass
            if rec.slice_thickness_mm is not None and rec.slice_thickness_mm < 0:
                raise ValidationError(_("slice_thickness_mm cannot be negative."))
            # rescale_slope can be negative in some modalities; allow any real number

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Image Number must be unique per company.',
    )
    _sop_uid_company_unique = models.Constraint(
        'unique(dicom_instance_uid, company_id)',
        'DICOM SOP Instance UID must be unique per company.',
    )
    _series_instance_unique = models.Constraint(
        'unique(series_id, instance_number, company_id)',
        'Instance Number must be unique within a Series (per company).',
    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.image") or _("New")
        records = super().create(vals_list)
        # If image is marked as key and Series has no key image, set it
        for rec in records:
            if rec.is_key and rec.series_id and not rec.series_id.key_image:
                rec.series_id.write({
                    "key_image": rec.file_image or rec.file_thumbnail or False,
                    "key_image_filename": rec.file_image_filename or rec.file_thumbnail_filename or False,
                })
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("dicom_instance_uid", False)
        default.setdefault("pacs_status", "none")
        default.setdefault("pacs_viewer_url", False)
        default.setdefault("is_key", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state in ("processed",):
                raise UserError(_("Processed images cannot be deleted. Archive instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_mark_acquired(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft images can be marked as Acquired."))
            if not rec.acquisition_datetime:
                rec.acquisition_datetime = fields.Datetime.now()
            rec.state = "acquired"
            rec.message_post(body=_("Image marked as Acquired."))

    def action_mark_processed(self):
        for rec in self:
            if rec.state not in ("acquired",):
                raise UserError(_("Only Acquired images can be marked as Processed."))
            rec.state = "processed"
            rec.message_post(body=_("Image marked as Processed."))

    def action_archive(self):
        for rec in self:
            if rec.state not in ("processed", "cancelled"):
                raise UserError(_("Only Processed or Cancelled images can be archived."))
            rec.active = False
            rec.state = "archived"
            rec.message_post(body=_("Image archived."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "processed":
                raise UserError(_("Processed images cannot be cancelled. Archive instead."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Image cancelled. Reason: %s") % reason)
            else:
                rec.message_post(body=_("Image cancelled."))

    # PACS helpers
    def action_send_to_pacs(self):
        for rec in self:
            rec.pacs_status = "to_send"
            rec.pacs_message_last = _("Queued for PACS transmission.")
            rec.message_post(body=_("Image queued for PACS transmission."))

    def action_mark_sent(self, message=None):
        for rec in self:
            rec.pacs_status = "sent"
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Image marked as Sent to PACS."))

    def action_mark_received(self, viewer_url=None, message=None):
        for rec in self:
            rec.pacs_status = "received"
            if viewer_url:
                rec.pacs_viewer_url = viewer_url
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Image acknowledged by PACS."))

    def action_mark_pacs_error(self, message):
        for rec in self:
            rec.pacs_status = "error"
            rec.pacs_message_last = message or _("Unknown PACS error.")
            rec.message_post(body=_("PACS error on Image: %s") % (message or ""))

    # Portal / Attachments / Navigation
    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

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

    def action_set_as_key(self):
        for rec in self:
            rec.is_key = True
            if rec.series_id and not rec.series_id.key_image:
                rec.series_id.write({
                    "key_image": rec.file_image or rec.file_thumbnail or False,
                    "key_image_filename": rec.file_image_filename or rec.file_thumbnail_filename or False,
                })
            rec.message_post(body=_("Image flagged as Key."))

    # def action_add_to_result(self, result_id=None):
    #     """
    #     Add this image to a Result's key images.
    #     Requires model 'clinical.imaging.result' to exist (same module).
    #     """
    #     Result = self.env["clinical.imaging.result"]
    #     for rec in self:
    #         # Find the latest final/amended result for the imaging if none provided
    #         dest = False
    #         if result_id:
    #             dest = Result.browse(result_id).exists()
    #         else:
    #             dest = Result.search(
    #                 [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
    #                 order="signed_datetime desc, write_date desc, id desc",
    #                 limit=1,
    #             )
    #         if not dest:
    #             raise UserError(_("No target Result found to add this image."))
    #         dest.key_image_ids = [(4, rec.id)]
    #         rec.message_post(body=_("Image added to Result %s as key image.") % dest.display_name)

    # Display
    @api.depends("name", "series_id", "study_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _("Image")]
            if rec.series_id:
                parts.append(rec.series_id.series_description or rec.series_id.display_name)
            if rec.study_id:
                parts.append(f"({rec.study_id.display_name})")
            rec.display_name = " - ".join([part for part in parts if part])


# =============================================================================
# Image Annotation (ROIs, measurements, comments)
# =============================================================================
class ClinicalImagingImageAnnotation(models.Model):
    """
    Stores structured annotations attached to an Image:
      - ROI geometry (point/line/rect/circle/polygon/polyline)
      - Optional measurement values and units
      - Optional linkage to a structured finding
    Geometry is stored as JSON (screen/pixel or patient space as provided by the viewer).
    """
    _name = "clinical.imaging.image.annotation"
    _description = "Clinical Imaging Image Annotation"
    _order = "image_id, sequence, id"
    _check_company_auto = True

    image_id = fields.Many2one(
        "clinical.imaging.image",
        string="Image",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="image_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    type = fields.Selection(
        [
            ("point", "Point"),
            ("line", "Line"),
            ("rect", "Rectangle"),
            ("circle", "Circle"),
            ("polygon", "Polygon"),
            ("polyline", "Polyline"),
            ("text", "Text"),
            ("arrow", "Arrow"),
            ("other", "Other"),
        ],
        string="Annotation Type",
        required=True,
        default="point",
    )
    geometry_json = fields.Text(
        string="Geometry JSON",
        help="JSON payload describing ROI geometry (coordinates, radius, etc.).",
    )
    coord_space = fields.Selection(
        [
            ("pixel", "Pixel Space"),
            ("patient", "Patient Space (mm)"),
            ("world", "World / Scanner Space"),
        ],
        string="Coordinate Space",
        default="pixel",
        help="Coordinate space of the stored geometry.",
    )
    measurement_value = fields.Float(string="Measurement Value", help="Primary measurement value, if any.")
    unit = fields.Char(string="Unit", help="Unit for the measurement value (e.g., 'mm', 'cm²').")
    color = fields.Char(string="Color", help="Optional color (hex or named) for display.")
    comment = fields.Char(string="Comment", help="Short comment for this annotation.")

    # author_id = fields.Many2one("res.users", string="Author", default=lambda self: self.env.user, required=True)
    # result_id = fields.Many2one(
    #     "clinical.imaging.result",
    #     string="Linked Result",
    #     help="Optional diagnostic result this annotation belongs to.",
    # )
    finding_id = fields.Many2one(
        "clinical.imaging.finding",
        string="Linked Finding",
        help="Optional structured finding linked to this annotation.",
    )
    created_datetime = fields.Datetime(string="Created At", default=fields.Datetime.now)
    last_modified = fields.Datetime(string="Last Modified", readonly=True)

    @api.constrains("geometry_json")
    def _check_geometry_json(self):
        for rec in self:
            if rec.type not in ("text", "other") and not rec.geometry_json:
                raise ValidationError(_("Geometry JSON is required for non-text annotations."))
            if rec.geometry_json:
                try:
                    json.loads(rec.geometry_json)
                except Exception:
                    raise ValidationError(_("Geometry JSON is not valid JSON."))

    @api.constrains("measurement_value")
    def _check_measurement_non_negative_when_length_area(self):
        for rec in self:
            # If unit suggests a length/area, value must be non-negative
            if rec.unit and any(u in rec.unit.lower() for u in ["mm", "cm", "m", "px", "²", "2"]):
                if rec.measurement_value is not None and rec.measurement_value < 0:
                    raise ValidationError(_("Measurement value must be non-negative for length/area units."))

    def write(self, vals):
        vals["last_modified"] = fields.Datetime.now()
        return super().write(vals)

    # Navigation helper
    def action_open_image(self):
        self.ensure_one()
        return {
            "name": _("Image"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "form",
            "res_id": self.image_id.id,
            "target": "current",
        }


# =============================================================================
# Soft links on Series/Result to navigate/open Images
# =============================================================================
class ClinicalImagingSeries(models.Model):
    _inherit = "clinical.imaging.series"

    def action_create_image(self):
        """
        Convenience action to create a blank Image from the Series form.
        """
        self.ensure_one()
        image = self.env["clinical.imaging.image"].create({
            "series_id": self.id,
        })
        return {
            "name": _("Image"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "form",
            "res_id": image.id,
            "target": "current",
        }

# DIPINDAH KE File clinical_imaging_kpi.py
# class ClinicalImagingResult(models.Model):
#     _inherit = "clinical.imaging.result"

#     def action_open_key_images(self):
#         self.ensure_one()
#         return {
#             "name": _("Key Images"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.image",
#             "view_mode": "list,form,kanban",
#             "domain": [("id", "in", self.key_image_ids.ids)],
#             "target": "current",
#         }
