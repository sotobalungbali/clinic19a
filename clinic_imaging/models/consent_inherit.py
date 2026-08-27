# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers (safe checks & utilities)
# =============================================================================
class _ImagingConsentHelpers(models.AbstractModel):
    _name = "clinical.imaging.consent.helpers"
    _description = "Imaging Consent Helpers"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_now(self):
        return fields.Datetime.now()

    def _today(self):
        return fields.Date.context_today(self)


# =============================================================================
# Consent Template (for Imaging)
# =============================================================================
class ClinicalImagingConsentTemplate(models.Model):
    _name = "clinical.imaging.consent.template"
    _description = "Imaging Consent Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(string="Template Name", required=True, tracking=True)
    code = fields.Char(string="Code", index=True, help="Short unique code (e.g., 'CONSENT_CT_CONTRAST').")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    scope = fields.Selection(
        [
            ("imaging_general", "General Imaging"),
            ("contrast", "Contrast Media"),
            ("mri_safety", "MRI Safety"),
            ("radiation_exposure", "Radiation Exposure"),
            ("sedation_anesthesia", "Sedation/Anesthesia"),
            ("ultrasound_procedure", "Ultrasound Procedure"),
            ("interventional", "Interventional Procedure"),
        ],
        string="Scope",
        required=True,
        default="imaging_general",
        help="Defines the consent category; used to determine applicability."
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
        help="If set, this template is intended for a specific modality."
    )
    imaging_type_ids = fields.Many2many(
        "clinical.imaging.type",
        "clinical_imaging_consent_template_type_rel",
        "template_id", "type_id",
        string="Imaging Types",
        help="Restrict applicability to selected imaging types (leave empty for all)."
    )
    default_validity_days = fields.Integer(
        string="Default Validity (days)", default=90,
        help="Default validity period from the signed date."
    )

    require_patient_signature = fields.Boolean(string="Require Patient Signature", default=True)
    require_staff_signature = fields.Boolean(string="Require Staff Signature", default=False)
    require_doctor_signature = fields.Boolean(string="Require Doctor Signature", default=False)

    body_html = fields.Html(
        string="Body (HTML)",
        sanitize=False,
        help="Main consent text. Can be rendered in the form using QWeb/HTML."
    )
    disclaimer = fields.Text(string="Disclaimer / Notes")

    question_ids = fields.One2many(
        "clinical.imaging.consent.template.question", "template_id",
        string="Questions", copy=True
    )

    @api.constrains("code")
    def _check_code_upper(self):
        for rec in self:
            if rec.code and rec.code.strip() != rec.code.strip().upper():
                rec.code = rec.code.strip().upper()

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Template Code must be unique per company.',
    )


class ClinicalImagingConsentTemplateQuestion(models.Model):
    _name = "clinical.imaging.consent.template.question"
    _description = "Imaging Consent Template Question"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one("clinical.imaging.consent.template", string="Template", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Company", related="template_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10)
    code = fields.Char(string="Code", help="Short code (unique per template).")
    text = fields.Char(string="Question Text", required=True)
    qtype = fields.Selection(
        [
            ("boolean", "Yes/No"),
            ("text", "Text"),
            ("select", "Selection"),
        ],
        string="Type", required=True, default="boolean"
    )
    selection_options = fields.Text(
        string="Selection Options",
        help="For 'Selection' type, provide one option per line."
    )
    required = fields.Boolean(string="Required", default=False)
    critical = fields.Boolean(
        string="Critical",
        help="If checked and answered 'Yes' (or specific option), this may raise an alert."
    )
    # defaults
    default_boolean = fields.Boolean(string="Default Yes")
    default_text = fields.Char(string="Default Text")
    default_selection = fields.Char(string="Default Selection")

    _code_template_unique = models.Constraint(
        'unique(code, template_id)',
        'Question Code must be unique per template.',
    )


