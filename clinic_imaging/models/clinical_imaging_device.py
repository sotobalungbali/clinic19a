# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re


# =============================================================================
# Clinical Imaging Device (extend full master with integrations & telemetry)
# =============================================================================
class ClinicalImagingDevice(models.Model):
    _name = "clinical.imaging.device"
    _description = "Clinical Imaging Device"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, modality, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Device Name", required=True, tracking=True,
        help="Human-friendly name of the device (e.g., 'MRI 1.5T Room A')."
    )
    code = fields.Char(
        string="Code", index=True, tracking=True,
        help="Short internal code for the device."
    )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(
        string="Active", default=True,
        help="Uncheck to archive the device."
    )

    # -------------------------------------------------------------------------
    # Technical Identity
    # -------------------------------------------------------------------------
    manufacturer = fields.Char(string="Manufacturer", help="Device manufacturer.")
    model_name = fields.Char(string="Model", help="Model/series name.")
    serial_number = fields.Char(string="Serial Number", help="Manufacturer serial number.", index=True)
    udi_di = fields.Char(string="UDI-DI", help="Unique Device Identifier - Device Identifier (if applicable).")
    software_version = fields.Char(string="Software Version")
    firmware_version = fields.Char(string="Firmware Version")
    install_date = fields.Date(string="Installation Date", help="Date when the device was installed.")
    warranty_expiry_date = fields.Date(string="Warranty Expiry")

    # -------------------------------------------------------------------------
    # Modality & Capabilities
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
        help="Primary modality of the device."
    )
    max_patient_weight_kg = fields.Float(
        string="Max Patient Weight (kg)",
        help="Maximum supported patient weight."
    )
    bore_diameter_cm = fields.Float(
        string="Bore Diameter (cm)",
        help="For MRI/CT devices, the bore diameter."
    )
    throughput_per_hour = fields.Float(
        string="Throughput (/hour)",
        help="Typical number of studies per hour under normal operation."
    )
    supports_contrast = fields.Boolean(
        string="Supports Contrast", default=True,
        help="If the device supports contrast workflows."
    )

    # -------------------------------------------------------------------------
    # Organization & Scheduling
    # -------------------------------------------------------------------------
    department_id = fields.Many2one(
        "hr.department", string="Department",
        help="Owning clinical/technical department."
    )
    room_id = fields.Many2one(
        "clinic.room", string="Room",
        help="Room where the device is installed (from ClinicOne Room & Device module)."
    )
    location = fields.Char(
        string="Location",
        help="Free-text location/room label if not using room records."
    )
    calendar_id = fields.Many2one(
        "resource.calendar", string="Operating Hours",
        help="Default working time used for scheduling and SLA."
    )

    # -------------------------------------------------------------------------
    # Connectivity (DICOM / Network)
    # -------------------------------------------------------------------------
    ip_address = fields.Char(string="IP Address", help="Device IP address.")
    dicom_supported = fields.Boolean(string="DICOM Supported", default=True)
    ae_title = fields.Char(
        string="AE Title",
        help="DICOM Application Entity Title (≤16 chars, uppercase, no spaces)."
    )
    dicom_port = fields.Integer(string="DICOM Port", help="TCP port used by the DICOM SCP.", default=104)
    dicom_tls = fields.Boolean(string="DICOM TLS", help="Enable TLS for DICOM association if supported.")

    # -------------------------------------------------------------------------
    # Maintenance & QC
    # -------------------------------------------------------------------------
    vendor_contact_id = fields.Many2one(
        "res.partner", string="Vendor",
        help="Vendor / service provider for maintenance."
    )
    last_maintenance_date = fields.Date(string="Last Maintenance")
    maintenance_interval_days = fields.Integer(
        string="Maintenance Interval (days)", default=180,
        help="Interval in days for preventive maintenance."
    )
    next_maintenance_date = fields.Date(
        string="Next Maintenance", compute="_compute_next_maintenance",
        store=True
    )

    last_qc_date = fields.Date(string="Last QC/QA")
    qc_interval_days = fields.Integer(
        string="QC Interval (days)", default=30,
        help="Interval for quality control tests."
    )
    next_qc_date = fields.Date(
        string="Next QC/QA", compute="_compute_next_qc", store=True
    )
    qc_status = fields.Selection(
        [
            ("ok", "OK"),
            ("due", "Due"),
            ("overdue", "Overdue"),
        ],
        string="QC Status", compute="_compute_qc_status", store=True
    )

    # -------------------------------------------------------------------------
    # Operational State
    # -------------------------------------------------------------------------
    status = fields.Selection(
        [
            ("operational", "Operational"),
            ("maintenance", "Under Maintenance"),
            ("down", "Down"),
            ("retired", "Retired"),
        ],
        string="Status", default="operational", tracking=True, index=True,
        help="Current operational status of the device."
    )
    status_note = fields.Char(string="Status Note", help="Short note for current status.")
    retired_date = fields.Date(string="Retired Date")

    # -------------------------------------------------------------------------
    # Usage & Uptime Stats
    # -------------------------------------------------------------------------
    # imaging_count = fields.Integer(
    #     string="Imaging Count", compute="_compute_imaging_stats", store=False,
    #     help="Number of imaging records acquired using this device."
    # )
    downtime_hours_total = fields.Float(
        string="Total Downtime (h)", compute="_compute_downtime_stats", store=False
    )
    uptime_ratio_30d = fields.Float(
        string="Uptime Ratio (30d)", compute="_compute_downtime_stats", store=False,
        help="Approximate uptime ratio over the last 30 days."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("last_maintenance_date", "maintenance_interval_days")
    def _compute_next_maintenance(self):
        for rec in self:
            if rec.last_maintenance_date and rec.maintenance_interval_days:
                rec.next_maintenance_date = fields.Date.add(
                    rec.last_maintenance_date, days=int(rec.maintenance_interval_days)
                )
            else:
                rec.next_maintenance_date = False

    @api.depends("last_qc_date", "qc_interval_days")
    def _compute_next_qc(self):
        for rec in self:
            if rec.last_qc_date and rec.qc_interval_days:
                rec.next_qc_date = fields.Date.add(rec.last_qc_date, days=int(rec.qc_interval_days))
            else:
                rec.next_qc_date = False

    @api.depends("next_qc_date")
    def _compute_qc_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.next_qc_date:
                rec.qc_status = "due"
            else:
                if rec.next_qc_date < today:
                    rec.qc_status = "overdue"
                elif (rec.next_qc_date - today).days <= 3:
                    rec.qc_status = "due"
                else:
                    rec.qc_status = "ok"

    # def _compute_imaging_stats(self):
    #     Imaging = self.env["clinical.imaging"]
    #     for rec in self:
    #         rec.imaging_count = Imaging.search_count([("device_id", "=", rec.id)])

    def _compute_downtime_stats(self):
        Downtime = self.env["clinical.imaging.device.downtime"]
        now = fields.Datetime.now()
        for rec in self:
            # Total downtime (all time)
            all_dt = Downtime.search([("device_id", "=", rec.id), ("state", "=", "closed")])
            rec.downtime_hours_total = sum(all_dt.mapped("duration_hours"))

            # Uptime ratio for last 30 days (approx = 30*24 - downtime)
            start = fields.Datetime.subtract(now, days=30)
            last30 = Downtime.search([
                ("device_id", "=", rec.id),
                ("state", "=", "closed"),
                ("end_datetime", ">=", start),
            ])
            dt_hours_30 = 0.0
            for d in last30:
                dt_hours_30 += d._duration_hours_window(start, now)
            total_hours = 30.0 * 24.0
            rec.uptime_ratio_30d = max(0.0, min(1.0, (total_hours - dt_hours_30) / total_hours)) if total_hours else 1.0

    # -------------------------------------------------------------------------
    # ONCHANGE & VALIDATION
    # -------------------------------------------------------------------------
    @api.onchange("ae_title")
    def _onchange_ae_title_normalize(self):
        for rec in self:
            if rec.ae_title:
                rec.ae_title = rec.ae_title.strip().upper().replace(" ", "")

    @api.constrains("serial_number", "company_id")
    def _check_unique_serial(self):
        for rec in self:
            if rec.serial_number:
                domain = [("serial_number", "=", rec.serial_number), ("company_id", "=", rec.company_id.id)]
                if self.search_count(domain) > 1:
                    raise ValidationError(_("Serial Number must be unique per company."))

    @api.constrains("dicom_port")
    def _check_port_range(self):
        for rec in self:
            if rec.dicom_port is not None and (rec.dicom_port < 1 or rec.dicom_port > 65535):
                raise ValidationError(_("DICOM Port must be in range 1..65535."))

    @api.constrains("ip_address")
    def _check_ip_format(self):
        ip_regex = r"^(\d{1,3}\.){3}\d{1,3}$"
        for rec in self:
            if rec.ip_address and not re.match(ip_regex, rec.ip_address):
                raise ValidationError(_("IP Address appears invalid (expect IPv4 dotted decimal)."))

    @api.constrains("ae_title")
    def _check_ae_title(self):
        for rec in self:
            if rec.ae_title:
                if len(rec.ae_title) > 16:
                    raise ValidationError(_("AE Title must be 16 characters or fewer."))
                if " " in rec.ae_title:
                    raise ValidationError(_("AE Title cannot contain spaces."))
                if not rec.ae_title.isupper():
                    raise ValidationError(_("AE Title must be uppercase."))

    @api.constrains("status", "active")
    def _check_retired_archival(self):
        for rec in self:
            if rec.status == "retired" and rec.active:
                # Not hard error; gently align flags
                rec.active = False

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_set_operational(self):
        for rec in self:
            rec.status = "operational"
            rec.status_note = False
            rec.message_post(body=_("Device set to Operational."))

    def action_set_maintenance(self):
        for rec in self:
            rec.status = "maintenance"
            rec.message_post(body=_("Device set to Under Maintenance."))

    def action_set_down(self, reason=None):
        for rec in self:
            rec.status = "down"
            if reason:
                rec.status_note = reason
            rec.message_post(body=_("Device set to Down. %s") % (reason or ""))

    def action_retire(self, note=None):
        for rec in self:
            rec.status = "retired"
            rec.active = False
            rec.retired_date = fields.Date.context_today(self)
            if note:
                rec.status_note = note
            rec.message_post(body=_("Device retired."))

    # def action_open_imaging(self):
    #     self.ensure_one()
    #     return {
    #         "name": _("Imaging Records"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinical.imaging",
    #         "view_mode": "list,form,kanban,calendar",
    #         "domain": [("device_id", "=", self.id)],
    #         "target": "current",
    #         "context": {"search_default_groupby_patient": 1},
    #     }

    def action_open_downtime(self):
        self.ensure_one()
        return {
            "name": _("Downtime Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.downtime",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"default_device_id": self.id},
        }

    def action_open_calibration(self):
        self.ensure_one()
        return {
            "name": _("Calibration / QC Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.calibration",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"default_device_id": self.id},
        }

    def action_open_connectivity(self):
        self.ensure_one()
        return {
            "name": _("Connectivity Endpoints"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.connectivity",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"default_device_id": self.id},
        }

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "code", "modality")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _("Imaging Device")]
            if rec.code:
                parts.append("[%s]" % rec.code)
            if rec.modality:
                parts.append("(%s)" % rec.modality)
            rec.display_name = " ".join(parts)

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Device code must be unique per company.',
    )
    _serial_company_unique = models.Constraint(
        'unique(serial_number, company_id)',
        'Serial number must be unique per company.',
    )


