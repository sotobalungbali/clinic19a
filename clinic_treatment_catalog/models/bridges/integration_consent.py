# -*- coding: utf-8 -*-
# ClinicOne - Clinical Staff (Nurse & Therapist) Management
# File: integration_consent.py
#
# CE-safe: no hard dependency to Enterprise models (e.g., 'sign.request').
# E-sign is represented by neutral fields (e_sign_*). Optional bridges may
# implement provider-specific logic without introducing Enterprise comodels.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

# 1) Tambahkan konstanta supaya value-nya konsisten
SCOPE_SELECTION = [
    ("treatment_general", "General Treatment Consent"),
    ("procedure_specific", "Procedure-Specific Consent"),
    ("telemedicine", "Telemedicine Consent"),
    ("medication_admin", "Medication Administration Consent"),
    ("photo_media", "Photo/Media Consent"),
    ("data_privacy", "Data Privacy / PDPA/GDPR"),
]

# =====================================================================
# Utilities
# =====================================================================
def _now():
    return fields.Datetime.now()


def _age_in_years(dob, at=None):
    """Return age in full years."""
    if not dob:
        return None
    at = at or fields.Date.context_today(None)
    if isinstance(at, datetime):
        at = at.date()
    years = at.year - dob.year - ((at.month, at.day) < (dob.month, dob.day))
    return years


# =====================================================================
# 1) CONSENT TEMPLATE
# =====================================================================
class ClinicConsentTemplate(models.Model):
    _name = "clinic.consent.template"
    _description = "Consent Template"
    _order = "sequence, name"

    sequence = fields.Integer(string="Sequence", default=10, help="Lower comes first in selection lists.")
    name = fields.Char(string="Template Name", required=True)
    code = fields.Char(string="Template Code", help="Short code used to reference this template.")
    active = fields.Boolean(string="Active", default=True)

    scope = fields.Selection(
        selection=[
            ("treatment_general", "General Treatment Consent"),
            ("procedure_specific", "Procedure-Specific Consent"),
            ("telemedicine", "Telemedicine Consent"),
            ("medication_admin", "Medication Administration Consent"),
            ("photo_media", "Photo/Media Consent"),
            ("data_privacy", "Data Privacy / PDPA/GDPR"),
        ],
        string="Consent Scope",
        required=True,
        help="Defines where this consent applies."
    )

    category = fields.Selection(
        selection=[("clinical", "Clinical"), ("privacy", "Privacy"), ("media", "Media"), ("other", "Other")],
        string="Category",
        default="clinical",
    )

    requires_guardian = fields.Boolean(
        string="Requires Guardian if Minor",
        default=True,
        help="If the patient is a minor, a guardian signature is required.",
    )
    requires_witness = fields.Boolean(
        string="Requires Staff Witness",
        default=False,
        help="If enabled, a staff witness signature is required.",
    )
    validity_days = fields.Integer(
        string="Validity (days)",
        default=365,
        help="Consent validity period starting from the signature time.",
    )
    allow_reuse = fields.Boolean(
        string="Reusable within Validity",
        default=True,
        help="If enabled, this consent can be reused across encounters within its validity window.",
    )

    # Default checklist items copied to requests
    default_item_ids = fields.One2many("clinic.consent.template.item", "template_id", string="Default Items")

    version_ids = fields.One2many("clinic.consent.template.version", "template_id", string="Versions")
    latest_version_id = fields.Many2one(
        "clinic.consent.template.version",
        string="Latest Version",
        compute="_compute_latest_version",
        store=True,
    )

    notes = fields.Text(string="Notes")

    treatment_id = fields.Many2one(comodel_name='clinic.treatment', 
        string='Treatment')    

    _code_unique = models.Constraint(
        "unique(code)",
        "Template Code must be unique.",
    )
    _validity_non_negative = models.Constraint(
        "CHECK (validity_days >= 0)",
        "Validity (days) must be non-negative.",
    )

    @api.depends("version_ids.effective_from", "version_ids.effective_to", "version_ids.state")
    def _compute_latest_version(self):
        for rec in self:
            published = rec.version_ids.filtered(lambda v: v.state == "published") \
                                       .sorted(key=lambda v: (v.effective_from or date.min), reverse=True)
            rec.latest_version_id = published[:1].id if published else False


