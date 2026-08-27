import base64
import binascii
import hashlib
import mimetypes
from pathlib import Path

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}


class ClinicTelemedicineAttachment(models.Model):
    """Secure file-sharing evidence bound to an exact Thread and Message."""

    _name = "clinic.telemedicine.attachment"
    _description = "Clinic Telemedicine Secure Attachment"
    _order = "uploaded_at desc, id desc"
    _check_company_auto = True

    _thread_upload_idx = models.Index(
        "(thread_id, uploaded_at, uploader_kind)"
    )

    thread_id = fields.Many2one(
        "clinic.telemedicine.thread",
        required=True,
        ondelete="cascade",
        index=True,
    )
    message_id = fields.Many2one(
        "clinic.telemedicine.message",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="thread_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    patient_id = fields.Many2one(
        related="thread_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="thread_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )

    name = fields.Char(string="Filename", required=True)
    datas = fields.Binary(
        string="File",
        required=True,
        attachment=True,
    )
    mimetype = fields.Char(required=True, readonly=True, index=True)
    size_bytes = fields.Integer(readonly=True)
    sha256 = fields.Char(readonly=True, index=True)

    uploader_kind = fields.Selection(
        [
            ("patient", "Patient"),
            ("clinic", "Clinic"),
            ("system", "System"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    uploaded_by_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        index=True,
    )
    uploaded_by_partner_id = fields.Many2one(
        "res.partner",
        readonly=True,
        index=True,
    )
    uploaded_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        index=True,
    )

    @api.model
    def _decode_payload(self, datas):
        if not datas:
            raise ValidationError(_("A file is required."))
        payload = datas.encode() if isinstance(datas, str) else datas
        try:
            return base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValidationError(_("Uploaded file data is invalid.")) from exc

    @api.model
    def _validate_file_payload(self, values, company):
        filename = (values.get("name") or "").strip()
        if not filename:
            raise ValidationError(_("A filename is required."))

        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                _("Only PDF, JPG/JPEG, and PNG files are allowed.")
            )

        mimetype = (
            values.get("mimetype")
            or mimetypes.guess_type(filename)[0]
            or ""
        ).lower()
        if mimetype not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                _("Only PDF, JPEG, and PNG MIME types are allowed.")
            )

        guessed = mimetypes.guess_type(filename)[0]
        if guessed and guessed.lower() not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                _("Filename extension and declared file type are inconsistent.")
            )

        raw = self._decode_payload(values.get("datas"))

        # Extension and declared MIME are not sufficient for secure sharing.
        # Verify a minimal binary signature before accepting the payload.
        signature_ok = {
            "application/pdf": raw.startswith(b"%PDF-"),
            "image/jpeg": raw.startswith(b"\\xff\\xd8\\xff"),
            "image/png": raw.startswith(b"\\x89PNG\\r\\n\\x1a\\n"),
        }.get(mimetype, False)
        if not signature_ok:
            raise ValidationError(
                _("File content does not match the declared PDF/JPEG/PNG type.")
            )

        max_mb = company.clinic_telemedicine_max_file_mb or 10
        max_bytes = max_mb * 1024 * 1024
        if len(raw) > max_bytes:
            raise ValidationError(
                _(
                    "File exceeds the company limit of %(limit)s MB."
                ) % {"limit": max_mb}
            )

        return {
            "name": filename,
            "mimetype": mimetype,
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    @api.model_create_multi
    def create(self, vals_list):
        portal_upload = self.env.context.get(
            "telemedicine_portal_patient_upload"
        )
        portal_partner_id = self.env.context.get(
            "telemedicine_portal_partner_id"
        )
        portal_user_id = self.env.context.get(
            "telemedicine_portal_user_id"
        )
        system_upload = self.env.context.get(
            "telemedicine_system_attachment"
        )

        if not portal_upload and not system_upload and not self.env.su:
            if not self.env.user.has_group(
                "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
            ):
                raise AccessError(
                    _("Telemedicine Clinician access is required to share files.")
                )

        prepared = []
        Thread = self.env["clinic.telemedicine.thread"]
        Message = self.env["clinic.telemedicine.message"]

        for original in vals_list:
            vals = dict(original)
            thread = Thread.browse(vals.get("thread_id")).exists()
            message = Message.browse(vals.get("message_id")).exists()
            if not thread or not message:
                raise ValidationError(
                    _("Secure file sharing requires a valid Thread and Message.")
                )
            if message.thread_id != thread:
                raise ValidationError(
                    _("The Attachment Message belongs to another Secure Thread.")
                )
            if thread.state != "open" and not system_upload:
                raise UserError(
                    _("Files can only be shared in an Open Secure Thread.")
                )

            if portal_upload:
                if (
                    thread.partner_id.id != portal_partner_id
                    or not thread.patient_can_upload
                ):
                    raise AccessError(
                        _("This patient cannot upload files to the selected Thread.")
                    )

            validated = self._validate_file_payload(
                vals,
                thread.company_id,
            )
            vals.update(validated)

            # Uploader identity is server-owned evidence.
            vals.pop("uploader_kind", None)
            vals.pop("uploaded_by_user_id", None)
            vals.pop("uploaded_by_partner_id", None)
            vals.pop("uploaded_at", None)

            if portal_upload:
                portal_user = self.env["res.users"].browse(
                    portal_user_id
                ).exists()
                vals.update({
                    "uploader_kind": "patient",
                    "uploaded_by_user_id": portal_user.id if portal_user else False,
                    "uploaded_by_partner_id": thread.partner_id.id,
                })
            elif system_upload:
                vals.update({
                    "uploader_kind": "system",
                    "uploaded_by_user_id": self.env.user.id,
                    "uploaded_by_partner_id": self.env.user.partner_id.id,
                })
            else:
                vals.update({
                    "uploader_kind": "clinic",
                    "uploaded_by_user_id": self.env.user.id,
                    "uploaded_by_partner_id": self.env.user.partner_id.id,
                })

            prepared.append(vals)

        return super().create(prepared)

    def write(self, vals):
        raise AccessError(
            _(
                "Secure Attachment evidence is immutable after upload. "
                "Share a new corrected file instead."
            )
        )

    def unlink(self):
        if not self.env.su:
            raise AccessError(
                _(
                    "Secure Attachment evidence cannot be deleted through "
                    "normal business operations."
                )
            )
        return super().unlink()

    @api.constrains("thread_id", "message_id", "company_id", "patient_id")
    def _check_scope(self):
        for attachment in self:
            if attachment.message_id.thread_id != attachment.thread_id:
                raise ValidationError(
                    _("Attachment Message does not match its Secure Thread.")
                )
            if attachment.company_id != attachment.thread_id.company_id:
                raise ValidationError(
                    _("Attachment company does not match its Secure Thread.")
                )
            if attachment.patient_id != attachment.thread_id.patient_id:
                raise ValidationError(
                    _("Attachment patient does not match its Secure Thread.")
                )

    def action_download(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/clinic/telemedicine/attachment/{self.id}/download",
            "target": "new",
        }

    def action_open_thread(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Secure Thread"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "form",
            "res_id": self.thread_id.id,
        }

    def action_open_message(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Secure Message"),
            "res_model": "clinic.telemedicine.message",
            "view_mode": "form",
            "res_id": self.message_id.id,
        }

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Card"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