# =============================================================================
# Device Downtime Log
# =============================================================================
class ClinicalImagingDeviceDowntime(models.Model):
    _name = "clinical.imaging.device.downtime"
    _description = "Imaging Device Downtime"
    _order = "start_datetime desc, id desc"
    _check_company_auto = True

    device_id = fields.Many2one(
        "clinical.imaging.device", string="Device",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="device_id.company_id", store=True, readonly=True
    )
    start_datetime = fields.Datetime(string="Start", required=True, default=fields.Datetime.now)
    end_datetime = fields.Datetime(string="End", help="Leave empty if ongoing.")
    duration_hours = fields.Float(
        string="Duration (h)", compute="_compute_duration_hours", store=True
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("in_progress", "In Progress"),
            ("closed", "Closed"),
        ],
        string="Status", default="open", index=True, tracking=True
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Severity", default="medium"
    )
    reason = fields.Char(string="Reason", help="Short reason for downtime.")
    description = fields.Text(string="Description")
    reported_by = fields.Many2one("res.users", string="Reported By", default=lambda self: self.env.user)
    ticket_ref = fields.Char(string="Ticket Reference", help="Internal or vendor ticket number.")
    attachment_count = fields.Integer(
        string="Attachments", compute="_compute_attachment_count", store=False
    )

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration_hours(self):
        for rec in self:
            start = rec.start_datetime
            end = rec.end_datetime or fields.Datetime.now()
            if start and end and end >= start:
                delta = fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0

    def _duration_hours_window(self, window_start, window_end):
        """Helper for parent device: partial duration within [window_start, window_end]."""
        self.ensure_one()
        s = fields.Datetime.to_datetime(self.start_datetime)
        e = fields.Datetime.to_datetime(self.end_datetime or fields.Datetime.now())
        ws = fields.Datetime.to_datetime(window_start)
        we = fields.Datetime.to_datetime(window_end)
        if e <= ws or s >= we:
            return 0.0
        overlap_start = max(s, ws)
        overlap_end = min(e, we)
        if overlap_end <= overlap_start:
            return 0.0
        return (overlap_end - overlap_start).total_seconds() / 3600.0

    @api.constrains("end_datetime", "start_datetime")
    def _check_end_after_start(self):
        for rec in self:
            if rec.end_datetime and rec.start_datetime and rec.end_datetime < rec.start_datetime:
                raise ValidationError(_("End must be on or after Start."))

    def action_close(self):
        for rec in self:
            if rec.state == "closed":
                continue
            if not rec.end_datetime:
                rec.end_datetime = fields.Datetime.now()
            rec.state = "closed"
            rec.device_id.message_post(body=_("Downtime closed (%s h).") % round(rec.duration_hours, 2))

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

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", self._name), ("res_id", "=", rec.id)]
            )


