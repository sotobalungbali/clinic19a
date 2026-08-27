
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_signature.py
#
# Signature ledger for ClinicOne Consent & Legal Forms (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Purpose:
#   - Persistent, append-only style log of signatures tied to a consent form
#   - Supports multiple roles (patient, guardian, doctor, witness, staff)
#   - Stores signature image, device info, IP, timestamp, content snapshot & checksum
#   - Allows revocation (with reason) and superseding when new versions are signed
#
# Integration notes:
#   - Primary link to `clinic.consent.form` (see consent_form.py)
#   - Soft-coupled to other modules via optional links (booking/encounter/room session)
#   - Portal anchoring points to parent consent URL with signature anchor
#
# Typical flow:
#   - Controllers/wizards call `clinic.consent.form.action_sign(...)`
#   - Additionally create a `clinic.consent.signature` entry via `create_from_consent(...)`
#
import hashlib
import json
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import format_datetime


class ConsentSignature(models.Model):
    _name = "clinic.consent.signature"
    _description = "Consent Signature (Ledger)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "signed_on desc, id desc"

    # -------------------------------------------------------------------------
    # CORE / LINKS
    # -------------------------------------------------------------------------
    form_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent Form",
        required=True,
        ondelete="cascade",
        index=True,
        help="The consent form this signature is associated with."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="form_id.company_id",
        store=True,
        index=True,
        readonly=True
    )

    # Convenience relateds for filtering/reporting
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
        help="Optional: link to appointment present at signing time."
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Optional: link to clinical encounter present at signing time."
    # )
    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Optional: link to room session present at signing time."
    )

    # -------------------------------------------------------------------------
    # SIGNER INFO
    # -------------------------------------------------------------------------
    role = fields.Selection(
        selection=[
            ("patient", "Patient"),
            ("guardian", "Guardian/Representative"),
            ("doctor", "Doctor"),
            ("witness", "Witness"),
            ("staff", "Staff"),
        ],
        string="Signature Role",
        required=True,
        default="patient",
        help="Role of the person who signed."
    )

    signer_name = fields.Char(
        string="Signer Full Name",
        required=True,
        help="Full name as it should appear on the legal document."
    )

    relationship = fields.Selection(
        selection=[
            ("self", "Self (Patient)"),
            ("guardian_parent", "Guardian/Parent"),
            ("guardian_legal", "Legal Guardian/Representative"),
            ("other", "Other Authorized Person"),
        ],
        string="Signer Relationship",
        default="self",
        help="Relationship of the signer to the patient (for non-patient signatures)."
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Signer (Partner)",
        ondelete="set null",
        help="If the signer exists in contacts, link here."
    )

    user_id = fields.Many2one(
        "res.users",
        string="Signed By (User)",
        ondelete="set null",
        help="If signed by a logged-in internal user (e.g., staff/doctor countersign)."
    )

    signature_image = fields.Binary(
        string="Signature Image",
        attachment=True,
        help="Captured e-signature image (PNG)."
    )

    signed_on = fields.Datetime(
        string="Signed On",
        required=True,
        default=lambda self: fields.Datetime.now(),
        index=True,
        help="Timestamp when the signature was recorded."
    )

    ip_address = fields.Char(
        string="IP Address",
        help="Public IP captured at the moment of signature (if available)."
    )
    user_agent = fields.Char(
        string="User-Agent",
        help="Client user-agent string captured at the moment of signature (if available)."
    )
    device_hint = fields.Char(
        string="Device Hint",
        help="Optional hint (e.g., 'iPad kiosk', 'Nurse station terminal', etc.)."
    )

    # -------------------------------------------------------------------------
    # STATE & AUDIT
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("signed", "Signed"),
            ("revoked", "Revoked"),
            ("superseded", "Superseded"),
        ],
        string="Status",
        default="signed",
        tracking=True,
        help="Signature status in the ledger."
    )

    revoke_reason = fields.Text(
        string="Revoke Reason",
        help="Reason for revocation, if any."
    )
    revoked_on = fields.Datetime(
        string="Revoked On",
        help="Timestamp when the signature was revoked."
    )

    content_version = fields.Char(
        string="Consent Version",
        help="Consent content version at the time of signing (copied from form)."
    )

    content_checksum = fields.Char(
        string="Content Integrity Hash",
        help="SHA256 hash of key legal fields at signing time."
    )

    content_snapshot = fields.Text(
        string="Content Snapshot (JSON)",
        help="JSON snapshot of key fields from consent form to support full audit."
    )

    access_url = fields.Char(
        string="Portal URL (Anchor)",
        compute="_compute_access_url",
        help="Public portal URL (anchor to this signature) for the parent consent."
    )

    is_latest_for_role = fields.Boolean(
        string="Is Latest For Role",
        compute="_compute_is_latest_for_role",
        help="True if this is the latest non-revoked signature for the given role on this form."
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    # Do NOT force uniqueness by role; allow multiple signatures (e.g., re-sign).
    _signed_on_required = models.Constraint(
        "CHECK(signed_on IS NOT NULL)",
        "Signed On must be set.",
    )

    @api.constrains("signature_image", "state")
    def _check_signature_image_required(self):
        for rec in self:
            if rec.state == "signed" and not rec.signature_image:
                raise ValidationError(_("Signature Image is required for a signed record."))

    @api.constrains("form_id", "state")
    def _check_form_state(self):
        for rec in self:
            if rec.form_id and rec.state == "signed" and rec.form_id.state not in ("to_sign", "signed"):
                # Allow historical imports via context 'allow_historical_signature'
                if not rec.env.context.get("allow_historical_signature"):
                    raise ValidationError(_(
                        "The parent consent must be in 'Waiting for Signature' or 'Signed' "
                        "to accept a signature."
                    ))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_access_url(self):
        for rec in self:
            # Anchor to parent consent portal URL using signature anchor
            # Parent consent computes: /my/consents/<id>
            base = rec.form_id.access_url or f"/my/consents/{rec.form_id.id}"
            rec.access_url = f"{base}#sig-{rec.id}"

    def _compute_is_latest_for_role(self):
        for rec in self:
            # Latest = most recent (by signed_on, id tiebreak) that is not revoked
            latest = self.search([
                ("form_id", "=", rec.form_id.id),
                ("role", "=", rec.role),
                ("state", "!=", "revoked"),
            ], order="signed_on desc, id desc", limit=1)
            rec.is_latest_for_role = (latest.id == rec.id) if latest else False

    # -------------------------------------------------------------------------
    # HELPERS: SNAPSHOT & CHECKSUM
    # -------------------------------------------------------------------------
    def _build_snapshot_dict(self):
        """Return a minimal JSON-serializable snapshot of the form & context at signing time."""
        self.ensure_one()
        f = self.form_id.sudo()
        snapshot = {
            "company_id": f.company_id.id if f.company_id else False,
            "patient_id": f.patient_id.id if f.patient_id else False,
            "doctor_id": f.doctor_id.id if f.doctor_id else False,
            "treatment_id": f.treatment_id.id if f.treatment_id else False,
            "booking_id": f.booking_id.id if f.booking_id else False,
            # "encounter_id": f.encounter_id.id if f.encounter_id else False,
            "room_session_id": f.room_session_id.id if f.room_session_id else False,

            "title": f.title or "",
            "content_html": f.content_html or "",
            "content_text": f.content_text or "",
            "risks_and_complications": f.risks_and_complications or "",
            "alternatives": f.alternatives or "",

            "required_before_procedure": bool(f.required_before_procedure),
            "validity_days": int(f.validity_days or 0),
            "consent_version": f.consent_version or "",

            # light denorms for search/report
            "form_state": f.state or "",
            "form_name": f.name or "",
        }
        return snapshot

    @api.model
    def _compute_checksum_from_payload(self, payload_dict, signer_name, role, signed_dt):
        """Compute a SHA256 checksum of key content composed with signer identity."""
        items = [
            # content payload
            ("payload", json.dumps(payload_dict, sort_keys=True, ensure_ascii=False)),
            # signer info
            ("signer_name", signer_name or ""),
            ("role", role or ""),
            ("signed_dt", format_datetime(self.env, signed_dt) if signed_dt else ""),
        ]
        raw = "|".join([f"{k}={v}" for k, v in items])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------------------
    # FACTORY: CREATE FROM CONSENT
    # -------------------------------------------------------------------------
    @api.model
    def create_from_consent(
        self,
        form_id,
        role="patient",
        signer_name=None,
        signature_image=None,
        relationship="self",
        partner_id=False,
        user_id=False,
        ip_address=False,
        user_agent=False,
        device_hint=False,
        booking_id=False,
        # encounter_id=False,
        room_session_id=False,
        signed_on=False,
    ):
        """
        Create a signature ledger entry for a given consent form.
        Raises if basic requirements are not met.

        Typical usage:
            env['clinic.consent.signature'].create_from_consent(
                form_id=form.id,
                role='patient',
                signer_name='John Doe',
                signature_image=b64png,
                ip_address=request.httprequest.remote_addr,
                user_agent=request.httprequest.user_agent.string,
            )
        """
        Consent = self.env["clinic.consent.form"]
        form = Consent.browse(form_id).exists()
        if not form:
            raise UserError(_("Consent Form not found."))

        if form.state not in ("to_sign", "signed"):
            # Allow backfill with context flag
            if not self.env.context.get("allow_historical_signature"):
                raise UserError(_("The consent is not in a signable state."))

        if not signer_name:
            raise UserError(_("Signer Full Name is required."))

        when = signed_on or fields.Datetime.now()

        # Build content snapshot & checksum
        # We use a new transient record (not stored yet) to access helper cleanly
        dummy = self.new({"form_id": form.id})
        payload = dummy._build_snapshot_dict()
        checksum = self._compute_checksum_from_payload(
            payload_dict=payload,
            signer_name=signer_name,
            role=role,
            signed_dt=when,
        )

        vals = {
            "form_id": form.id,
            "role": role,
            "signer_name": signer_name,
            "relationship": relationship or "self",
            "partner_id": partner_id or False,
            "user_id": user_id or False,

            "signature_image": signature_image,
            "signed_on": when,

            "ip_address": ip_address or False,
            "user_agent": user_agent or False,
            "device_hint": device_hint or False,

            "booking_id": booking_id or form.booking_id.id or False,
            # "encounter_id": encounter_id or form.encounter_id.id or False,
            "room_session_id": room_session_id or form.room_session_id.id or False,

            "state": "signed",
            "content_version": form.consent_version or False,
            "content_checksum": checksum,
            "content_snapshot": json.dumps(payload, ensure_ascii=False),
        }
        rec = self.create(vals)

        # Post a chatter message on parent form for traceability
        form.message_post(
            body=_("Signature recorded (%s) by <b>%s</b>.") % (rec.role, rec.signer_name),
            subtype_xmlid="mail.mt_note",
        )
        return rec

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_revoke(self, reason=None):
        """Revoke signature with an optional reason."""
        for rec in self:
            if rec.state != "signed":
                raise UserError(_("Only 'Signed' signatures can be revoked."))
            rec.write({
                "state": "revoked",
                "revoke_reason": reason or rec.revoke_reason or _("Revoked"),
                "revoked_on": fields.Datetime.now(),
            })
            rec.form_id.message_post(
                body=_("Signature revoked (%s) by <b>%s</b>. Reason: %s") %
                     (rec.role, rec.signer_name, rec.revoke_reason or "-"),
                subtype_xmlid="mail.mt_note",
            )

    def action_mark_superseded(self):
        """Mark signature as superseded (e.g., when a newer version is signed)."""
        for rec in self:
            if rec.state != "signed":
                # Allow idempotent supersede on non-signed states (no-op)
                continue
            rec.write({"state": "superseded"})
            rec.form_id.message_post(
                body=_("Signature marked as superseded (%s) for <b>%s</b>.") %
                     (rec.role, rec.signer_name),
                subtype_xmlid="mail.mt_note",
            )

    def action_open_parent_consent(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": self.form_id.id,
            "target": "current",
        }

    def action_open_in_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    # -------------------------------------------------------------------------
    # UI / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("content_version", "role", "signer_name", "signed_on")
    def _compute_display_name(self):
        for rec in self:
            ts = format_datetime(self.env, rec.signed_on) if rec.signed_on else ""
            ver = f"[{rec.content_version}] " if rec.content_version else ""
            rec.display_name = f"{ver}{(rec.role or 'signature').capitalize()} - {rec.signer_name or _('Signer')} ({ts})"

    def name_get(self):
        return [(rec.id, rec.display_name) for rec in self]

    # -------------------------------------------------------------------------
    # CREATE/WRITE OVERRIDES (light guards)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Ensure each record has checksum & snapshot (if a direct create bypasses factory)
        for rec in records:
            if not rec.content_snapshot or not rec.content_checksum:
                payload = rec._build_snapshot_dict()
                checksum = rec._compute_checksum_from_payload(
                    payload_dict=payload,
                    signer_name=rec.signer_name,
                    role=rec.role,
                    signed_dt=rec.signed_on or fields.Datetime.now(),
                )
                rec.write({
                    "content_snapshot": json.dumps(payload, ensure_ascii=False),
                    "content_checksum": checksum,
                    "content_version": rec.form_id.consent_version or rec.content_version,
                })
        return records

    def write(self, vals):
        # Disallow mutating critical signer identity once signed, except for administrative corrections
        protected_when_signed = {"signer_name", "role", "signature_image", "signed_on"}
        if any(rec.state == "signed" for rec in self) and protected_when_signed & set(vals.keys()):
            # Allow via context flag when truly necessary
            if not self.env.context.get("allow_signature_identity_edit"):
                raise AccessError(_("Editing signer identity or signature content is not allowed."))
        return super().write(vals)
 
    def unlink(self):
        """Signature ledger rows are immutable legal evidence."""
        if not self.env.context.get("allow_signature_ledger_unlink"):
            raise AccessError(_("Signature ledger entries cannot be deleted. Revoke or supersede them instead."))
        return super().unlink()