class ClinicConsentTemplateItem(models.Model):
    _name = "clinic.consent.template.item"
    _description = "Consent Template Item"
    _order = "sequence, id"

    sequence = fields.Integer(string="Sequence", default=10)
    template_id = fields.Many2one("clinic.consent.template", string="Template", required=True, ondelete="cascade")
    label = fields.Char(string="Item Label", required=True, help="Item label that the patient must acknowledge.")
    required = fields.Boolean(string="Required", default=False)
    default_value = fields.Selection(
        selection=[("none", "None"), ("agree", "Agree"), ("disagree", "Disagree")],
        string="Default Value",
        default="none",
    )
    notes = fields.Char(string="Notes")


class ClinicConsentTemplateVersion(models.Model):
    _name = "clinic.consent.template.version"
    _description = "Consent Template Version"
    _order = "template_id, version desc"

    template_id = fields.Many2one("clinic.consent.template", string="Template", required=True, ondelete="cascade")
    version = fields.Integer(string="Version", required=True, default=1)
    title = fields.Char(string="Title", help="Public title of this version.")
    body_html = fields.Html(string="Body (HTML)", sanitize=True, help="Consent body in HTML (snapshotted on request).")
    effective_from = fields.Date(string="Effective From", required=True, default=lambda s: fields.Date.today())
    effective_to = fields.Date(string="Effective To", help="Optional end of validity for this version (superseded).")
    changelog = fields.Text(string="Changelog / Notes")
    state = fields.Selection(
        selection=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")],
        string="Status",
        default="draft",
        index=True,
    )

    _version_unique = models.Constraint(
        "unique(template_id, version)",
        "Version number must be unique per template.",
    )
    _date_range_valid = models.Constraint(
        "CHECK (effective_to IS NULL OR effective_to > effective_from)",
        "Effective To must be later than Effective From.",
    )


