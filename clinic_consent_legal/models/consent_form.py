
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_form.py
#
# Primary domain model for Consent & Legal Forms in ClinicOne (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Integration notes:
# - Patient: res.partner (is_company = False) from contacts/clinic_patient
# - Doctor: clinic.doctor (assumed to expose partner_id) from clinic_doctor
# - Treatment: clinic.treatment from clinic_treatment
# - Booking/Appointment: booking.booking from clinic_booking
# - Clinical Encounter: clinic.encounter from clinic_encounter
# - Room Session: clinic.room.session from clinic_room_device or clinic_queue_room
# - Billing/Invoice: account.move (out_invoice / out_refund)
#
# Dependencies expected in __manifest__.py:
#   base, mail, contacts, hr, account, product, portal, clinic_base,
#   clinic_patient, clinic_doctor, clinic_booking, clinic_treatment, clinic_billing, ...
#
from datetime import timedelta
import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import format_datetime


class ConsentForm(models.Model):
    _name = "clinic.consent.form"
    _description = "Consent & Legal Form"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # CORE / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Consent Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self._default_name(),
        help="Unique consent identifier generated from an internal sequence."
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Human-readable display name: Consent Number + Patient."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the record will be hidden without being deleted."
    )

    # -------------------------------------------------------------------------
    # LINKS TO OTHER MODULES (Soft-coupled)
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        ondelete="restrict",
        domain="[('is_company', '=', False)]",
        tracking=True,
        index=True,
        help="The patient who is giving consent."
    )

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        ondelete="set null",
        tracking=True,
        index=True,
        help="The doctor responsible for the procedure (from Clinic Doctor module)."
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment / Procedure",
        ondelete="set null",
        tracking=True,
        index=True,
        help="The treatment/procedure for which this consent is required."
    )

    # Optional direct links (keep optional to avoid hard coupling at install)
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking / Appointment",
        ondelete="set null",
        help="Related booking/appointment record when available."
    )

    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Clinical Appointment",
        ondelete="set null",
        index=True,
        help="Direct link to the ClinicOne appointment that requested this consent.",
    )

    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Related clinical encounter record when available."
    # )

    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Related room session record when available."
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Related Invoice",
        domain="[('move_type', 'in', ['out_invoice', 'out_refund'])]",
        ondelete="set null",
        help="Optional link to the invoice related to this consent."
    )

    # Generic reference to other records (Appointment, Encounter, etc.)
    target_ref = fields.Reference(
        selection=lambda self: self._referenceable_models(),
        string="Related Record",
        help="Generic link to a related record (e.g., appointment, encounter, "
             "treatment session) within ClinicOne."
    )

    # -------------------------------------------------------------------------
    # TEMPLATE / CONTENT
    # -------------------------------------------------------------------------
    template_id = fields.Many2one(
        "clinic.consent.template",
        string="Template",
        ondelete="set null",
        help="Template used to pre-fill the legal content and defaults."
    )

    title = fields.Char(
        string="Title",
        required=True,
        tracking=True,
        help="Short title of the consent (e.g., 'Laser Treatment Consent')."
    )

    content_html = fields.Html(
        string="Consent Content (HTML)",
        sanitize=True,
        help="Full consent content in rich HTML."
    )

    content_text = fields.Text(
        string="Consent Content (Text)",
        help="Plain text fallback for the consent content."
    )

    risks_and_complications = fields.Html(
        string="Risks & Complications",
        help="Documented risks and complications associated with the procedure."
    )

    alternatives = fields.Html(
        string="Alternatives",
        help="Possible alternatives to the proposed procedure."
    )

    required_before_procedure = fields.Boolean(
        string="Required Before Procedure",
        default=True,
        help="If checked, the procedure cannot start unless this consent is signed."
    )

    validity_days = fields.Integer(
        string="Validity (days)",
        default=365,
        help="Number of days after signature during which this consent remains valid."
    )

    consent_version = fields.Char(
        string="Consent Version",
        help="Version marker of the consent content (e.g., derived from template)."
    )

    # -------------------------------------------------------------------------
    # SIGNING & E-SIGNATURE
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("to_sign", "Waiting for Signature"),
            ("signed", "Signed"),
            ("cancelled", "Cancelled"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle state of the consent."
    )

    signer_name = fields.Char(
        string="Signer Full Name",
        help="Full name of the signer as it should appear on the legal document."
    )

    signer_relationship = fields.Selection(
        selection=[
            ("self", "Self (Patient)"),
            ("guardian_parent", "Guardian/Parent"),
            ("guardian_legal", "Legal Guardian/Representative"),
            ("other", "Other Authorized Person"),
        ],
        string="Signer Relationship",
        default="self",
        help="Relationship of the signer to the patient."
    )

    guardian_partner_id = fields.Many2one(
        "res.partner",
        string="Signer (Partner)",
        ondelete="set null",
        help="If the signer is not the patient (e.g., parent/guardian), "
             "link to the partner here."
    )

    signature_binary = fields.Binary(
        string="Signature",
        attachment=True,
        help="Captured e-signature image (PNG)."
    )

    signature_datetime = fields.Datetime(
        string="Signed On",
        help="Timestamp when the consent was signed."
    )

    signature_ip = fields.Char(
        string="Signature IP Address",
        help="Public IP address captured at the moment of signature (if available)."
    )

    signature_user_agent = fields.Char(
        string="Signature User-Agent",
        help="Client user-agent string captured at the moment of signature (if available)."
    )

    integrity_hash = fields.Char(
        string="Content Integrity Hash",
        readonly=True,
        help="SHA256 hash to record the integrity of key fields at signature time."
    )

    expiry_date = fields.Date(
        string="Expiry Date",
        compute="_compute_expiry_date",
        store=True,
        help="Date when this consent expires based on validity settings."
    )

    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        search="_search_is_expired",
        store=False,
        help="Indicates whether the consent has already expired."
    )

    # -------------------------------------------------------------------------
    # PORTAL / ACCESS
    # -------------------------------------------------------------------------
    access_url = fields.Char(
        string="Portal URL",
        compute="_compute_access_url",
        help="Public portal URL for the patient to review/sign this consent."
    )

    # access_token is provided by portal.mixin (Char)
    # message_follower_ids provided by mail.thread

    # -------------------------------------------------------------------------
    # OPERATIONS / REMINDERS / UTILITIES
    # -------------------------------------------------------------------------
    source = fields.Selection(
        selection=[
            ("in_clinic", "In-Clinic"),
            ("portal", "Portal"),
            ("ecommerce", "eCommerce Pre-Booking"),
            ("import", "Imported")
        ],
        string="Origin Source",
        default="in_clinic",
        help="Where this consent was initiated."
    )

    next_reminder_date = fields.Date(
        string="Next Reminder On",
        help="Next planned reminder date to request signature."
    )

    signature_ids = fields.One2many(
        "clinic.consent.signature",
        "form_id",
        string="Signature Ledger",
        readonly=True,
        help="Append-only style signature ledger for this consent.",
    )
    signature_count = fields.Integer(
        string="Signatures",
        compute="_compute_signature_count",
    )
    legal_attachment_ids = fields.One2many(
        "clinic.consent.attachment",
        "form_id",
        string="Legal Attachments",
        readonly=True,
    )
    legal_attachment_count = fields.Integer(
        string="Legal Attachments",
        compute="_compute_legal_attachment_count",
    )

    attachments_count = fields.Integer(
        string="Attachments",
        compute="_compute_attachments_count",
        help="Number of attachments linked to this consent."
    )

    note = fields.Text(
        string="Internal Notes",
        help="Internal notes for staff; not included in the legal document."
    )

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_name(self):
        # Sequence code should exist in data/consent_sequence.xml
        return self.env["ir.sequence"].next_by_code("clinic.consent.form") or _("New")

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.patient_id:
                rec.display_name = f"{rec.name} - {rec.patient_id.display_name}"
            else:
                rec.display_name = rec.name or _("Consent")

    @api.depends("signature_datetime", "validity_days")
    def _compute_expiry_date(self):
        for rec in self:
            if rec.signature_datetime and rec.validity_days and rec.validity_days > 0:
                rec.expiry_date = (rec.signature_datetime + timedelta(days=rec.validity_days)).date()
            else:
                rec.expiry_date = False

    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(rec.expiry_date and rec.expiry_date < today)

    @api.model
    def _search_is_expired(self, operator, value):
        """Translate the dynamic flag into a searchable stored-date domain."""
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise ValidationError(_("Expired can only be searched with '=' or '!=' and a Boolean value."))
        today = fields.Date.context_today(self)
        expired_domain = [("expiry_date", "!=", False), ("expiry_date", "<", today)]
        not_expired_domain = [
            "|",
            ("expiry_date", "=", False),
            ("expiry_date", ">=", today),
        ]
        wants_expired = value if operator == "=" else not value
        return expired_domain if wants_expired else not_expired_domain

    def _compute_signature_count(self):
        Signature = self.env["clinic.consent.signature"]
        for rec in self:
            rec.signature_count = Signature.search_count([("form_id", "=", rec.id)])

    def _compute_legal_attachment_count(self):
        Attachment = self.env["clinic.consent.attachment"]
        for rec in self:
            rec.legal_attachment_count = Attachment.search_count([("form_id", "=", rec.id)])

    def _compute_access_url(self):
        for rec in self:
            # Keep stable, portable portal URL
            rec.access_url = f"/my/consents/{rec.id}"

    @api.depends()
    def _compute_attachments_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachments_count = Attachment.search_count([
                ("res_model", "=", rec._name),
                ("res_id", "=", rec.id),
            ])

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("template_id")
    def _onchange_template_id(self):
        """When selecting a template, pull in content, risks, alternatives, version, validity, and title if empty."""
        if self.template_id:
            tpl = self.template_id.sudo()
            if not self.title:
                self.title = tpl.title or _("Consent")
            self.content_html = tpl.content_html
            self.content_text = tpl.content_text
            self.risks_and_complications = tpl.risks_and_complications
            self.alternatives = tpl.alternatives
            if tpl.validity_days:
                self.validity_days = tpl.validity_days
            if tpl.consent_version:
                self.consent_version = tpl.consent_version
            if tpl.required_before_procedure is not None:
                self.required_before_procedure = tpl.required_before_procedure

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Consent Number must be unique per company.",
    )

    @api.constrains("patient_id", "title", "content_html", "content_text")
    def _check_minimum_content(self):
        for rec in self:
            if not rec.title:
                raise ValidationError(_("Title is required."))
            if not rec.patient_id:
                raise ValidationError(_("Patient is required."))
            if not (rec.content_html or rec.content_text):
                raise ValidationError(_("Consent content is required (HTML or Text)."))

    # If required_before_procedure = True, ensure treatment/booking known before signing
    @api.constrains("required_before_procedure", "state")
    def _check_required_context(self):
        for rec in self:
            if rec.required_before_procedure and rec.state in ("to_sign", "signed"):
                # Prefer at least treatment or booking context for audit clarity
                if not (rec.treatment_id or rec.booking_id):
                    raise ValidationError(
                        _("When consent is required before a procedure, "
                          "either Treatment or Booking should be specified.")
                    )

    # -------------------------------------------------------------------------
    # ACCESS GUARDS
    # -------------------------------------------------------------------------
    def _ensure_editable(self):
        for rec in self:
            if rec.state in ("signed", "archived"):
                raise AccessError(_("You cannot modify a signed or archived consent."))

    def write(self, vals):
        # Disallow editing after signed/archived, except certain benign fields
        protected_states = ("signed", "archived")
        benign_fields = {
            "activity_exception_decoration", "message_follower_ids", "message_ids",
            "message_main_attachment_id", "activity_ids", "activity_state",
            "activity_user_id", "activity_type_id", "activity_date_deadline",
            "next_reminder_date", "note", "active",
        }
        if any(rec.state in protected_states for rec in self):
            forbidden = set(vals.keys()) - benign_fields
            transition_only = forbidden <= {"state"} and self.env.context.get("allow_legal_state_transition")
            if forbidden and not transition_only:
                raise AccessError(_("You cannot modify a signed or archived consent."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise AccessError(_("You can only delete consents in Draft or Cancelled state."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # REFERENCEABLE MODELS (for fields.Reference)
    # -------------------------------------------------------------------------
    @api.model
    def _referenceable_models(self):
        """
        Return a selection of (model, label) that are safe to reference across ClinicOne.
        These models may or may not be installed; that's acceptable for a reference field.
        """
        return [
            ("clinic.treatment", "Treatment"),
            ("clinic.treatment.session", "Treatment Session"),
            ("clinic.encounter", "Clinical Encounter"),
            ("booking.booking", "Booking/Appointment"),
            ("clinic.room.session", "Room Session"),
            ("account.move", "Invoice"),
            ("res.partner", "Partner"),
        ]

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS & BUSINESS METHODS
    # -------------------------------------------------------------------------
    def action_set_to_sign(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise UserError(_("Only Draft/Cancelled consents can be sent for signature."))
            if not rec.patient_id:
                raise UserError(_("Please set the Patient before requesting a signature."))
            if not (rec.content_html or rec.content_text):
                raise UserError(_("Please fill the consent content before requesting a signature."))
            rec.state = "to_sign"
            rec._subscribe_parties()
            # Schedule an activity for the responsible user (optional)
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=self.env.user.id,
                note=_("Request the patient to review and sign the consent."),
            )

    def action_sign(
        self,
        signer_name=False,
        signature_binary=False,
        signer_relationship=False,
        ip_address=False,
        user_agent=False,
        signed_dt=False,
    ):
        """
        Perform signature. Typically called from a controller or wizard.

        :param signer_name: Full name of signer (string)
        :param signature_binary: Binary PNG of signature
        :param signer_relationship: 'self', 'guardian_parent', 'guardian_legal', 'other'
        :param ip_address: IP address string
        :param user_agent: HTTP user-agent string
        :param signed_dt: datetime; if False, use fields.Datetime.now()
        """
        for rec in self:
            if rec.state != "to_sign":
                raise UserError(_("Only consents in 'Waiting for Signature' can be signed."))
            if rec.required_before_procedure and not rec.patient_id:
                raise UserError(_("Patient is required before signing."))

            _signer_name = signer_name or rec.signer_name
            if not _signer_name:
                raise UserError(_("Signer Full Name is required."))
            signature_value = signature_binary or rec.signature_binary
            if not signature_value:
                raise UserError(_("A signature image is required before the consent can be signed."))

            signed_when = signed_dt or fields.Datetime.now()

            # Persist signature
            rec.write({
                "signer_name": _signer_name,
                "signature_binary": signature_value,
                "signer_relationship": signer_relationship or rec.signer_relationship,
                "signature_ip": ip_address or rec.signature_ip,
                "signature_user_agent": user_agent or rec.signature_user_agent,
                "signature_datetime": signed_when,
                "state": "signed",
                "integrity_hash": rec._compute_integrity_hash(
                    signer_name=_signer_name,
                    signed_dt=signed_when,
                ),
            })

            # Record an immutable-style ledger entry at the same legal event.
            Signature = self.env["clinic.consent.signature"].sudo()
            if not Signature.search_count([
                ("form_id", "=", rec.id),
                ("signed_on", "=", signed_when),
                ("signer_name", "=", _signer_name),
                ("state", "=", "signed"),
            ]):
                Signature.create_from_consent(
                    form_id=rec.id,
                    role="guardian" if rec.signer_relationship != "self" else "patient",
                    signer_name=_signer_name,
                    signature_image=signature_value,
                    relationship=rec.signer_relationship,
                    partner_id=rec.guardian_partner_id.id if rec.guardian_partner_id else rec.patient_id.id,
                    user_id=self.env.user.id,
                    ip_address=ip_address or rec.signature_ip,
                    user_agent=user_agent or rec.signature_user_agent,
                    signed_on=signed_when,
                )

            # Optional: close related activities
            rec.activity_feedback(["mail.mail_activity_data_todo"])

    def action_cancel(self):
        self._ensure_editable()
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        # Allow resetting cancelled only
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(_("Only Cancelled consents can be reset to Draft."))
        self.write({"state": "draft"})

    def action_archive(self):
        for rec in self:
            if rec.state != "signed":
                raise UserError(_("Only Signed consents can be archived."))
        self.with_context(allow_legal_state_transition=True).write({"state": "archived"})

    def action_send_reminder(self, days=3):
        """Set next reminder date and schedule an activity."""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != "to_sign":
                raise UserError(_("Only consents waiting for signature can be reminded."))
            rec.next_reminder_date = today + timedelta(days=days or 3)
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=self.env.user.id,
                note=_("Follow up with the patient to sign the consent."),
                date_deadline=rec.next_reminder_date,
            )

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def _subscribe_parties(self):
        """Subscribe patient and doctor partners to chatter notifications."""
        for rec in self:
            partner_ids = []
            if rec.patient_id:
                partner_ids.append(rec.patient_id.id)
            # If doctor model has a partner_id field, subscribe it when available.
            if rec.doctor_id and hasattr(rec.doctor_id, "partner_id") and rec.doctor_id.partner_id:
                partner_ids.append(rec.doctor_id.partner_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=partner_ids)

    def _compute_integrity_hash(self, signer_name, signed_dt):
        """Compute a SHA256 hash over key legal fields at signature time."""
        items = [
            ("company_id", self.company_id.id if self.company_id else 0),
            ("patient_id", self.patient_id.id if self.patient_id else 0),
            ("doctor_id", self.doctor_id.id if self.doctor_id else 0),
            ("treatment_id", self.treatment_id.id if self.treatment_id else 0),
            ("booking_id", self.booking_id.id if self.booking_id else 0),
            # ("encounter_id", self.encounter_id.id if self.encounter_id else 0),
            ("room_session_id", self.room_session_id.id if self.room_session_id else 0),
            ("title", self.title or ""),
            ("content_html", self.content_html or ""),
            ("content_text", self.content_text or ""),
            ("risks", self.risks_and_complications or ""),
            ("alternatives", self.alternatives or ""),
            ("required_before_procedure", str(bool(self.required_before_procedure))),
            ("validity_days", int(self.validity_days or 0)),
            ("consent_version", self.consent_version or ""),
            ("signer_name", signer_name or ""),
            ("signer_relationship", self.signer_relationship or ""),
            ("signed_dt", format_datetime(self.env, signed_dt) if signed_dt else ""),
        ]
        payload = "|".join([f"{k}={v}" for k, v in items])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------------------
    # PORTAL MIXIN
    # -------------------------------------------------------------------------
    def _get_report_base_filename(self):
        self.ensure_one()
        base = self.name or "Consent"
        suffix = f" - {self.patient_id.display_name}" if self.patient_id else ""
        return f"{base}{suffix}"

    def _get_access_action(self, access_uid=None):
        """Override to route portal action to our custom URL."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": self.access_url,
        }

    # -------------------------------------------------------------------------
    # HELPERS FOR VIEWS & UI
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_view_signatures(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Signature Ledger"),
            "res_model": "clinic.consent.signature",
            "view_mode": "list,form",
            "domain": [("form_id", "=", self.id)],
            "context": {"default_form_id": self.id},
        }

    def action_view_legal_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Legal Attachments"),
            "res_model": "clinic.consent.attachment",
            "view_mode": "list,form",
            "domain": [("form_id", "=", self.id)],
            "context": {"default_form_id": self.id},
        }

    def action_open_template(self):
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("No consent template is linked."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Template"),
            "res_model": "clinic.consent.template",
            "view_mode": "form",
            "res_id": self.template_id.id,
        }

    def action_preview_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.get_portal_url(),
            "target": "new",
        }
