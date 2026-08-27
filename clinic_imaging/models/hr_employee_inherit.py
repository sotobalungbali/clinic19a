# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers Mixin (safe checks)
# =============================================================================
class _ImagingEmployeeHelpersMixin(models.AbstractModel):
    _name = "clinical.imaging.employee.helpers.mixin"
    _description = "Imaging Employee Helpers Mixin"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_now(self):
        return fields.Datetime.now()

    def _dt_days_ago(self, days):
        return self._dt_now() - timedelta(days=days)


# =============================================================================
# Modality Tag for Staff Competency
# =============================================================================
class ClinicalImagingModalityTag(models.Model):
    _name = "clinical.imaging.modality.tag"
    _description = "Imaging Modality Tag"
    _order = "sequence, code"
    _check_company_auto = True

    name = fields.Char(string="Modality Name", required=True, help="Display name, e.g., 'CT', 'MRI'.")
    code = fields.Selection(
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
        string="Code",
        required=True,
        help="Standardized modality code."
    )
    sequence = fields.Integer(string="Sequence", default=10)
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Modality code must be unique per company.',
    )


# =============================================================================
# Staff Credential (License/Certification)
# =============================================================================
class ClinicalImagingStaffCredential(models.Model):
    _name = "clinical.imaging.staff.credential"
    _description = "Imaging Staff Credential"
    _order = "employee_id, credential_type, issue_date, id"
    _check_company_auto = True

    employee_id = fields.Many2one(
        "hr.employee", string="Employee",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="employee_id.company_id", store=True, readonly=True
    )
    credential_type = fields.Selection(
        [
            ("license", "Professional License"),
            ("board", "Board Certification"),
            ("training", "Training/CPD"),
            ("privilege", "Hospital Privilege"),
            ("other", "Other"),
        ],
        string="Credential Type",
        required=True,
        default="license",
    )
    name = fields.Char(
        string="Title / Credential Name",
        required=True,
        help="Credential title, e.g., 'Radiologist License', 'ARRT', 'Ultrasound Certification'."
    )
    number = fields.Char(string="Credential Number", help="Official license/certificate number.")
    issuer = fields.Char(string="Issuer / Authority")
    issue_date = fields.Date(string="Issue Date")
    expiry_date = fields.Date(string="Expiry Date")
    verified = fields.Boolean(string="Verified", help="Checked if HR has verified this credential.")
    attachment_id = fields.Many2one("ir.attachment", string="Attachment", help="Scan or digital certificate.")
    notes = fields.Text(string="Notes")

    status = fields.Selection(
        [
            ("valid", "Valid"),
            ("due", "Due Soon"),
            ("expired", "Expired"),
            ("unknown", "Unknown"),
        ],
        string="Status",
        compute="_compute_status",
        store=True,
    )
    days_to_expiry = fields.Integer(string="Days to Expiry", compute="_compute_status", store=True)

    @api.constrains("issue_date", "expiry_date")
    def _check_issue_expiry(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date and rec.expiry_date < rec.issue_date:
                raise ValidationError(_("Expiry Date cannot be earlier than Issue Date."))

    @api.depends("expiry_date")
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.expiry_date:
                rec.status = "unknown"
                rec.days_to_expiry = 0
                continue
            delta = (rec.expiry_date - today).days
            rec.days_to_expiry = delta
            if delta < 0:
                rec.status = "expired"
            elif delta <= 30:
                rec.status = "due"
            else:
                rec.status = "valid"


# =============================================================================
# hr.employee — Imaging extensions
# =============================================================================
class HrEmployee(models.Model, _ImagingEmployeeHelpersMixin):
    _inherit = "hr.employee"

    # -------------------------------------------------------------------------
    # Roles & Privileges (do NOT redefine is_doctor; assumed from clinic_hr/doctor)
    # -------------------------------------------------------------------------
    is_radiologist = fields.Boolean(
        string="Radiologist",
        help="Checked if this employee is a radiologist who can sign imaging results."
    )
    is_technologist = fields.Boolean(
        string="Imaging Technologist",
        help="Checked if this employee performs image acquisition."
    )
    is_sonographer = fields.Boolean(
        string="Sonographer",
        help="Checked if this employee performs ultrasound scans."
    )
    is_physicist = fields.Boolean(
        string="Medical Physicist",
        help="Checked if this employee handles QA/QC and dose audits."
    )
    is_imaging_nurse = fields.Boolean(
        string="Imaging Nurse",
        help="Checked if this employee provides nursing support for imaging (e.g., IV/contrast/sedation)."
    )
    imaging_active = fields.Boolean(
        string="Active in Imaging",
        default=True,
        help="Uncheck to exclude from imaging rosters and auto-assignments."
    )

    # Signing & Supervision
    can_sign_imaging_result = fields.Boolean(
        string="Can Sign Results",
        help="If checked, this user can finalize imaging results (subject to access rules)."
    )
    sign_policy = fields.Selection(
        [
            ("alone", "Sign Alone"),
            ("cosign_required", "Co-sign Required"),
            ("supervision_required", "Supervision Required"),
        ],
        string="Signing Policy",
        default="alone",
        help="Policy applied when this user signs reports."
    )
    co_signer_id = fields.Many2one(
        "hr.employee", string="Default Co-signer",
        domain=[("is_radiologist", "=", True)],
        help="If co-sign is required, this radiologist will be suggested."
    )

    # -------------------------------------------------------------------------
    # Competency & Preferences
    # -------------------------------------------------------------------------
    modality_tag_ids = fields.Many2many(
        "clinical.imaging.modality.tag",
        "clinical_imaging_modality_tag_employee_rel",
        "employee_id", "tag_id",
        string="Modality Competencies",
        help="Modalities this employee is qualified to perform/read."
    )
    device_ids = fields.Many2many(
        "clinical.imaging.device",
        "clinical_imaging_device_employee_rel",
        "employee_id", "device_id",
        string="Authorized Devices",
        help="Devices this staff is allowed/preferred to operate/read."
    )
    preferred_location = fields.Char(
        string="Preferred Location",
        help="Preferred radiology room/site for rostering."
    )
    max_daily_workload = fields.Integer(
        string="Max Daily Workload",
        default=40,
        help="Target maximum number of studies per day for this staff."
    )
    default_report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Default Report Template",
        help="Default report template when this staff authors a result."
    )
    worklist_assignment = fields.Selection(
        [
            ("manual", "Manual"),
            ("round_robin", "Round Robin"),
            ("load_based", "Load-based"),
            ("modality_based", "Modality-based"),
        ],
        string="Worklist Assignment",
        default="manual",
        help="Preferred assignment strategy for this staff."
    )

    # -------------------------------------------------------------------------
    # Signature & Identity
    # -------------------------------------------------------------------------
    signature_image = fields.Binary(
        string="Signature Image",
        attachment=True,
        help="Scanned or drawn signature image to display on reports."
    )
    signature_text = fields.Char(
        string="Signature Text",
        help="Textual signature (name with degrees/registrations)."
    )
    sign_pin = fields.Char(
        string="Signing PIN",
        help="Optional PIN required to sign imaging results. Keep confidential."
    )
    provider_identifier = fields.Char(
        string="Provider Identifier",
        help="National or local provider ID (e.g., NPI/STR/DOKTER ID)."
    )

    # -------------------------------------------------------------------------
    # Counters (rolling 30 days) & Today
    # -------------------------------------------------------------------------
    result_signed_30d = fields.Integer(
        string="Results Signed (30d)", compute="_compute_imaging_counters", store=False
    )
    avg_tat_acq_to_sign_30d = fields.Float(
        string="Avg TAT Acq→Sign (h, 30d)", compute="_compute_imaging_counters", store=False
    )
    pending_results_assigned = fields.Integer(
        string="Pending Results Assigned", compute="_compute_imaging_counters", store=False
    )
    studies_acquired_30d = fields.Integer(
        string="Studies Acquired (30d)", compute="_compute_imaging_counters", store=False
    )
    todays_worklist = fields.Integer(
        string="Today's Worklist", compute="_compute_imaging_counters", store=False
    )

    # -------------------------------------------------------------------------
    # Relations
    # -------------------------------------------------------------------------
    credential_ids = fields.One2many(
        "clinical.imaging.staff.credential", "employee_id",
        string="Credentials", copy=True
    )
    credential_count = fields.Integer(string="Credential Count", compute="_compute_counts", store=False)
    credential_due = fields.Integer(string="Credentials Due", compute="_compute_counts", store=False)
    credential_expired = fields.Integer(string="Credentials Expired", compute="_compute_counts", store=False)

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        for rec in self:
            rec.credential_count = len(rec.credential_ids)
            rec.credential_due = len(rec.credential_ids.filtered(lambda c: c.status == "due"))
            rec.credential_expired = len(rec.credential_ids.filtered(lambda c: c.status == "expired"))

    def _compute_imaging_counters(self):
        """
        Compute rolling 30-day productivity and today's worklist numbers.
        Safe if related models are not installed.
        """
        now = self._dt_now()
        start_30d = self._dt_days_ago(30)
        today_start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        today_end = today_start + timedelta(days=1, seconds=-1)

        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None

        for rec in self:
            # Defaults
            rec.result_signed_30d = 0
            rec.avg_tat_acq_to_sign_30d = 0.0
            rec.pending_results_assigned = 0
            rec.studies_acquired_30d = 0
            rec.todays_worklist = 0

            # Results: signed by this radiologist
            if Result and rec.is_radiologist:
                # Signed within last 30d
                domain_signed = [
                    ("author_doctor_id", "=", rec.id),
                    ("signed_datetime", ">=", start_30d),
                    ("signed_datetime", "<=", now),
                    ("state", "in", ["final", "amended"]),
                ] if self._has_field("clinical.imaging.result", "state") else [
                    ("author_doctor_id", "=", rec.id),
                    ("signed_datetime", ">=", start_30d),
                    ("signed_datetime", "<=", now),
                ]
                signed = Result.search(domain_signed, order="signed_datetime asc")
                rec.result_signed_30d = len(signed)

                # Avg TAT Acq->Sign
                if signed and Study:
                    hours = []
                    for r in signed:
                        st = Study.search([("imaging_id", "=", r.imaging_id.id)], limit=1, order="study_datetime asc")
                        if st and st.study_datetime and r.signed_datetime:
                            delta = fields.Datetime.to_datetime(r.signed_datetime) - fields.Datetime.to_datetime(st.study_datetime)
                            if delta.total_seconds() > 0:
                                hours.append(delta.total_seconds() / 3600.0)
                    rec.avg_tat_acq_to_sign_30d = round(sum(hours) / len(hours), 2) if hours else 0.0

                # Pending results assigned (not yet final)
                if self._has_field("clinical.imaging.result", "state"):
                    pending_states = ["draft", "in_review", "preliminary", "verified", "approved"]
                    rec.pending_results_assigned = Result.search_count([
                        ("author_doctor_id", "=", rec.id),
                        ("state", "in", pending_states),
                    ])
                else:
                    rec.pending_results_assigned = 0

                # Today's worklist (results targeting this radiologist by author or reviewer)
                domain_today = [
                    ("author_doctor_id", "=", rec.id),
                    ("create_date", ">=", today_start),
                    ("create_date", "<=", today_end),
                ]
                rec.todays_worklist = Result.search_count(domain_today)

            # Studies acquired by this technologist (30d)
            if Study and (rec.is_technologist or rec.is_sonographer):
                # Try to detect field 'acquired_by_id' or 'technologist_id' on Study
                tech_field = None
                for fname in ["acquired_by_id", "technologist_id", "operator_id"]:
                    if self._has_field("clinical.imaging.study", fname):
                        tech_field = fname
                        break
                if tech_field:
                    rec.studies_acquired_30d = Study.search_count([
                        (tech_field, "=", rec.id),
                        ("study_datetime", ">=", start_30d),
                        ("study_datetime", "<=", now),
                    ])
                else:
                    rec.studies_acquired_30d = 0

    # -------------------------------------------------------------------------
    # ACTIONS (Smart Buttons / Utilities)
    # -------------------------------------------------------------------------
    def _action_window(self, name, res_model, domain, view_mode="list,form"):
        self.ensure_one()
        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": res_model,
            "view_mode": view_mode,
            "domain": domain,
            "target": "current",
        }

    def action_open_my_results_pending(self):
        """Open Results assigned to me that are not yet final."""
        self.ensure_one()
        if not self.is_radiologist:
            raise UserError(_("Only radiologists have a results worklist."))
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        domain = [("author_doctor_id", "=", self.id)]
        if self._has_field("clinical.imaging.result", "state"):
            domain.append(("state", "in", ["draft", "in_review", "preliminary", "verified", "approved"]))
        return self._action_window(_("My Pending Results"), "clinical.imaging.result", domain)

    def action_open_my_results_signed_30d(self):
        """Open Results signed by me in the last 30 days."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        start_30d = self._dt_days_ago(30)
        domain = [
            ("author_doctor_id", "=", self.id),
            ("signed_datetime", ">=", start_30d),
            ("signed_datetime", "<=", self._dt_now()),
        ]
        return self._action_window(_("My Results (Last 30 days)"), "clinical.imaging.result", domain)

    def action_open_my_studies_acquired_30d(self):
        """Open Studies acquired by me in the last 30 days."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.study"):
            raise UserError(_("Imaging Study model is not available."))
        tech_field = None
        for fname in ["acquired_by_id", "technologist_id", "operator_id"]:
            if self._has_field("clinical.imaging.study", fname):
                tech_field = fname
                break
        if not tech_field:
            raise UserError(_("This database does not track technologist on Study."))
        start_30d = self._dt_days_ago(30)
        domain = [
            (tech_field, "=", self.id),
            ("study_datetime", ">=", start_30d),
            ("study_datetime", "<=", self._dt_now()),
        ]
        return self._action_window(_("My Acquired Studies (Last 30 days)"), "clinical.imaging.study", domain, view_mode="list,form,kanban")

    def action_open_credentials(self):
        self.ensure_one()
        return self._action_window(_("My Credentials"), "clinical.imaging.staff.credential", [("employee_id", "=", self.id)])

    def action_open_authorized_devices(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.device"):
            raise UserError(_("Imaging Device model is not available."))
        return self._action_window(_("Authorized Devices"), "clinical.imaging.device", [("id", "in", self.device_ids.ids)], view_mode="list,form,kanban")

    def action_open_today_worklist(self):
        """Open today's newly created Results assigned to me (for triage)."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        today_start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        today_end = today_start + timedelta(days=1, seconds=-1)
        domain = [
            ("author_doctor_id", "=", self.id),
            ("create_date", ">=", today_start),
            ("create_date", "<=", today_end),
        ]
        return self._action_window(_("Today's Worklist"), "clinical.imaging.result", domain)

    # -------------------------------------------------------------------------
    # DEFAULTING / INTEROP for other modules
    # -------------------------------------------------------------------------
    @api.onchange("is_radiologist")
    def _onchange_is_radiologist(self):
        for rec in self:
            if rec.is_radiologist:
                rec.can_sign_imaging_result = True
                # suggest report template from company default if empty
                if not rec.default_report_template_id and "clinical.imaging.report.template" in self.env:
                    tmpl = self.env["clinical.imaging.report.template"].search([
                        ("company_id", "=", rec.company_id.id),
                        ("is_default_company", "=", True),
                        ("active", "=", True),
                    ], limit=1)
                    if tmpl:
                        rec.default_report_template_id = tmpl.id

    # -------------------------------------------------------------------------
    # SQL Constraints (none for inherited model — use credential uniqueness)
    # -------------------------------------------------------------------------
