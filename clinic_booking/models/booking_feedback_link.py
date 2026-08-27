# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_feedback_link.py
#
# Purpose
# -------
# Manage post-visit feedback invitations:
# - Generate secure tokenized links per booking/patient
# - Build public URL (portal/website) to collect feedback
# - Send email/SMS (email implemented via mail.template)
# - Track lifecycle: draft → queued → sent → opened → submitted / expired / revoked
# - Optional reminders; auto-expire by cron
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking (mandatory link) / patient/doctor/treatment (related)
# - booking.channel (default feedback template + optional website route)
# - booking.policy (for retention rules; optional)
# - mail.template / mail.mail (outbound email)
# - portal/website controller should validate token and call 'action_mark_opened' / 'action_submit_feedback'
#
# Notes
# -----
# - All user-facing strings are in English.
# - Controllers/views/templates are defined elsewhere (controllers/ & data/ XML).
# - This model is safe to use even if website/portal is not installed; link builds from base URL.

import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BookingFeedbackLink(models.Model):
    _name = "booking.feedback.link"
    _description = "Booking Feedback Link"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    # -------------------------------------------------------------------------
    # CORE RELATIONS / CONTEXT
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default="/",
        help="Internal reference for this feedback invitation.",
        tracking=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        required=True,
        ondelete="cascade",
        index=True,
        help="The booking for which this feedback is requested.",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="booking_id.company_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="booking_id.doctor_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="booking_id.treatment_id",
        store=True,
        readonly=True,
    )
    channel_id = fields.Many2one(
        "booking.channel",
        string="Channel",
        help="Channel driving default templates and website route, if any.",
    )
    policy_id = fields.Many2one(
        "booking.policy",
        string="Policy",
        help="Optional policy context for retention/terms.",
    )

    # -------------------------------------------------------------------------
    # TOKEN & ACCESS
    # -------------------------------------------------------------------------
    token = fields.Char(
        string="Access Token",
        required=True,
        copy=False,
        index=True,
        help="Opaque token used for secure public access.",
    )
    access_path = fields.Char(
        string="Access Path",
        compute="_compute_access_path",
        store=True,
        help="Relative path used to build the public URL (includes token).",
    )
    access_url = fields.Char(
        string="Public URL",
        compute="_compute_access_url",
        help="Absolute URL constructed from base URL + Access Path.",
    )

    allow_anonymous_update = fields.Boolean(
        string="Allow Anonymous Update",
        default=True,
        help="If enabled, public visitors can submit feedback using only the token.",
    )

    # -------------------------------------------------------------------------
    # LIFECYCLE / STATUS
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("opened", "Opened"),
            ("submitted", "Submitted"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
        help="Lifecycle status of the feedback invitation.",
    )
    sent_at = fields.Datetime(
        string="Sent At",
        help="Timestamp when the invitation was sent.",
        tracking=True,
    )
    opened_at = fields.Datetime(
        string="First Opened At",
        help="Timestamp when the public link was first opened.",
        tracking=True,
    )
    submitted_at = fields.Datetime(
        string="Submitted At",
        help="Timestamp when feedback was submitted.",
        tracking=True,
    )
    expiration_days = fields.Integer(
        string="Valid For (days)",
        default=14,
        help="Number of days after which the link expires.",
    )
    expire_at = fields.Datetime(
        string="Expires At",
        compute="_compute_expire_at",
        store=True,
        help="Datetime when the link becomes invalid.",
    )
    is_expired = fields.Boolean(
        string="Is Expired",
        compute="_compute_is_expired",
        store=True,
        help="True if current time is past the expiration time.",
    )

    # Reminders (basic counters)
    reminder_count = fields.Integer(
        string="Reminders Sent",
        default=0,
        help="How many reminder emails were sent for this feedback link.",
    )
    last_reminder_at = fields.Datetime(
        string="Last Reminder At",
        help="Timestamp when the last reminder was sent.",
    )

    # -------------------------------------------------------------------------
    # COMMUNICATION TEMPLATES
    # -------------------------------------------------------------------------
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        domain=[("model", "=", "booking.feedback.link")],
        help="Template used when sending the feedback invitation.",
    )
    # Fallback to channel.feedback_template_id if not set

    # For audit/reference
    last_mail_id = fields.Many2one(
        "mail.mail",
        string="Last Mail",
        help="Technical link to the last mail sent for this invitation.",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # FEEDBACK CONTENT
    # -------------------------------------------------------------------------
    rating_value = fields.Selection(
        selection=[
            ("1", "1 - Very Dissatisfied"),
            ("2", "2 - Dissatisfied"),
            ("3", "3 - Neutral"),
            ("4", "4 - Satisfied"),
            ("5", "5 - Very Satisfied"),
        ],
        string="Rating",
        help="Overall rating given by the patient.",
    )
    comment = fields.Text(
        string="Comment",
        help="Free text feedback from the patient.",
    )
    would_recommend = fields.Selection(
        selection=[("yes", "Yes"), ("no", "No"), ("na", "Prefer not to say")],
        string="Would Recommend",
        help="Whether the patient would recommend our clinic to others.",
        default="na",
    )

    # Optional tags/labels for analytics
    tag_ids = fields.Many2many(
        "booking.tag",
        "booking_feedback_tag_rel",
        "link_id",
        "tag_id",
        string="Tags",
        help="Optional tags for grouping and reporting.",
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _token_uniq = models.Constraint(
        'unique(token)',
        'Access Token must be unique.',
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_booking.sequence_booking_feedback", raise_if_not_found=False)
        for vals in vals_list:
            # Name
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = seq._next() if seq else self.env["ir.sequence"].next_by_code("booking.feedback.link")
            # Token
            if not vals.get("token"):
                vals["token"] = uuid.uuid4().hex  # 32 chars, URL-safe
            # Defaults from booking if not set
            if vals.get("booking_id"):
                booking = self.env["booking.booking"].browse(vals["booking_id"])
                if booking:
                    vals.setdefault("channel_id", booking.channel_id.id or False)
                    vals.setdefault("policy_id", booking.policy_id.id or False)
            # Template fallback to channel
            if not vals.get("mail_template_id") and vals.get("channel_id"):
                channel = self.env["booking.channel"].browse(vals["channel_id"])
                if channel and channel.feedback_template_id:
                    vals["mail_template_id"] = channel.feedback_template_id.id
        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        # Prevent altering token after sending (safety)
        for rec in self:
            if rec.state in ("sent", "opened", "submitted") and "token" in vals:
                raise UserError(_("Token cannot be changed after the invitation has been sent."))
        return super().write(vals)

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("booking_id.end_datetime", "expiration_days", "state")
    def _compute_expire_at(self):
        for rec in self:
            base = rec.booking_id.end_datetime or fields.Datetime.now()
            if not rec.expiration_days or rec.expiration_days <= 0:
                # Infinite validity not recommended; cap at 365d for safety
                rec.expire_at = fields.Datetime.to_string(
                    fields.Datetime.from_string(base) + timedelta(days=365)
                )
            else:
                rec.expire_at = fields.Datetime.to_string(
                    fields.Datetime.from_string(base) + timedelta(days=rec.expiration_days)
                )

    @api.depends("expire_at", "state")
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_expired = bool(rec.expire_at and fields.Datetime.from_string(rec.expire_at) < now)
            # Optionally auto-mark state, but leave to cron to avoid surprise state flips in UI

    @api.depends("token", "channel_id.website_route")
    def _compute_access_path(self):
        """
        Build relative path for feedback collection:
        - Prefer channel.website_route if provided (e.g., '/clinic/feedback/')
        - Default to '/clinic/feedback/'
        Rules:
          - If route ends with '?', append 'token=...'
          - If route ends with '/', append token as path segment
          - Else, append '/{token}'
        """
        for rec in self:
            token = rec.token or ""
            route = (rec.channel_id.website_route or "/clinic/feedback/").strip()
            if not route.startswith("/"):
                route = "/" + route
            if route.endswith("?"):
                rec.access_path = f"{route}token={token}"
            elif route.endswith("/"):
                rec.access_path = f"{route}{token}"
            else:
                rec.access_path = f"{route}/{token}"

    def _get_base_url(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("web.base.url", default="http://localhost:8069")

    @api.depends("access_path")
    def _compute_access_url(self):
        base = self._get_base_url()
        for rec in self:
            rec.access_url = base.rstrip("/") + (rec.access_path or "")

    # -------------------------------------------------------------------------
    # ACTIONS — GENERATION & SENDING
    # -------------------------------------------------------------------------
    def action_generate_link(self):
        """Ensure token/path/url are generated and set state to queued."""
        for rec in self:
            if not rec.token:
                rec.token = uuid.uuid4().hex
            # Trigger compute
            rec._compute_access_path()
            rec._compute_access_url()
            if rec.state == "draft":
                rec.state = "queued"
            rec.message_post(body=_("Feedback link generated: <a href='%s' target='_blank'>Open</a>") % (rec.access_url,))

    def _get_mail_template(self):
        self.ensure_one()
        # Priority: record → channel.feedback_template → module default
        tmpl = self.mail_template_id
        if not tmpl and self.channel_id and self.channel_id.feedback_template_id:
            tmpl = self.channel_id.feedback_template_id
        if not tmpl:
            tmpl = self.env.ref("clinic_booking.booking_feedback_email_template", raise_if_not_found=False)
        return tmpl

    def _prepare_mail_context(self):
        self.ensure_one()
        # Context variables usable in qweb template
        return {
            "feedback_link": self,
            "booking": self.booking_id,
            "patient": self.patient_id,
            "doctor": self.doctor_id,
            "treatment": self.treatment_id,
            "access_url": self.access_url,
            "token": self.token,
            "company": self.company_id,
        }

    def action_send_invitation(self, force_send=True):
        """Send the feedback invitation via email using the selected template."""
        for rec in self:
            if rec.is_expired or rec.state in ("expired", "revoked"):
                raise UserError(_("Cannot send an expired or revoked invitation."))
            if not rec.patient_id or not rec.patient_id.email:
                raise UserError(_("Patient has no email address."))

            tmpl = rec._get_mail_template()
            if not tmpl:
                raise UserError(_("No email template configured for feedback invitations."))

            # Ensure link
            if not rec.token:
                rec.token = uuid.uuid4().hex
                rec._compute_access_path()
                rec._compute_access_url()

            email_values = {"email_to": rec.patient_id.email}
            ctx = {"default_model": "booking.feedback.link", "default_res_id": rec.id}
            ctx.update(rec._prepare_mail_context())

            mail_id = tmpl.with_context(ctx).send_mail(rec.id, force_send=force_send, email_values=email_values)
            if mail_id:
                rec.last_mail_id = mail_id
            rec.sent_at = fields.Datetime.now()
            rec.state = "sent"
            rec.message_post(
                body=_("Feedback invitation sent to %s. <a href='%s' target='_blank'>Public link</a>") %
                     (rec.patient_id.email, rec.access_url)
            )
        return True

    def action_send_reminder(self, force_send=True):
        """Send a reminder email if not submitted and not expired."""
        for rec in self:
            if rec.state in ("submitted", "revoked"):
                raise UserError(_("This feedback link has already been completed or revoked."))
            if rec.is_expired:
                raise UserError(_("This feedback link is already expired."))
            rec.action_send_invitation(force_send=force_send)
            rec.reminder_count += 1
            rec.last_reminder_at = fields.Datetime.now()
            rec.message_post(body=_("Reminder sent."))

    # -------------------------------------------------------------------------
    # PUBLIC ENTRYPOINTS — called by controllers
    # -------------------------------------------------------------------------
    def action_mark_opened(self):
        """Mark as opened (first open only)."""
        for rec in self:
            if not rec.opened_at:
                rec.opened_at = fields.Datetime.now()
            if rec.state in ("sent", "queued", "draft"):
                rec.state = "opened"
            rec.message_post(body=_("Feedback link opened by recipient."))

    def action_submit_feedback(self, rating_value=None, comment=None, would_recommend=None):
        """Persist submitted feedback and mark as submitted."""
        for rec in self:
            if rec.is_expired or rec.state in ("expired", "revoked"):
                raise UserError(_("This feedback link is expired or revoked."))
            if rec.state == "submitted":
                # Idempotent updates allowed (overwrite if provided)
                pass

            # Apply values
            write_vals = {}
            if rating_value is not None:
                # Normalize to defined choices ('1'..'5' as strings)
                rating_value = str(rating_value)
                if rating_value not in dict(self._fields["rating_value"].selection):
                    raise UserError(_("Invalid rating value."))
                write_vals["rating_value"] = rating_value
            if comment is not None:
                write_vals["comment"] = comment
            if would_recommend is not None:
                would_recommend = str(would_recommend)
                if would_recommend not in dict(self._fields["would_recommend"].selection):
                    raise UserError(_("Invalid recommendation value."))
                write_vals["would_recommend"] = would_recommend

            write_vals["submitted_at"] = fields.Datetime.now()
            write_vals["state"] = "submitted"
            rec.write(write_vals)
            rec.message_post(body=_("Feedback submitted."))

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    @api.model
    def sudo_find_by_token(self, token):
        """Public-safe lookup by token for use in controllers."""
        if not token:
            return self.browse()
        return self.sudo().search([("token", "=", token)], limit=1)

    def action_open_public(self):
        """Open the public URL in a new tab (staff convenience)."""
        self.ensure_one()
        if not self.access_url:
            self.action_generate_link()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    def action_revoke(self, reason=None):
        """Invalidate the link (cannot be used anymore)."""
        for rec in self:
            rec.state = "revoked"
            if reason:
                rec.message_post(body=_("Feedback link revoked: %s") % reason)
            else:
                rec.message_post(body=_("Feedback link revoked."))

    # -------------------------------------------------------------------------
    # CRON — EXPIRATION
    # -------------------------------------------------------------------------
    @api.model
    def cron_expire_feedback_links(self):
        """Auto-expire links past 'expire_at' that are not yet submitted/revoked."""
        now = fields.Datetime.now()
        domain = [
            ("state", "in", ["draft", "queued", "sent", "opened"]),
            ("expire_at", "!=", False),
            ("expire_at", "<", now),
        ]
        to_expire = self.search(domain)
        for rec in to_expire:
            rec.state = "expired"
            rec.message_post(body=_("Feedback link expired automatically."))

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'booking_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Feedback")
            if rec.booking_id:
                label = f"{label} - {rec.booking_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("expiration_days")
    def _check_expiration_days(self):
        for rec in self:
            if rec.expiration_days is not None and rec.expiration_days < 0:
                raise ValidationError(_("Valid For (days) must be 0 or a positive number."))

    @api.constrains("patient_id")
    def _check_patient_email(self):
        for rec in self:
            # Not hard error: allow creating without email (could be SMS-only in future),
            # but if sending via email we will block there. Keep as soft guard if desired.
            pass


# -----------------------------------------------------------------------------
# OPTIONAL MIXIN — attach feedback to other models if needed
# -----------------------------------------------------------------------------
class BookingFeedbackLinkMixin(models.AbstractModel):
    _name = "booking.feedback.link.mixin"
    _description = "Feedback Link Mixin"

    feedback_link_ids = fields.One2many(
        "booking.feedback.link",
        "booking_id",
        string="Feedback Links",
        help="All feedback invitations associated with this record.",
    )

    def action_new_feedback_link(self):
        """Convenience action to create a feedback link from an inheriting record."""
        self.ensure_one()
        if self._name != "booking.booking":
            raise UserError(_("This helper is intended to be used from Booking."))
        vals = {
            "booking_id": self.id,
            "channel_id": self.channel_id.id if hasattr(self, "channel_id") and self.channel_id else False,
            "policy_id": self.policy_id.id if hasattr(self, "policy_id") and self.policy_id else False,
        }
        link = self.env["booking.feedback.link"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "booking.feedback.link",
            "view_mode": "form",
            "res_id": link.id,
            "target": "current",
        }
