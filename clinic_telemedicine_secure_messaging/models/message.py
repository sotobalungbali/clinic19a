from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


AUTHOR_KINDS = [
    ("patient", "Patient"),
    ("doctor", "Doctor"),
    ("staff", "Clinic Staff"),
    ("system", "System"),
]


class ClinicTelemedicineMessage(models.Model):
    """Immutable plain-text doctor-patient message evidence.

    Secure patient chat is intentionally not mirrored to generic mail.thread
    chatter or email. That prevents sensitive message text from being exposed
    through follower notification behavior.
    """

    _name = "clinic.telemedicine.message"
    _description = "Clinic Telemedicine Secure Message"
    _order = "sent_at asc, id asc"
    _check_company_auto = True

    _thread_sent_idx = models.Index("(thread_id, sent_at, author_kind)")

    thread_id = fields.Many2one(
        "clinic.telemedicine.thread",
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
    doctor_id = fields.Many2one(
        related="thread_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )

    author_kind = fields.Selection(
        AUTHOR_KINDS,
        required=True,
        readonly=True,
        index=True,
    )
    author_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        index=True,
    )
    author_partner_id = fields.Many2one(
        "res.partner",
        readonly=True,
        index=True,
    )
    author_staff_id = fields.Many2one(
        "clinic.staff",
        readonly=True,
        index=True,
    )
    sender_display_name = fields.Char(readonly=True)

    body = fields.Text(required=True)
    sent_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        index=True,
    )
    direction = fields.Selection(
        [
            ("patient_to_clinic", "Patient → Clinic"),
            ("clinic_to_patient", "Clinic → Patient"),
            ("system", "System"),
        ],
        compute="_compute_direction",
        store=True,
        index=True,
    )

    patient_read_at = fields.Datetime(readonly=True, index=True)
    clinic_read_at = fields.Datetime(readonly=True, index=True)

    attachment_ids = fields.One2many(
        "clinic.telemedicine.attachment",
        "message_id",
        string="Secure Attachments",
        readonly=True,
    )
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    @api.depends("author_kind")
    def _compute_direction(self):
        for message in self:
            if message.author_kind == "patient":
                message.direction = "patient_to_clinic"
            elif message.author_kind in ("doctor", "staff"):
                message.direction = "clinic_to_patient"
            else:
                message.direction = "system"

    def _compute_attachment_count(self):
        for message in self:
            message.attachment_count = len(message.attachment_ids)

    @api.model_create_multi
    def create(self, vals_list):
        portal_post = self.env.context.get(
            "telemedicine_portal_patient_message"
        )
        portal_partner_id = self.env.context.get(
            "telemedicine_portal_partner_id"
        )
        portal_user_id = self.env.context.get(
            "telemedicine_portal_user_id"
        )
        system_post = self.env.context.get(
            "telemedicine_system_message"
        )

        if not portal_post and not system_post and not self.env.su:
            if not self.env.user.has_group(
                "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
            ):
                raise AccessError(
                    _("Telemedicine Clinician access is required to send messages.")
                )

        prepared = []
        Thread = self.env["clinic.telemedicine.thread"]
        Staff = self.env["clinic.staff"]

        for original in vals_list:
            vals = dict(original)
            thread = Thread.browse(vals.get("thread_id")).exists()
            if not thread:
                raise ValidationError(_("A valid Secure Thread is required."))
            if thread.state != "open" and not system_post:
                raise UserError(_("Messages can only be sent to an Open Secure Thread."))

            body = (vals.get("body") or "").strip()
            if not body:
                raise ValidationError(_("Secure Message text is required."))
            max_chars = (
                thread.company_id.clinic_telemedicine_max_message_chars
                or 5000
            )
            if len(body) > max_chars:
                raise ValidationError(
                    _(
                        "Message exceeds the company limit of %(limit)s characters."
                    ) % {"limit": max_chars}
                )
            vals["body"] = body

            # Author identity is system-owned evidence; caller values are ignored.
            vals.pop("author_kind", None)
            vals.pop("author_user_id", None)
            vals.pop("author_partner_id", None)
            vals.pop("author_staff_id", None)
            vals.pop("sender_display_name", None)
            vals.pop("patient_read_at", None)
            vals.pop("clinic_read_at", None)

            now = fields.Datetime.now()
            vals.setdefault("sent_at", now)

            if portal_post:
                if (
                    thread.partner_id.id != portal_partner_id
                    or not thread.patient_can_reply
                ):
                    raise AccessError(
                        _("This patient cannot reply to the selected Secure Thread.")
                    )
                portal_user = self.env["res.users"].browse(
                    portal_user_id
                ).exists()
                vals.update({
                    "author_kind": "patient",
                    "author_user_id": portal_user.id if portal_user else False,
                    "author_partner_id": thread.partner_id.id,
                    "sender_display_name": thread.partner_id.display_name,
                    "patient_read_at": now,
                    "clinic_read_at": False,
                })

            elif system_post:
                vals.update({
                    "author_kind": "system",
                    "author_user_id": self.env.user.id,
                    "author_partner_id": self.env.user.partner_id.id,
                    "sender_display_name": _("ClinicOne System"),
                    "patient_read_at": False,
                    "clinic_read_at": now,
                })

            else:
                current_user = self.env.user
                staff = Staff.search([
                    ("partner_id", "=", current_user.partner_id.id),
                    ("company_id", "in", (False, thread.company_id.id)),
                ], limit=1)

                if (
                    thread.doctor_id.user_id
                    and thread.doctor_id.user_id == current_user
                ):
                    author_kind = "doctor"
                    sender_name = thread.doctor_id.display_name
                else:
                    author_kind = "staff"
                    sender_name = (
                        staff.display_name
                        if staff
                        else current_user.display_name
                    )

                vals.update({
                    "author_kind": author_kind,
                    "author_user_id": current_user.id,
                    "author_partner_id": current_user.partner_id.id,
                    "author_staff_id": staff.id if staff else False,
                    "sender_display_name": sender_name,
                    "patient_read_at": False,
                    "clinic_read_at": now,
                })

                # Assign a previously unassigned thread when the sender has a
                # concrete Clinic Staff identity.
                if staff and not thread.handler_id:
                    thread.handler_id = staff.id

            prepared.append(vals)

        messages = super().create(prepared)
        for message in messages:
            message.thread_id._record_message_metrics(message)
        return messages

    def write(self, vals):
        allowed = {"patient_read_at", "clinic_read_at"}
        if not (
            self.env.context.get("telemedicine_message_read")
            and set(vals).issubset(allowed)
        ):
            raise AccessError(
                _(
                    "Secure Messages are immutable after sending. "
                    "Only controlled read evidence may be updated."
                )
            )
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(
                _(
                    "Secure Message evidence cannot be deleted. "
                    "Archive/close the parent Thread instead."
                )
            )
        return super().unlink()

    @api.constrains("thread_id", "company_id", "patient_id")
    def _check_scope(self):
        for message in self:
            if message.company_id != message.thread_id.company_id:
                raise ValidationError(_("Message company does not match its Thread."))
            if message.patient_id != message.thread_id.patient_id:
                raise ValidationError(_("Message patient does not match its Thread."))

    def action_mark_clinic_read(self):
        if not self.env.su and not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
        ):
            raise AccessError(_("Telemedicine Clinician access is required."))
        messages = self.filtered(
            lambda message:
            message.author_kind == "patient"
            and not message.clinic_read_at
        )
        if messages:
            messages.sudo().with_context(
                telemedicine_message_read=True
            ).write({"clinic_read_at": fields.Datetime.now()})
        return True

    def _mark_patient_read(self):
        portal_partner_id = self.env.context.get(
            "telemedicine_portal_partner_id"
        )
        if not self.env.context.get("telemedicine_portal_patient_read"):
            raise AccessError(
                _("Patient read evidence requires a controlled Portal route.")
            )
        if self.filtered(
            lambda message: message.partner_id.id != portal_partner_id
        ):
            raise AccessError(
                _("Patient read evidence does not match the signed-in Patient Contact.")
            )
        messages = self.filtered(
            lambda message:
            message.author_kind != "patient"
            and not message.patient_read_at
        )
        if messages:
            messages.sudo().with_context(
                telemedicine_message_read=True
            ).write({"patient_read_at": fields.Datetime.now()})
        return True

    def action_open_thread(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Secure Thread"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "form",
            "res_id": self.thread_id.id,
        }

    def action_open_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Secure Attachments"),
            "res_model": "clinic.telemedicine.attachment",
            "view_mode": "list,form",
            "domain": [("message_id", "=", self.id)],
            "context": {
                "default_thread_id": self.thread_id.id,
                "default_message_id": self.id,
            },
        }