# =============================================================================
# Inherit clinic.consent — Imaging-specific extensions
# =============================================================================
class ClinicConsent(models.Model, _ImagingConsentHelpers):
    _inherit = "clinic.consent.form"

    # -------------------------------------------------------------------------
    # Imaging Context & Links
    # -------------------------------------------------------------------------
    imaging_template_id = fields.Many2one(
        "clinical.imaging.consent.template",
        string="Imaging Consent Template",
        help="Template applied to this consent."
    )
    imaging_scope = fields.Selection(
        related="imaging_template_id.scope",
        string="Imaging Scope",
        store=False,
        readonly=True
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
        help="Modality this consent relates to."
    )
    imaging_type_id = fields.Many2one("clinical.imaging.type", string="Imaging Type")
    device_id = fields.Many2one("clinical.imaging.device", string="Device")

    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    encounter_id = fields.Many2one("clinic.encounter", string="Clinical Encounter")
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment")
    prescription_order_id = fields.Many2one("clinic.emar.order", string="Prescription Order")

    imaging_request_id = fields.Many2one("clinical.imaging.request", string="Imaging Request", index=True)
    imaging_id = fields.Many2one("clinical.imaging", string="Imaging Record")
    imaging_result_id = fields.Many2one("clinical.imaging.result", string="Imaging Result")

    # -------------------------------------------------------------------------
    # Patient/Staff/Doctor Signatures (digital)
    # -------------------------------------------------------------------------
    patient_signature = fields.Binary(string="Patient Signature", attachment=True)
    patient_signed_datetime = fields.Datetime(string="Patient Signed At")
    patient_signed_by_partner_id = fields.Many2one("res.partner", string="Patient (Signer)")
    patient_signed_by_user_id = fields.Many2one("res.users", string="Captured By (User)")
    patient_signed_ip = fields.Char(string="Signer IP")

    staff_signature = fields.Binary(string="Staff Signature", attachment=True)
    staff_signed_datetime = fields.Datetime(string="Staff Signed At")
    staff_employee_id = fields.Many2one("hr.employee", string="Staff (Witness/Operator)")

    doctor_signature = fields.Binary(string="Doctor Signature", attachment=True)
    doctor_signed_datetime = fields.Datetime(string="Doctor Signed At")
    doctor_employee_id = fields.Many2one("hr.employee", string="Doctor (Supervisor)", domain=[("is_doctor", "=", True)])

    # -------------------------------------------------------------------------
    # Validity & State
    # -------------------------------------------------------------------------
    validity_from = fields.Date(string="Validity From", help="Usually the date the patient signed.")
    validity_to = fields.Date(string="Validity To")
    validity_days = fields.Integer(string="Validity (days)", default=0, help="If >0, used to compute Validity To.")
    is_expired = fields.Boolean(string="Expired", compute="_compute_validity", store=False)
    is_revoked = fields.Boolean(string="Revoked")
    revoked_datetime = fields.Datetime(string="Revoked At")
    revoked_by_user_id = fields.Many2one("res.users", string="Revoked By")
    revoked_reason = fields.Text(string="Revocation Reason")

    imaging_body_html = fields.Html(
        string="Rendered Body (HTML)",
        sanitize=False,
        help="Optional rendered HTML for the consent text. Can be filled from template."
    )

    # Questions/Answers captured for this consent (from template)
    answer_ids = fields.One2many("clinical.imaging.consent.answer", "consent_id", string="Answers", copy=True)
    required_answer_pending = fields.Boolean(string="Required Questions Pending", compute="_compute_required_pending", store=False)

    # -------------------------------------------------------------------------
    # Display helpers (computed patient if base model doesn't provide)
    # -------------------------------------------------------------------------
    consent_patient_id = fields.Many2one("res.partner", string="Patient (Resolved)", compute="_compute_consent_patient", store=False)

    # -------------------------------------------------------------------------
    # Constraints & Computes
    # -------------------------------------------------------------------------
    @api.constrains("validity_from", "validity_to")
    def _check_validity_dates(self):
        for rec in self:
            if rec.validity_from and rec.validity_to and rec.validity_to < rec.validity_from:
                raise ValidationError(_("Validity To cannot be earlier than Validity From."))

    @api.depends("validity_from", "validity_to", "validity_days")
    def _compute_validity(self):
        today = self._today()
        for rec in self:
            # derive validity_to if missing but days set
            if rec.validity_from and rec.validity_days and not rec.validity_to:
                rec.validity_to = rec.validity_from + timedelta(days=int(rec.validity_days))
            rec.is_expired = bool(rec.validity_to and rec.validity_to < today)

    def _compute_required_pending(self):
        for rec in self:
            pending = False
            # if template defines required questions, ensure they are answered
            if rec.imaging_template_id and rec.imaging_template_id.question_ids:
                # build map by code if present
                req_questions = rec.imaging_template_id.question_ids.filtered(lambda q: q.required)
                if req_questions:
                    # answers matched by question_id or code
                    answered_codes = set()
                    for ans in rec.answer_ids:
                        if ans.question_id and ans._is_answer_filled():
                            answered_codes.add(ans.question_id.code or ans.question_id.id)
                        elif ans.code and ans._is_value_filled():
                            answered_codes.add(ans.code)
                    for q in req_questions:
                        key = q.code or q.id
                        if key not in answered_codes:
                            pending = True
                            break
            rec.required_answer_pending = pending

    def _compute_consent_patient(self):
        for rec in self:
            patient = False
            # First, try base model's patient_id if exists
            if self._has_field("clinic.consent.form", "patient_id") and getattr(rec, "patient_id", False):
                patient = rec.patient_id
            # Derive from linked objects
            if not patient and rec.imaging_request_id and self._has_field("clinical.imaging.request", "patient_id"):
                patient = rec.imaging_request_id.patient_id
            if not patient and rec.encounter_id and self._has_field("clinic.encounter", "patient_id"):
                patient = rec.encounter_id.patient_id
            if not patient and rec.treatment_id and self._has_field("clinic.treatment", "patient_id"):
                patient = rec.treatment_id.patient_id
            if not patient and rec.appointment_id and self._has_field("clinic.appointment", "patient_id"):
                patient = rec.appointment_id.patient_id
            if not patient and rec.imaging_id and self._has_field("clinical.imaging", "patient_id"):
                patient = rec.imaging_id.patient_id
            if not patient and rec.imaging_result_id and self._has_field("clinical.imaging.result", "patient_id"):
                patient = rec.imaging_result_id.patient_id
            rec.consent_patient_id = patient.id if patient else False

    @api.constrains("imaging_request_id", "imaging_id", "imaging_result_id")
    def _check_patient_consistency(self):
        """Ensure the consent patient (resolved) matches linked imaging objects if their patient is known."""
        for rec in self:
            pat = rec.consent_patient_id
            if not pat:
                continue
            # request
            if rec.imaging_request_id and self._has_field("clinical.imaging.request", "patient_id"):
                if rec.imaging_request_id.patient_id and rec.imaging_request_id.patient_id.id != pat.id:
                    raise ValidationError(_("Patient on the Imaging Request does not match the consent patient."))
            # imaging
            if rec.imaging_id and self._has_field("clinical.imaging", "patient_id"):
                if rec.imaging_id.patient_id and rec.imaging_id.patient_id.id != pat.id:
                    raise ValidationError(_("Patient on the Imaging record does not match the consent patient."))
            # result
            if rec.imaging_result_id and self._has_field("clinical.imaging.result", "patient_id"):
                if rec.imaging_result_id.patient_id and rec.imaging_result_id.patient_id.id != pat.id:
                    raise ValidationError(_("Patient on the Imaging Result does not match the consent patient."))

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    def write(self, vals):
        # Prevent destructive change after signing unless revoking
        locked_fields = {"imaging_template_id", "modality", "imaging_type_id", "device_id"}
        if any(f in vals for f in locked_fields):
            for rec in self:
                if rec.patient_signed_datetime or rec.staff_signed_datetime or rec.doctor_signed_datetime:
                    raise UserError(_("Cannot change core imaging fields after the consent has been signed. Revoke or duplicate instead."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.patient_signed_datetime or rec.staff_signed_datetime or rec.doctor_signed_datetime:
                raise UserError(_("Signed consents cannot be deleted. Revoke instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # Apply template ⇒ populate HTML & questions
    # -------------------------------------------------------------------------
    def action_apply_imaging_template(self):
        for rec in self:
            if not rec.imaging_template_id:
                raise UserError(_("Please choose an Imaging Consent Template first."))
            # Fill HTML body if empty
            if not rec.imaging_body_html and rec.imaging_template_id.body_html:
                rec.imaging_body_html = rec.imaging_template_id.body_html
            # Derive modality if not set
            if not rec.modality and rec.imaging_template_id.modality:
                rec.modality = rec.imaging_template_id.modality
            # Populate questions (replace existing answers)
            rec.answer_ids.unlink()
            lines = []
            for q in rec.imaging_template_id.question_ids.sorted("sequence"):
                val = {
                    "consent_id": rec.id,
                    "template_id": rec.imaging_template_id.id,
                    "question_id": q.id,
                    "code": q.code or False,
                    "text": q.text,
                    "qtype": q.qtype,
                    "required": q.required,
                    "critical": q.critical,
                    "selection_options": q.selection_options,
                }
                # defaults
                if q.qtype == "boolean":
                    val["answer_boolean"] = q.default_boolean
                elif q.qtype == "text":
                    val["answer_text"] = q.default_text or ""
                elif q.qtype == "select":
                    val["answer_selection"] = q.default_selection or ""
                lines.append((0, 0, val))
            if lines:
                rec.write({"answer_ids": lines})
        return True

    # -------------------------------------------------------------------------
    # Signing & Revocation
    # -------------------------------------------------------------------------
    def _check_ready_to_sign(self, role="patient"):
        for rec in self:
            # Required answers must be completed
            if rec.required_answer_pending:
                raise UserError(_("Please complete all required questions before signing."))
            # Template signature requirements
            tmpl = rec.imaging_template_id
            if role == "patient" and tmpl and tmpl.require_patient_signature is False:
                raise UserError(_("This template does not require a patient signature."))
            if role == "staff" and tmpl and tmpl.require_staff_signature is False:
                raise UserError(_("This template does not require a staff signature."))
            if role == "doctor" and tmpl and tmpl.require_doctor_signature is False:
                raise UserError(_("This template does not require a doctor signature."))
            # Already revoked/expired?
            if rec.is_revoked:
                raise UserError(_("This consent has been revoked."))
            # ok

    def action_sign_patient(self, signature=None, signer_partner_id=False, signer_user_id=False, signer_ip=None):
        for rec in self:
            rec._check_ready_to_sign("patient")
            vals = {
                "patient_signed_datetime": self._dt_now(),
                "validity_from": rec.validity_from or fields.Date.context_today(self),
            }
            if signature:
                vals["patient_signature"] = signature
            if signer_partner_id:
                vals["patient_signed_by_partner_id"] = signer_partner_id
            if signer_user_id:
                vals["patient_signed_by_user_id"] = signer_user_id
            if signer_ip:
                vals["patient_signed_ip"] = signer_ip
            # compute validity_to if validity_days set
            if rec.validity_days and not rec.validity_to:
                vals["validity_to"] = (vals["validity_from"] or fields.Date.context_today(self)) + timedelta(days=int(rec.validity_days))
            rec.write(vals)
            rec.message_post(body=_("Patient signed the consent."))

    def action_sign_staff(self, signature=None, staff_employee_id=False):
        for rec in self:
            rec._check_ready_to_sign("staff")
            vals = {"staff_signed_datetime": self._dt_now()}
            if signature:
                vals["staff_signature"] = signature
            if staff_employee_id:
                vals["staff_employee_id"] = staff_employee_id
            rec.write(vals)
            rec.message_post(body=_("Staff signed the consent."))

    def action_sign_doctor(self, signature=None, doctor_employee_id=False):
        for rec in self:
            rec._check_ready_to_sign("doctor")
            vals = {"doctor_signed_datetime": self._dt_now()}
            if signature:
                vals["doctor_signature"] = signature
            if doctor_employee_id:
                vals["doctor_employee_id"] = doctor_employee_id
            rec.write(vals)
            rec.message_post(body=_("Doctor signed the consent."))

    def action_revoke(self, reason=None):
        for rec in self:
            if rec.is_revoked:
                continue
            rec.is_revoked = True
            rec.revoked_datetime = self._dt_now()
            rec.revoked_by_user_id = self.env.user
            rec.revoked_reason = reason or ""
            rec.message_post(body=_("Consent revoked. %s") % (reason or ""))

    # -------------------------------------------------------------------------
    # Convenience checks used by other modules (Request/Result)
    # -------------------------------------------------------------------------
    def is_fully_valid(self):
        """Return True if signatures required by template are present, not expired, not revoked."""
        self.ensure_one()
        if self.is_revoked or self.is_expired:
            return False
        tmpl = self.imaging_template_id
        if not tmpl:
            return True
        if tmpl.require_patient_signature and not self.patient_signed_datetime:
            return False
        if tmpl.require_staff_signature and not self.staff_signed_datetime:
            return False
        if tmpl.require_doctor_signature and not self.doctor_signed_datetime:
            return False
        return True

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------
    @api.depends(
        "name",
        "imaging_template_id",
        "modality",
        "imaging_type_id",
        "validity_to",
    )
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            base = rec.display_name or rec.name or _("Consent")
            extras = []
            if rec.imaging_template_id:
                extras.append(rec.imaging_template_id.code or rec.imaging_template_id.display_name)
            if rec.modality:
                extras.append(rec.modality)
            if rec.imaging_type_id:
                extras.append(rec.imaging_type_id.display_name)
            if rec.validity_to:
                extras.append(_("valid until %s") % fields.Date.to_string(rec.validity_to))
            if extras:
                rec.display_name = f"{base} [{', '.join(extras)}]"


# =============================================================================
# Answers captured from Consent (instantiated from template)
# =============================================================================
class ClinicalImagingConsentAnswer(models.Model):
    _name = "clinical.imaging.consent.answer"
    _description = "Imaging Consent Answer"
    _order = "consent_id, sequence, id"
    _check_company_auto = True

    consent_id = fields.Many2one("clinic.consent.form", string="Consent", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Company", related="consent_id.company_id", store=True, readonly=True)

    template_id = fields.Many2one("clinical.imaging.consent.template", string="Template", help="For traceability.")
    question_id = fields.Many2one("clinical.imaging.consent.template.question", string="Question")
    sequence = fields.Integer(string="Sequence", default=10)
    code = fields.Char(string="Code")
    text = fields.Char(string="Question Text", required=True)
    qtype = fields.Selection(
        [("boolean", "Yes/No"), ("text", "Text"), ("select", "Selection")],
        string="Type", required=True, default="boolean"
    )
    selection_options = fields.Text(string="Selection Options")

    required = fields.Boolean(string="Required", default=False)
    critical = fields.Boolean(string="Critical", default=False)

    # answers
    answer_boolean = fields.Boolean(string="Answer (Yes)")
    answer_text = fields.Char(string="Answer (Text)")
    answer_selection = fields.Char(string="Answer (Selection)")

    def _is_answer_filled(self):
        self.ensure_one()
        if self.qtype == "boolean":
            return self.answer_boolean in (True, False)  # always filled (default False counts as filled)
        if self.qtype == "text":
            return bool(self.answer_text and self.answer_text.strip())
        if self.qtype == "select":
            return bool(self.answer_selection and self.answer_selection.strip())
        return False

    def _is_value_filled(self):
        """Alias when question_id is not set (fallback by code)."""
        return self._is_answer_filled()


# =============================================================================
# Inherit clinical.imaging.request — Link to consent & checks
# =============================================================================
class ClinicalImagingRequest(models.Model, _ImagingConsentHelpers):
    _inherit = "clinical.imaging.request"

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        help="Consent document linked to this request."
    )
    consent_required = fields.Boolean(string="Consent Required", compute="_compute_consent_flags", store=False)
    consent_ok = fields.Boolean(string="Consent OK", compute="_compute_consent_flags", store=False)
    consent_scope_needed = fields.Selection(
        selection=lambda self: self.env["clinical.imaging.consent.template"]._fields["scope"].selection,
        string="Required Consent Scope", compute="_compute_consent_flags", store=False
    )

    def _compute_consent_flags(self):
        for rec in self:
            # Determine if consent is required based on modality/imaging type or flags
            scope_needed = False
            required = False
            if rec.imaging_type_id and self._has_field("clinical.imaging.type", "modality") and rec.imaging_type_id.modality == "MR":
                scope_needed = "mri_safety"
                required = True
            # contrast?
            if hasattr(rec, "contrast_required") and getattr(rec, "contrast_required"):
                scope_needed = scope_needed or "contrast"
                required = True
            # sedation?
            if hasattr(rec, "sedation_required") and getattr(rec, "sedation_required"):
                scope_needed = scope_needed or "sedation_anesthesia"
                required = True
            # radiation exposure for CT/fluoro/NM
            if rec.imaging_type_id and self._has_field("clinical.imaging.type", "modality") and rec.imaging_type_id.modality in ("CT", "DX", "MG", "NM", "XR"):
                scope_needed = scope_needed or "radiation_exposure"
            rec.consent_scope_needed = scope_needed or False
            rec.consent_required = required or bool(scope_needed)

            # Check consent validity
            ok = False
            if rec.consent_id:
                try:
                    ok = rec.consent_id.is_fully_valid()
                except Exception:
                    ok = False
            rec.consent_ok = bool(ok)

    @api.onchange("consent_id")
    def _onchange_consent_id(self):
        for rec in self:
            if rec.consent_id:
                # Set reverse link for visibility on consent
                if self._has_field("clinic.consent.form", "imaging_request_id"):
                    rec.consent_id.imaging_request_id = rec.id


# =============================================================================
# Inherit clinical.imaging.result — Convenience backlink to consent
# =============================================================================
class ClinicalImagingResult(models.Model, _ImagingConsentHelpers):
    _inherit = "clinical.imaging.result"

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        compute="_compute_consent_id",
        store=False,
        help="Resolved consent document for this result (from request/encounter/treatment if available)."
    )

    def _compute_consent_id(self):
        for rec in self:
            consent = False
            # Prefer from imaging.request if present
            if rec.imaging_id and self._has_field("clinical.imaging", "request_id") and rec.imaging_id.request_id:
                req = rec.imaging_id.request_id
                if self._has_field("clinical.imaging.request", "consent_id"):
                    consent = req.consent_id
            # Fallback: from encounter screening consent if available
            if not consent and rec.encounter_id and "clinical.imaging.encounter.screening" in self.env:
                scr = self.env["clinical.imaging.encounter.screening"].sudo().search([("encounter_id", "=", rec.encounter_id.id)], limit=1, order="create_date desc")
                if scr and self._has_field("clinical.imaging.encounter.screening", "consent_id"):
                    consent = scr.consent_id
            rec.consent_id = consent.id if consent else False
