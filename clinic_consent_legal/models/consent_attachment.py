
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_attachment.py
#
# Attachment registry for ClinicOne Consent & Legal Forms (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Purpose:
#   - Centralize attachments related to a consent form (support docs, photos, lab results, IDs, etc.)
#   - Track file metadata (size/mime/checksum) via ir.attachment
#   - Control portal visibility per attachment with confidentiality levels
#   - Enforce edit/delete guards after consent is signed/archived
#   - Offer soft-coupled links to booking/encounter/room session for audit
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError


class ConsentAttachment(models.Model):
    _name = "clinic.consent.attachment"
    _description = "Consent Attachment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, create_date desc, id desc"

    # -------------------------------------------------------------------------
    # CORE / LINKS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Title",
        required=True,
        tracking=True,
        help="Short title of the attachment (e.g., 'Pre-op Photo (Front)')."
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order for display in lists/kanban."
    )

    form_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent Form",
        required=True,
        ondelete="cascade",
        index=True,
        help="The consent form this attachment belongs to."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="form_id.company_id",
        store=True,
        index=True,
        readonly=True
    )

    # Convenience relateds (for easy filtering/reporting)
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="form_id.patient_id",
        store=True,
        index=True,
        readonly=True
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="form_id.doctor_id",
        store=True,
        index=True,
        readonly=True
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="form_id.treatment_id",
        store=True,
        index=True,
        readonly=True
    )

    # Optional deep links (soft-coupled)
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking / Appointment",
        ondelete="set null",
        help="Optional link to appointment for contextual audit."
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Optional link to clinical encounter for contextual audit."
    # )
    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Optional link to room session for contextual audit."
    )

    # -------------------------------------------------------------------------
    # CLASSIFICATION & VISIBILITY
    # -------------------------------------------------------------------------
    category = fields.Selection(
        selection=[
            ("id_doc", "Identity Document"),
            ("medical_record", "Medical Record"),
            ("lab_result", "Lab Result"),
            ("imaging", "Imaging"),
            ("pre_photo", "Pre-op Photo"),
            ("post_photo", "Post-op Photo"),
            ("consent_support", "Consent Supporting Doc"),
            ("external_legal", "External Legal Document"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        index=True,
        help="Attachment classification to support search and policies."
    )

    confidentiality = fields.Selection(
        selection=[
            ("internal", "Internal Only"),
            ("patient", "Visible to Patient"),
            ("third_party", "Shareable to Third-Party"),
        ],
        string="Confidentiality",
        default="internal",
        help="Visibility and sharing policy for this attachment."
    )

    show_on_portal = fields.Boolean(
        string="Show on Portal",
        default=False,
        help="If enabled, the attachment appears on the patient portal under the related consent."
    )

    requires_redaction = fields.Boolean(
        string="Requires Redaction",
        help="Indicates that sensitive information must be redacted before sharing."
    )

    # -------------------------------------------------------------------------
    # STORAGE (IR.ATTACHMENT OR EXTERNAL URL)
    # -------------------------------------------------------------------------
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        ondelete="set null",
        help="Linked file stored in Odoo filestore."
    )

    external_url = fields.Char(
        string="External URL",
        help="External link to the document if not stored as an Odoo attachment."
    )

    file_name = fields.Char(
        string="Filename",
        compute="_compute_file_meta",
        store=True,
        help="Filename derived from the linked attachment."
    )

    mimetype = fields.Char(
        string="MIME Type",
        compute="_compute_file_meta",
        store=True,
        help="MIME type derived from the linked attachment."
    )

    file_size = fields.Integer(
        string="File Size (bytes)",
        compute="_compute_file_meta",
        store=True,
        help="Size in bytes derived from the linked attachment."
    )

    checksum = fields.Char(
        string="Checksum",
        compute="_compute_file_meta",
        store=True,
        help="Checksum derived from the linked attachment."
    )

    # Redacted version (if any)
    redacted_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Redacted Attachment",
        ondelete="set null",
        help="Optional redacted copy of the attachment for sharing."
    )

    # -------------------------------------------------------------------------
    # ORIGINS & AUDIT
    # -------------------------------------------------------------------------
    origin = fields.Selection(
        selection=[
            ("backend_user", "Backend User Upload"),
            ("portal_patient", "Portal (Patient)"),
            ("api", "External API"),
            ("scanner", "Scanner/Import"),
            ("camera", "Camera Capture"),
            ("import", "Data Import"),
        ],
        string="Origin",
        default="backend_user",
        help="How this attachment was acquired."
    )

    uploaded_by = fields.Many2one(
        "res.users",
        string="Uploaded By",
        default=lambda self: self.env.user,
        help="User who uploaded/linked the attachment."
    )

    uploaded_on = fields.Datetime(
        string="Uploaded On",
        default=lambda self: fields.Datetime.now(),
        help="Timestamp when the attachment was uploaded/linked."
    )

    note = fields.Text(
        string="Internal Notes",
        help="Internal notes regarding this attachment."
    )

    # Portal deep-link (anchor), consistent with consent/signature anchors
    access_url = fields.Char(
        string="Portal URL (Anchor)",
        compute="_compute_access_url",
        help="Public portal URL (anchor to this attachment) for the parent consent."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("attachment_id")
    def _compute_file_meta(self):
        for rec in self:
            att = rec.attachment_id.sudo() if rec.attachment_id else False
            rec.file_name = att.name if att else False
            rec.mimetype = att.mimetype if att else False
            rec.file_size = att.file_size if att and hasattr(att, "file_size") else False
            rec.checksum = att.checksum if att and hasattr(att, "checksum") else False

    def _compute_access_url(self):
        for rec in self:
            base = rec.form_id.access_url or f"/my/consents/{rec.form_id.id}"
            rec.access_url = f"{base}#att-{rec.id}"

    # -------------------------------------------------------------------------
    # CONSTRAINTS & SANITY CHECKS
    # -------------------------------------------------------------------------
    _unique_attachment_per_form = models.Constraint(
        "unique(form_id, attachment_id)",
        "The same file is already linked to this consent.",
    )

    @api.constrains("attachment_id", "external_url")
    def _check_attachment_or_url(self):
        for rec in self:
            if not rec.attachment_id and not rec.external_url:
                raise ValidationError(_("Please provide either an Attachment or an External URL."))

    @api.constrains("show_on_portal", "confidentiality")
    def _check_portal_visibility_policy(self):
        for rec in self:
            if rec.show_on_portal and rec.confidentiality not in ("patient", "third_party"):
                raise ValidationError(_(
                    "Attachments shown on the portal must have confidentiality 'Visible to Patient' "
                    "or 'Shareable to Third-Party'."
                ))

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _ensure_editable(self):
        """Prevent edits on attachments when form is signed/archived, except benign fields."""
        for rec in self:
            if rec.form_id.state in ("signed", "archived"):
                raise AccessError(_("You cannot modify attachments of a signed or archived consent."))

    def _ensure_deletable(self):
        for rec in self:
            if rec.form_id.state not in ("draft", "cancelled"):
                raise AccessError(_("You can only delete attachments when the consent is Draft or Cancelled."))

    def _link_attachment_to_form(self):
        """
        Ensure ir.attachment is linked to the consent record (res_model/res_id).
        This keeps all files discoverable from the consent's 'Attachments' smart button.
        """
        for rec in self:
            if not rec.attachment_id:
                continue
            att = rec.attachment_id.sudo()
            # Link only if not already referencing the form
            if getattr(att, "res_model", False) != rec.form_id._name or getattr(att, "res_id", 0) != rec.form_id.id:
                att.write({
                    "res_model": rec.form_id._name,
                    "res_id": rec.form_id.id,
                })

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # After create: propagate filename/meta and link ir.attachment to the consent
        for rec in records:
            rec._link_attachment_to_form()
            rec._compute_file_meta()
            # Auto-policy: if confidentiality is 'patient', auto-enable show_on_portal
            if rec.confidentiality == "patient" and not rec.show_on_portal:
                rec.write({"show_on_portal": True})
        return records

    def write(self, vals):
        # Guard writes when parent is signed/archived (allow benign fields)
        benign_fields = {
            "activity_exception_decoration", "message_follower_ids", "message_ids",
            "message_main_attachment_id", "activity_ids", "activity_state",
            "activity_user_id", "activity_type_id", "activity_date_deadline",
            "note", "sequence", "show_on_portal", "confidentiality",
        }
        if any(rec.form_id.state in ("signed", "archived") for rec in self):
            forbidden = set(vals.keys()) - benign_fields
            if forbidden:
                raise AccessError(_("You cannot modify attachments of a signed or archived consent."))
        res = super().write(vals)
        # Refresh metadata & ensure ir.attachment link if attachment_id updated
        if "attachment_id" in vals:
            for rec in self:
                rec._link_attachment_to_form()
        if {"attachment_id"} & set(vals.keys()):
            self._compute_file_meta()
        return res

    def unlink(self):
        self._ensure_deletable()
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_open_attachment_record(self):
        """Open the underlying ir.attachment in a form view."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("No Odoo attachment is linked to this record."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Attachment"),
            "res_model": "ir.attachment",
            "view_mode": "form",
            "res_id": self.attachment_id.id,
            "target": "current",
        }

    def action_open_in_portal(self):
        """Open the consent portal page anchored to this attachment."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    def action_mark_portal_visible(self):
        self.write({"show_on_portal": True, "confidentiality": "patient"})

    def action_mark_portal_hidden(self):
        self.write({"show_on_portal": False})

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("attachment_id")
    def _onchange_attachment_id(self):
        """Update computed meta early in the UI and auto-fill name if empty."""
        if self.attachment_id:
            att = self.attachment_id.sudo()
            self.file_name = att.name
            self.mimetype = att.mimetype
            self.file_size = att.file_size if hasattr(att, "file_size") else False
            self.checksum = att.checksum if hasattr(att, "checksum") else False
            if not self.name and att.name:
                self.name = att.name

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "category")
    def _compute_display_name(self):
        labels = dict(self._fields["category"].selection)
        for rec in self:
            label = rec.name or _("Attachment")
            if rec.category:
                label = f"[{labels.get(rec.category, rec.category)}] {label}"
            rec.display_name = label

    def name_get(self):
        return [(rec.id, rec.display_name) for rec in self]