# =============================================================================
# Device Calibration / QC Log
# =============================================================================
class ClinicalImagingDeviceCalibration(models.Model):
    _name = "clinical.imaging.device.calibration"
    _description = "Imaging Device Calibration / QC"
    _order = "date desc, id desc"
    _check_company_auto = True

    device_id = fields.Many2one(
        "clinical.imaging.device", string="Device",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="device_id.company_id", store=True, readonly=True
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    type = fields.Selection(
        [
            ("install", "Installation Acceptance"),
            ("preventive", "Preventive Maintenance QC"),
            ("periodic", "Periodic QC"),
            ("postrepair", "Post-Repair QC"),
            ("dosecheck", "Dose Check"),
            ("other", "Other"),
        ],
        string="Type", default="periodic", required=True
    )
    passed = fields.Boolean(string="Passed", default=True)
    findings = fields.Text(string="Findings / Notes")
    attachment = fields.Binary(string="Report Attachment", attachment=True)
    attachment_filename = fields.Char(string="File Name")
    performed_by = fields.Many2one("hr.employee", string="Performed By",
                                   help="Technician or engineer who performed the QC/calibration.")
    next_due_date = fields.Date(string="Next Due Date", help="Next suggested QC/calibration date.")
    reference_measure = fields.Char(
        string="Reference Measure",
        help="Optional summarized metrics (e.g., calibration offsets)."
    )

    @api.constrains("next_due_date", "date")
    def _check_next_due_after_date(self):
        for rec in self:
            if rec.next_due_date and rec.date and rec.next_due_date < rec.date:
                raise ValidationError(_("Next Due Date must be on or after the QC/Calibration Date."))


# =============================================================================
# Device Connectivity (DICOM endpoints, etc.)
# =============================================================================
class ClinicalImagingDeviceConnectivity(models.Model):
    _name = "clinical.imaging.device.connectivity"
    _description = "Imaging Device Connectivity"
    _order = "device_id, ae_title, host, port"
    _check_company_auto = True

    device_id = fields.Many2one(
        "clinical.imaging.device", string="Device",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="device_id.company_id", store=True, readonly=True
    )

    # Endpoint definition
    role = fields.Selection(
        [
            ("scp", "Storage SCP"),
            ("scu", "Storage SCU"),
            ("qrs", "Query/Retrieve SCP"),
            ("qrq", "Query/Retrieve SCU"),
            ("worklist_scp", "MWL SCP"),
            ("print_scp", "Print SCP"),
            ("other", "Other"),
        ],
        string="DICOM Role", default="scp", required=True
    )
    ae_title = fields.Char(
        string="AE Title", required=True,
        help="AE Title for this endpoint (≤16 chars, uppercase, no spaces)."
    )
    host = fields.Char(string="Host/IP", required=True)
    port = fields.Integer(string="Port", required=True, default=104)
    use_tls = fields.Boolean(string="Use TLS")
    description = fields.Char(string="Description")
    is_default = fields.Boolean(
        string="Default Endpoint", default=False,
        help="Mark as default endpoint for this device/role."
    )

    @api.constrains("port")
    def _check_port_range(self):
        for rec in self:
            if rec.port < 1 or rec.port > 65535:
                raise ValidationError(_("Port must be in range 1..65535."))

    @api.constrains("ae_title")
    def _check_ae_title(self):
        for rec in self:
            if rec.ae_title:
                if len(rec.ae_title) > 16:
                    raise ValidationError(_("AE Title must be 16 characters or fewer."))
                if " " in rec.ae_title:
                    raise ValidationError(_("AE Title cannot contain spaces."))
                if not rec.ae_title.isupper():
                    raise ValidationError(_("AE Title must be uppercase."))

    _endpoint_unique = models.Constraint(
        'unique(device_id, ae_title, host, port, company_id)',
        'An identical endpoint already exists for this device.',
    )

# DIPINDAH KE file clinical_imaging_study.py
# =============================================================================
# Soft links on Imaging to navigate back to Device logs (smart buttons)
# =============================================================================
# class ClinicalImaging(models.Model):
#     _inherit = "clinical.imaging"

#     device_downtime_count = fields.Integer(
#         string="Downtimes", compute="_compute_device_log_counts", store=False
#     )
#     device_calibration_count = fields.Integer(
#         string="Calibrations/QC", compute="_compute_device_log_counts", store=False
#     )

#     def _compute_device_log_counts(self):
#         Downtime = self.env["clinical.imaging.device.downtime"]
#         Calib = self.env["clinical.imaging.device.calibration"]
#         for rec in self:
#             if rec.device_id:
#                 rec.device_downtime_count = Downtime.search_count([("device_id", "=", rec.device_id.id)])
#                 rec.device_calibration_count = Calib.search_count([("device_id", "=", rec.device_id.id)])
#             else:
#                 rec.device_downtime_count = 0
#                 rec.device_calibration_count = 0

#     def action_open_device_downtime(self):
#         self.ensure_one()
#         if not self.device_id:
#             raise UserError(_("No device is linked to this imaging."))
#         return {
#             "name": _("Downtime Logs"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.device.downtime",
#             "view_mode": "list,form",
#             "domain": [("device_id", "=", self.device_id.id)],
#             "target": "current",
#         }

#     def action_open_device_calibration(self):
#         self.ensure_one()
#         if not self.device_id:
#             raise UserError(_("No device is linked to this imaging."))
#         return {
#             "name": _("Calibration / QC Logs"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.device.calibration",
#             "view_mode": "list,form",
#             "domain": [("device_id", "=", self.device_id.id)],
#             "target": "current",
#         }
