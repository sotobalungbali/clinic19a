# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re

# =============================================================================
# Clinical Imaging Study
# =============================================================================
class ClinicalImagingStudy(models.Model):
    """
    Represents a DICOM Study (collection of one or more Series) acquired
    for an Imaging record (clinical.imaging).

    Design notes:
    - One Imaging record MAY have multiple Studies (multi-modality or repeat).
    - Each Study groups Series and Images, stores key DICOM attributes,
      and tracks PACS/RIS integration metadata.
    - This model does not duplicate the medical report; see clinical.imaging.result.
    """
    _name = "clinical.imaging.study"
    _description = "Clinical Imaging Study"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "study_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Study Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence at creation time.",
        index=True,
        tracking=True,
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
        help="Uncheck to archive this study from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links & Context
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        required=True,
        ondelete="cascade",
        index=True,
        help="The parent Imaging record that this study belongs to.",
        tracking=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="imaging_id.patient_id",
        store=True,
        readonly=True,
        help="Patient (readonly; propagated from Imaging).",
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True, readonly=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Clinical Encounter",
        related="imaging_id.encounter_id",
        store=True, readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True, readonly=True,
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True, readonly=True,
    )

    # -------------------------------------------------------------------------
    # Study Descriptors (DICOM & Clinical)
    # -------------------------------------------------------------------------
    study_datetime = fields.Datetime(
        string="Study Datetime",
        default=fields.Datetime.now,
        help="Datetime the study acquisition was started (DICOM StudyDate/StudyTime).",
        tracking=True,
    )
    study_description = fields.Char(
        string="Study Description",
        help="DICOM Study Description or locally curated summary.",
        tracking=True,
    )
    body_part = fields.Char(
        string="Body Part",
        help="Body part examined (free text or as per DICOM BodyPartExamined).",
    )
    laterality = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
            ("bilateral", "Bilateral"),
            ("unknown", "Unknown"),
        ],
        string="Laterality",
        default="unknown",
        help="Laterality (if applicable).",
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
        help="Primary modality for this study. Defaults from Imaging Type if available.",
        tracking=True,
    )
    referring_doctor_id = fields.Many2one(
        "hr.employee",
        string="Referring Doctor",
        domain=[("is_doctor", "=", True)],
        help="Referring physician.",
    )
    reading_radiologist_id = fields.Many2one(
        "hr.employee",
        string="Reading Radiologist",
        domain=[("is_doctor", "=", True)],
        help="Radiologist responsible for reading this study.",
        tracking=True,
    )

    # Contrast / Sedation actually used in this STUDY (not just 'type default')
    contrast_used = fields.Boolean(
        string="Contrast Used",
        help="Checked if contrast was administered during this study.",
    )
    contrast_agent_product_id = fields.Many2one(
        "product.product",
        string="Contrast Agent",
        domain=[("type", "in", ["consu"])],
        help="Actual contrast agent used.",
    )
    contrast_volume_ml = fields.Float(
        string="Contrast Volume (mL)",
        help="Volume of contrast administered in milliliters.",
    )
    sedation_used = fields.Boolean(
        string="Sedation Used",
        help="Checked if sedation/anxiolysis was used.",
    )
    sedation_agent_product_id = fields.Many2one(
        "product.product",
        string="Sedation Agent",
        domain=[("type", "in", ["consu"])],
        help="Sedation/anxiolysis agent used, if any.",
    )

    # -------------------------------------------------------------------------
    # Device & Acquisition
    # -------------------------------------------------------------------------
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Imaging Device",
        help="Device used to acquire this study.",
        tracking=True,
    )
    manufacturer = fields.Char(
        string="Manufacturer",
        help="DICOM Manufacturer (from device) if known.",
    )
    station_name = fields.Char(
        string="Station Name",
        help="DICOM StationName (acquisition console).",
    )

    # -------------------------------------------------------------------------
    # DICOM Identifiers
    # -------------------------------------------------------------------------
    dicom_study_uid = fields.Char(
        string="DICOM Study Instance UID",
        copy=False,
        index=True,
        help="Globally unique DICOM Study Instance UID.",
    )
    dicom_accession_number = fields.Char(
        string="Accession Number",
        copy=False,
        index=True,
        help="Accession Number assigned by RIS/PACS for the study.",
    )

    # -------------------------------------------------------------------------
    # Series & Images (linked models defined in other files)
    # -------------------------------------------------------------------------
    series_ids = fields.One2many(
        "clinical.imaging.series",
        "study_id",
        string="Series",
        help="List of series belonging to this study.",
        copy=True,
    )
    series_count = fields.Integer(
        string="Series Count",
        compute="_compute_counts",
        store=False,
    )
    image_count = fields.Integer(
        string="Image Count",
        compute="_compute_counts",
        store=False,
        help="Total images across all series in this study.",
    )

    # -------------------------------------------------------------------------
    # Files & Attachments (optional)
    # -------------------------------------------------------------------------
    primary_preview = fields.Binary(
        string="Primary Preview",
        attachment=True,
        help="Representative image (e.g., thumbnail) for quick preview.",
    )
    dicom_bundle = fields.Binary(
        string="DICOM Export (ZIP)",
        attachment=True,
        help="Optional ZIP export of DICOM instances for this study.",
    )
    dicom_bundle_filename = fields.Char(string="DICOM Export File Name")
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
        help="Status for PACS/RIS integration workflows.",
        tracking=True,
    )
    pacs_viewer_url = fields.Char(
        string="Viewer URL",
        help="Link to an external viewer (PACS/VNA/Web viewer) for this study.",
    )
    pacs_message_last = fields.Text(
        string="Last PACS Message",
        help="Last message or error returned by PACS/RIS integration.",
    )

    # -------------------------------------------------------------------------
    # Notes & Audit
    # -------------------------------------------------------------------------
    notes = fields.Text(
        string="Internal Notes",
        help="Internal notes about this study.",
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("acquired", "Acquired"),
            ("verified", "Verified"),
            ("archived", "Archived"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the study.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        Image = self.env["clinical.imaging.image"]
        for rec in self:
            rec.series_count = len(rec.series_ids)
            # Count images by study via series
            if rec.series_ids:
                rec.image_count = Image.search_count([("series_id", "in", rec.series_ids.ids)])
            else:
                rec.image_count = 0

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_id")
    def _onchange_imaging_id_defaults(self):
        for rec in self:
            if not rec.imaging_id:
                continue
            # Default modality from imaging type
            if not rec.modality and rec.imaging_id.imaging_type_id and rec.imaging_id.imaging_type_id.modality:
                rec.modality = rec.imaging_id.imaging_type_id.modality
            # Default device/manufacturer/station from imaging device
            if rec.imaging_id.device_id and not rec.device_id:
                rec.device_id = rec.imaging_id.device_id.id
                if rec.imaging_id.device_id.manufacturer:
                    rec.manufacturer = rec.imaging_id.device_id.manufacturer
                if rec.imaging_id.device_id.location and not rec.station_name:
                    rec.station_name = rec.imaging_id.device_id.location
            # Default doctors
            if rec.imaging_id.doctor_id and not rec.referring_doctor_id:
                rec.referring_doctor_id = rec.imaging_id.doctor_id.id
            # reading radiologist may be different; leave blank unless same
            # Copy accession from imaging if present
            if rec.imaging_id.dicom_accession_number and not rec.dicom_accession_number:
                rec.dicom_accession_number = rec.imaging_id.dicom_accession_number
            # Copy study UID to imaging if imaging lacks it
            if rec.dicom_study_uid and not rec.imaging_id.dicom_study_uid:
                rec.imaging_id.dicom_study_uid = rec.dicom_study_uid

    @api.onchange("device_id")
    def _onchange_device_id(self):
        for rec in self:
            if rec.device_id and rec.device_id.manufacturer and not rec.manufacturer:
                rec.manufacturer = rec.device_id.manufacturer
            # If device modality differs, warn
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                return {
                    "warning": {
                        "title": _("Modality Mismatch"),
                        "message": _(
                            "Device modality (%s) differs from Study modality (%s). "
                            "Please review your selection."
                        ) % (rec.device_id.modality, rec.modality)
                    }
                }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("dicom_study_uid")
    def _check_dicom_uid_format(self):
        """
        Soft validation that Study Instance UID looks like a DICOM UID:
        digits and dots, starts with digit, no consecutive dots.
        """
        uid_re = re.compile(r"^[0-9](?:[0-9]*\.?)*[0-9]?$")
        for rec in self:
            if rec.dicom_study_uid:
                uid = rec.dicom_study_uid.strip()
                if ".." in uid or not uid_re.match(uid):
                    raise ValidationError(_("DICOM Study Instance UID appears invalid."))

    @api.constrains("reading_radiologist_id", "state")
    def _check_verify_requirements(self):
        for rec in self:
            if rec.state in ("verified",) and not rec.reading_radiologist_id:
                raise ValidationError(_("Reading Radiologist is required when Study is Verified."))

    @api.constrains("modality", "device_id")
    def _check_device_modality_match(self):
        for rec in self:
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                raise ValidationError(_("Device modality must match Study modality."))

    # Unique constraints
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Study Number must be unique per company.',
    )
    _study_uid_company_unique = models.Constraint(
        'unique(dicom_study_uid, company_id)',
        'DICOM Study UID must be unique per company.',
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
                vals["name"] = seq.next_by_code("clinical.imaging.study") or _("New")
        records = super().create(vals_list)
        # Post-create: propagate first study UID to Imaging (if empty)
        for rec in records:
            if rec.dicom_study_uid and rec.imaging_id and not rec.imaging_id.dicom_study_uid:
                rec.imaging_id.sudo().write({"dicom_study_uid": rec.dicom_study_uid})
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("dicom_study_uid", False)
        default.setdefault("pacs_status", "none")
        default.setdefault("pacs_viewer_url", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state == "verified":
                raise UserError(_("You cannot delete a Verified study. Consider Archiving instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_mark_acquired(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft studies can be marked as Acquired."))
            if not rec.study_datetime:
                rec.study_datetime = fields.Datetime.now()
            rec.state = "acquired"
            rec.message_post(body=_("Study marked as Acquired."))

    def action_verify(self):
        for rec in self:
            if rec.state not in ("acquired",):
                raise UserError(_("Only Acquired studies can be Verified."))
            if not rec.reading_radiologist_id:
                raise UserError(_("Please set Reading Radiologist before verifying."))
            rec.state = "verified"
            rec.message_post(body=_("Study verified by %s.") % (rec.reading_radiologist_id.name or _("Radiologist")))
            # Optional: notify Imaging that a study is verified
            if rec.imaging_id and rec.imaging_id.state in ("completed",):
                # nothing to change on imaging; leave to result workflow
                pass

    def action_archive(self):
        for rec in self:
            if rec.state not in ("verified", "cancelled"):
                raise UserError(_("Only Verified or Cancelled studies can be archived."))
            rec.state = "archived"
            rec.active = False
            rec.message_post(body=_("Study archived."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "verified":
                raise UserError(_("Verified studies cannot be cancelled. Archive instead."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Study cancelled. Reason: %s") % reason)
            else:
                rec.message_post(body=_("Study cancelled."))

    # PACS / Viewer helpers
    def action_send_to_pacs(self):
        """
        Placeholder for integration hooks (connector module).
        Change pacs_status and store message.
        """
        for rec in self:
            rec.pacs_status = "to_send"
            rec.pacs_message_last = _("Queued for PACS transmission.")
            rec.message_post(body=_("Study queued for PACS transmission."))

    def action_mark_sent(self, message=None):
        for rec in self:
            rec.pacs_status = "sent"
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Study marked as Sent to PACS."))

    def action_mark_received(self, viewer_url=None, message=None):
        for rec in self:
            rec.pacs_status = "received"
            if viewer_url:
                rec.pacs_viewer_url = viewer_url
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Study acknowledged by PACS."))

    def action_mark_pacs_error(self, message):
        for rec in self:
            rec.pacs_status = "error"
            rec.pacs_message_last = message or _("Unknown PACS error.")
            rec.message_post(body=_("PACS error: %s") % (message or ""))

    # Navigation
    def action_open_series(self):
        self.ensure_one()
        return {
            "name": _("Series"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.series",
            "view_mode": "list,form,kanban",
            "domain": [("study_id", "=", self.id)],
            "target": "current",
            "context": {"default_study_id": self.id},
        }

    def action_open_images(self):
        self.ensure_one()
        return {
            "name": _("Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("series_id.study_id", "=", self.id)],
            "target": "current",
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


# =============================================================================
# Study Notes (lightweight threaded items per Study)
# =============================================================================
class ClinicalImagingStudyNote(models.Model):
    _name = "clinical.imaging.study.note"
    _description = "Clinical Imaging Study Note"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="study_id.company_id",
        store=True,
        readonly=True,
    )
    author_id = fields.Many2one(
        "res.users",
        string="Author",
        default=lambda self: self.env.user,
        required=True,
    )
    note = fields.Text(
        string="Note",
        required=True,
        help="Plain text note about this study (non-diagnostic).",
    )
    tag = fields.Selection(
        [
            ("general", "General"),
            ("safety", "Safety"),
            ("prep", "Preparation"),
            ("tech", "Technical"),
        ],
        string="Tag",
        default="general",
        help="Category tag for this note.",
    )

class ClinicalImagingDeviceStudy(models.Model):
    _inherit = "clinical.imaging.device"
        
    imaging_count = fields.Integer(
        string="Imaging Count", compute="_compute_imaging_stats", store=False,
        help="Number of imaging records acquired using this device."
    )
    
    def _compute_imaging_stats(self):
        Imaging = self.env["clinical.imaging"]
        for rec in self:
            rec.imaging_count = Imaging.search_count([("device_id", "=", rec.id)])

    def _compute_imaging_stats(self):
        Imaging = self.env["clinical.imaging"]
        for rec in self:
            rec.imaging_count = Imaging.search_count([("device_id", "=", rec.id)])


    def action_open_imaging(self):
        self.ensure_one()
        return {
            "name": _("Imaging Records"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"search_default_groupby_patient": 1},
        }


# =============================================================================
# Soft links on Imaging to navigate to Studies
# =============================================================================
class ClinicalImaging(models.Model):
    _inherit = "clinical.imaging"

    study_ids = fields.One2many(
        "clinical.imaging.study",
        "imaging_id",
        string="Studies",
        help="DICOM studies acquired for this imaging.",
    )
    study_count = fields.Integer(
        string="Study Count",
        compute="_compute_study_count",
        store=False,
    )

    device_downtime_count = fields.Integer(
        string="Downtimes", compute="_compute_device_log_counts", store=False
    )
    device_calibration_count = fields.Integer(
        string="Calibrations/QC", compute="_compute_device_log_counts", store=False
    )

    def _compute_device_log_counts(self):
        Downtime = self.env["clinical.imaging.device.downtime"]
        Calib = self.env["clinical.imaging.device.calibration"]
        for rec in self:
            if rec.device_id:
                rec.device_downtime_count = Downtime.search_count([("device_id", "=", rec.device_id.id)])
                rec.device_calibration_count = Calib.search_count([("device_id", "=", rec.device_id.id)])
            else:
                rec.device_downtime_count = 0
                rec.device_calibration_count = 0

    def action_open_device_downtime(self):
        self.ensure_one()
        if not self.device_id:
            raise UserError(_("No device is linked to this imaging."))
        return {
            "name": _("Downtime Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.downtime",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.device_id.id)],
            "target": "current",
        }

    def action_open_device_calibration(self):
        self.ensure_one()
        if not self.device_id:
            raise UserError(_("No device is linked to this imaging."))
        return {
            "name": _("Calibration / QC Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.calibration",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.device_id.id)],
            "target": "current",
        }

    def _compute_study_count(self):
        for rec in self:
            rec.study_count = len(rec.study_ids)

    def action_open_studies(self):
        self.ensure_one()
        return {
            "name": _("Studies"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.study",
            "view_mode": "list,form,kanban",
            "domain": [("imaging_id", "=", self.id)],
            "target": "current",
            "context": {"default_imaging_id": self.id},
        }

    def action_create_study(self):
        """
        Convenience action to create a blank Study from the Imaging form.
        """
        self.ensure_one()
        study = self.env["clinical.imaging.study"].create({
            "imaging_id": self.id,
            "company_id": self.company_id.id,
            "modality": (self.imaging_type_id and self.imaging_type_id.modality) or False,
            "device_id": self.device_id.id if self.device_id else False,
            "dicom_accession_number": self.dicom_accession_number or False,
        })
        return {
            "name": _("Study"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.study",
            "view_mode": "form",
            "res_id": study.id,
            "target": "current",
        }

# \\\ PINDAHAN DARI File: clinical_imaging_device.py ///
# /// Digabungkan DIATAS \\\
# class ClinicalImaging(models.Model):
#     _inherit = "clinical.imaging"

    # device_downtime_count = fields.Integer(
    #     string="Downtimes", compute="_compute_device_log_counts", store=False
    # )
    # device_calibration_count = fields.Integer(
    #     string="Calibrations/QC", compute="_compute_device_log_counts", store=False
    # )

    # def _compute_device_log_counts(self):
    #     Downtime = self.env["clinical.imaging.device.downtime"]
    #     Calib = self.env["clinical.imaging.device.calibration"]
    #     for rec in self:
    #         if rec.device_id:
    #             rec.device_downtime_count = Downtime.search_count([("device_id", "=", rec.device_id.id)])
    #             rec.device_calibration_count = Calib.search_count([("device_id", "=", rec.device_id.id)])
    #         else:
    #             rec.device_downtime_count = 0
    #             rec.device_calibration_count = 0

    # def action_open_device_downtime(self):
    #     self.ensure_one()
    #     if not self.device_id:
    #         raise UserError(_("No device is linked to this imaging."))
    #     return {
    #         "name": _("Downtime Logs"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinical.imaging.device.downtime",
    #         "view_mode": "list,form",
    #         "domain": [("device_id", "=", self.device_id.id)],
    #         "target": "current",
    #     }

    # def action_open_device_calibration(self):
    #     self.ensure_one()
    #     if not self.device_id:
    #         raise UserError(_("No device is linked to this imaging."))
    #     return {
    #         "name": _("Calibration / QC Logs"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinical.imaging.device.calibration",
    #         "view_mode": "list,form",
    #         "domain": [("device_id", "=", self.device_id.id)],
    #         "target": "current",
    #     }