# =====================================================================
# 2) CONSENT REQUEST (INSTANCE PER PATIENT)
# =====================================================================
class ClinicConsentRequest(models.Model):
    _name = "clinic.consent.request"
    _description = "Patient Consent Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "state desc, signed_at desc, id desc"

    # Identity & context
    reference = fields.Char(string="Reference", copy=False, default="/", index=True,
                            help="Unique consent reference generated by sequence.", tracking=True)
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company)
    branch_id = fields.Many2one("clinic.branch", string="Branch", help="Operational branch where consent was collected.", tracking=True)

    template_id = fields.Many2one("clinic.consent.template", string="Template", required=True, ondelete="restrict", tracking=True)
    version_id = fields.Many2one("clinic.consent.template.version", string="Template Version", required=True, ondelete="restrict")
    title = fields.Char(string="Title", help="Title snapshot from template version.")
    content_html = fields.Html(string="Content (Snapshot)", help="Snapshot of consent body used at signing time.")
    # scope = fields.Selection(related="template_id.scope", store=True, readonly=True)
    # 2) Ganti definisi field scope (HAPUS yang lama: related="template_id.scope")
    scope = fields.Selection(
        selection=SCOPE_SELECTION,
        compute="_compute_scope",
        store=True,
        readonly=True,
    )

    # Clinical context (keep optional to reduce hard deps; enable via other modules as needed)
    # Existing active consent code already reads/searches patient_id.
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    # encounter_id = fields.Many2one("clinic.encounter", string="Encounter", ondelete="set null")
    # procedure_id = fields.Many2one("clinic.procedure", string="Procedure", ondelete="set null")
    # emar_admin_id = fields.Many2one("clinic.emar.administration", string="Medication Administration", ondelete="set null")
    # tele_session_id = fields.Many2one("clinic.telemedicine.session", string="Telemedicine Session", ondelete="set null")
    # booking_id = fields.Many2one("booking.booking", string="Booking", ondelete="set null")
    staff_assignment_id = fields.Many2one("clinic.staff.assignment", string="Staff Assignment", ondelete="set null")
    # room_assignment_id = fields.Many2one("clinic.room.assignment", string="Room Assignment", ondelete="set null")

    # Parties
    created_by_id = fields.Many2one("clinic.staff", string="Created By", ondelete="set null", help="Staff who created the consent request.")
    requested_by_id = fields.Many2one("clinic.staff", string="Requested By", ondelete="set null", help="Staff who requested the consent.")
    witness_staff_id = fields.Many2one("clinic.staff", string="Witness Staff", ondelete="set null", help="Staff who witnessed the signature.")
    guardian_required = fields.Boolean(string="Guardian Required", help="Computed based on template and patient age.")
    guardian_name = fields.Char(string="Guardian Name", help="If guardian is required, fill the guardian's full name.")
    guardian_relation = fields.Char(string="Guardian Relation", help="Relationship to the patient.")
    guardian_id_no = fields.Char(string="Guardian ID No.", help="Government-issued ID or other identifier.")

    # Manual signatures (fallback)
    patient_signature = fields.Binary(string="Patient Signature", attachment=True, help="Signature image (manual).")
    guardian_signature = fields.Binary(string="Guardian Signature", attachment=True, help="Guardian signature image (manual).")
    witness_signature = fields.Binary(string="Witness Signature", attachment=True, help="Witness signature image (manual).")

    # CE-safe E-Sign neutral fields (no Enterprise comodels)
    e_sign_provider = fields.Selection(
        selection=[("none", "None"), ("external", "External Provider")],
        string="E-Sign Provider",
        default="none",
        tracking=True,
        help="Neutral provider flag for Community Edition. No hard links to Enterprise models.",
    )
    e_sign_reference = fields.Char(
        string="E-Sign Reference",
        help="External e-sign request reference or identifier (free text).",
        tracking=True,
    )
    e_sign_url = fields.Char(
        string="E-Sign URL",
        help="Public tracking/signing URL from the provider (if any).",
    )
    e_sign_status = fields.Selection(
        selection=[("none", "None"), ("sent", "Sent"), ("signed", "Signed"), ("declined", "Declined"), ("cancelled", "Cancelled")],
        string="E-Sign Status",
        default="none",
        tracking=True,
        help="Mirror status from the external provider, or maintain manually in CE.",
    )
    e_sign_last_sync = fields.Datetime(
        string="E-Sign Last Sync",
        help="Timestamp of the last synchronization (if bridged to a provider).",
        readonly=True,
    )
    e_sign_payload = fields.Text(
        string="E-Sign Payload (JSON)",
        help="Raw JSON payload returned by the provider. Stored as text for CE compatibility.",
    )
    has_e_signature = fields.Boolean(
        string="Has E-Signature",
        compute="_compute_has_e_signature",
        help="True when provider is set and status is 'signed'.",
    )

    # Metadata at signing
    signer_ip = fields.Char(string="Signer IP", help="Captured IP address at signing time (if available).")
    signer_user_agent = fields.Char(string="Signer User Agent", help="Captured browser user-agent (if available).")
    signed_at = fields.Datetime(string="Signed At", help="Date/time when consent was signed (UTC).", tracking=True)
    expires_at = fields.Datetime(string="Expires At", help="Consent expiry date/time.")
    revoked_at = fields.Datetime(string="Revoked At", help="When the consent was revoked.")
    revoke_reason = fields.Char(string="Revoke Reason")

    is_valid = fields.Boolean(string="Is Valid", compute="_compute_is_valid", store=True, help="True if signed and not expired/revoked.")
    validity_days = fields.Integer(string="Validity (days)", related="template_id.validity_days", store=True, readonly=True)

    # Items (acknowledgements)
    item_ids = fields.One2many("clinic.consent.request.item", "request_id", string="Items")

    # Attachments
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Signed PDF", ondelete="set null")
    attachment_count = fields.Integer(string="Attachments", compute="_compute_attachment_count", store=False)

    # Billing context (optional)
    invoice_id = fields.Many2one("account.move", string="Invoice", ondelete="set null")

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("signed", "Signed"),
            ("revoked", "Revoked"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
    )

    notes = fields.Text(string="Notes")

    _consent_reference_unique = models.Constraint(
        "unique(reference)",
        "Consent Reference must be unique.",
    )

    # ----------------------------
    # Computes
    # ----------------------------
    # 3) Compute tanpa nested depends (cukup 'template_id')
    @api.depends("template_id")
    def _compute_scope(self):
        for rec in self:
            rec.scope = rec.template_id.scope or False

    @api.depends("e_sign_provider", "e_sign_status")
    def _compute_has_e_signature(self):
        for rec in self:
            rec.has_e_signature = bool(rec.e_sign_provider != "none" and rec.e_sign_status == "signed")

    @api.depends("reference", "title", "state", "patient_id")
    def _compute_display_name(self):
        """Build a stable human label without changing the consent workflow."""
        selection = self._fields["state"].selection
        state_labels = dict(selection) if isinstance(selection, list) else {}
        for rec in self:
            parts = []
            if rec.reference and rec.reference != "/":
                parts.append("[%s]" % rec.reference)
            if rec.patient_id:
                parts.append(rec.patient_id.display_name)
            if rec.title:
                parts.append("• %s" % rec.title)
            if rec.state:
                parts.append("[%s]" % state_labels.get(rec.state, rec.state))
            rec.display_name = " ".join(parts) or _("Consent")

    @api.depends("state", "signed_at", "expires_at", "revoked_at")
    def _compute_is_valid(self):
        now = _now()
        for rec in self:
            valid = rec.state == "signed"
            if valid and rec.expires_at and rec.expires_at <= now:
                valid = False
            if valid and rec.revoked_at:
                valid = False
            rec.is_valid = valid

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].search_count([
                ("res_model", "=", self._name),
                ("res_id", "=", rec.id),
            ])

    # ----------------------------
    # Create override
    # ----------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Reference
            if not vals.get("reference") or vals.get("reference") in ("/",):
                vals["reference"] = self.env["ir.sequence"].next_by_code("clinic.consent.request") or "/"

            # Snapshot from version
            if vals.get("version_id"):
                ver = self.env["clinic.consent.template.version"].browse(vals["version_id"])
                if ver:
                    vals.setdefault("title", ver.title or ver.template_id.name)
                    vals.setdefault("content_html", ver.body_html or "")

            # Default version from template.latest_version_id
            if not vals.get("version_id") and vals.get("template_id"):
                tpl = self.env["clinic.consent.template"].browse(vals["template_id"])
                if tpl and tpl.latest_version_id:
                    ver = tpl.latest_version_id
                    vals["version_id"] = ver.id
                    vals.setdefault("title", ver.title or tpl.name)
                    vals.setdefault("content_html", ver.body_html or "")

            # Guardian required?
            if "guardian_required" not in vals and vals.get("patient_id") and vals.get("template_id"):
                pat = self.env["clinic.patient"].browse(vals["patient_id"])
                tpl = self.env["clinic.consent.template"].browse(vals["template_id"])
                minor = False
                if hasattr(pat, "birth_date") and pat.birth_date:
                    minor = (_age_in_years(pat.birth_date) or 999) < 18
                elif hasattr(pat, "is_minor"):
                    minor = bool(pat.is_minor)
                vals["guardian_required"] = bool(tpl.requires_guardian and minor)

        recs = super().create(vals_list)

        # Populate default items from template
        for rec in recs:
            if not rec.item_ids and rec.template_id.default_item_ids:
                items = [(0, 0, {
                    "label": it.label,
                    "required": it.required,
                    "value": it.default_value,
                }) for it in rec.template_id.default_item_ids]
                if items:
                    rec.item_ids = items
        return recs

    # ----------------------------
    # Onchange
    # ----------------------------
    @api.onchange("template_id")
    def _onchange_template(self):
        for rec in self:
            if rec.template_id and rec.template_id.latest_version_id:
                ver = rec.template_id.latest_version_id
                rec.version_id = ver.id
                rec.title = ver.title or rec.template_id.name
                rec.content_html = ver.body_html or ""
            # Guardian required recompute on form
            if rec.patient_id and rec.template_id:
                minor = False
                if hasattr(rec.patient_id, "birth_date") and rec.patient_id.birth_date:
                    minor = (_age_in_years(rec.patient_id.birth_date) or 999) < 18
                elif hasattr(rec.patient_id, "is_minor"):
                    minor = bool(rec.patient_id.is_minor)
                rec.guardian_required = bool(rec.template_id.requires_guardian and minor)

    # ----------------------------
    # Constraints
    # ----------------------------
    @api.constrains("template_id", "version_id")
    def _check_version_belongs_to_template(self):
        for rec in self:
            if rec.version_id and rec.template_id and rec.version_id.template_id.id != rec.template_id.id:
                raise ValidationError(_("Selected version does not belong to the chosen template."))

    # ----------------------------
    # Helpers
    # ----------------------------
    def _calc_expires_at(self):
        for rec in self:
            days = rec.validity_days or 0
            rec.expires_at = (rec.signed_at + timedelta(days=days)) if (rec.signed_at and days > 0) else False

    # ----------------------------
    # Workflow
    # ----------------------------
    def action_request(self):
        """Move to 'requested'. In CE, e-sign is manual or bridged externally."""
        for rec in self:
            if rec.state not in ("draft", "cancelled", "expired"):
                continue
            rec.state = "requested"
            if rec.e_sign_provider != "none":
                rec.e_sign_status = "sent"
            rec.message_post(body=_("Consent requested."))

    def action_mark_signed(self, signer_ip=None, user_agent=None):
        """Manual sign (or callback from external bridge)."""
        for rec in self:
            if rec.state not in ("requested", "draft"):
                continue
            rec.signed_at = _now()
            rec._calc_expires_at()
            rec.state = "signed"
            if signer_ip:
                rec.signer_ip = signer_ip
            if user_agent:
                rec.signer_user_agent = user_agent
            if rec.e_sign_provider != "none":
                rec.e_sign_status = "signed"
            rec.message_post(body=_("Consent signed."))

    def action_revoke(self, reason=None):
        for rec in self:
            if rec.state not in ("signed",):
                continue
            rec.revoked_at = _now()
            rec.revoke_reason = reason or rec.revoke_reason
            rec.state = "revoked"
            rec.message_post(body=_("Consent revoked. %s") % (("Reason: %s" % reason) if reason else ""))

    def action_expire(self):
        for rec in self:
            if rec.state == "signed":
                rec.state = "expired"
                rec.message_post(body=_("Consent expired."))
            elif rec.expires_at and rec.expires_at <= _now():
                rec.state = "expired"
                rec.message_post(body=_("Consent expired (auto)."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state in ("signed",):
                raise ValidationError(_("Signed consent cannot be cancelled. Please revoke instead."))
            rec.state = "cancelled"
            if reason:
                rec.notes = (rec.notes or "") + ("\n" if rec.notes else "") + _("Cancelled: %s") % reason
            rec.message_post(body=_("Consent cancelled."))

    # ----------------------------
    # Enforcement API (used by other modules)
    # ----------------------------
    @api.model
    def ensure_valid_consent(self, patient_id, scope, at_datetime=None, procedure_id=False, tele_session_id=False, emar_admin_id=False):
        """Ensure a valid consent exists for patient & scope at 'at_datetime' (or now)."""
        at = at_datetime or _now()
        dom = [
            ("patient_id", "=", patient_id),
            ("scope", "=", scope),
            ("state", "=", "signed"),
            "|", ("expires_at", "=", False), ("expires_at", ">", at),
            ("revoked_at", "=", False),
        ]
        optional_scope_fields = {
            "procedure_id": procedure_id,
            "tele_session_id": tele_session_id,
            "emar_admin_id": emar_admin_id,
        }
        for field_name, value in optional_scope_fields.items():
            if not value:
                continue
            if field_name not in self._fields:
                raise ValidationError(
                    _("Consent integration field '%s' is not available in the current addon closure.")
                    % field_name
                )
            dom.append((field_name, "=", value))
        consent = self.search(dom, limit=1, order="signed_at desc")
        if consent:
            return True
        raise ValidationError(_("No valid consent found for the required scope."))

    # ----------------------------
    # Name get
    # ----------------------------
    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.display_name or rec.reference or _("Consent")))
        return res

    # ----------------------------
    # Cron helper (auto-expire)
    # ----------------------------
    @api.model
    def cron_expire_consents(self):
        recs = self.search([("state", "=", "signed"), ("expires_at", "!=", False), ("expires_at", "<=", _now())])
        for r in recs:
            r.action_expire()
        return True


class ClinicConsentRequestItem(models.Model):
    _name = "clinic.consent.request.item"
    _description = "Consent Request Item"
    _order = "sequence, id"

    sequence = fields.Integer(string="Sequence", default=10)
    request_id = fields.Many2one("clinic.consent.request", string="Consent Request", required=True, ondelete="cascade")
    label = fields.Char(string="Item Label", required=True)
    required = fields.Boolean(string="Required", default=False)
    value = fields.Selection(
        selection=[("none", "None"), ("agree", "Agree"), ("disagree", "Disagree")],
        string="Value",
        default="none",
    )
    notes = fields.Char(string="Notes")

    @api.constrains("value", "required")
    def _check_required_agreement(self):
        for rec in self:
            if rec.required and rec.value != "agree":
                raise ValidationError(_("Required consent item must be agreed."))


# =====================================================================
# Hook for Staff convenience (optional)
# =====================================================================
class ClinicStaffConsentMixin(models.AbstractModel):
    _name = "clinic.staff.consent.mixin"
    _description = "Staff Consent Helper Mixin"

    def require_consent(self, patient_id, scope, **kwargs):
        """Quick helper for staff/assignment to verify consent."""
        self.env["clinic.consent.request"].ensure_valid_consent(patient_id=patient_id, scope=scope, **kwargs)
        return True

