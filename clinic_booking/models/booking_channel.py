# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_channel.py
#
# Purpose:
# - Define booking channels (Walk-in, Phone, Website, Portal, WhatsApp, etc.)
# - Centralize rules/policies per channel (deposit, cancellation, default mail templates)
# - Provide safe hooks for applying channel defaults into bookings
#
# Key integrations (soft-coupled):
# - booking.booking (channel_id -> this model)
# - booking.policy (channel-level default policy)
# - mail.template (reminder/feedback templates)
# - website (website_published flag for online channels)
# - account/currency/company awareness for deposit handling
#
# Notes:
# - All user-facing strings are in English, as requested.
# - Avoids external dependencies beyond what clinic_booking already declares.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BookingChannel(models.Model):
    _name = "booking.channel"
    _description = "Booking Channel"
    _order = "sequence, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # -------------------------------------------------------------------------
    # BASIC / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Channel Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the booking channel (e.g., Walk-in, Phone, Website, Portal).",
    )

    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code for this channel, e.g. 'walkin', 'phone', 'website'.",
    )

    channel_type = fields.Selection(
        selection=[
            ("walkin", "Walk-in"),
            ("phone", "Phone"),
            ("website", "Website"),
            ("portal", "Portal"),
            ("whatsapp", "WhatsApp"),
            ("marketplace", "Marketplace"),
            ("kiosk", "Kiosk"),
            ("mobile_app", "Mobile App"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="walkin",
        tracking=True,
        help="Classify the channel to enable type-specific behaviors (online flags, defaults, etc.).",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to hide this channel from selection while keeping historical references.",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower is earlier in lists. Used to order channels in selection widgets.",
    )

    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban/Calendar indicators for quick visual grouping.",
    )

    description = fields.Text(
        string="Description",
        help="Optional description or internal notes about this channel.",
    )

    # -------------------------------------------------------------------------
    # COMPANY / CURRENCY CONTEXT
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        required=True,
        help="Company to which this channel belongs.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # ONLINE FLAGS & WEBSITE EXPOSURE
    # -------------------------------------------------------------------------
    is_online = fields.Boolean(
        string="Online Channel",
        compute="_compute_is_online",
        store=True,
        help="True when the channel is used online (Website, Portal, Mobile App, Marketplace).",
    )

    website_published = fields.Boolean(
        string="Show on Website",
        help="If enabled, expose this channel to website features (forms/flows).",
    )

    website_route = fields.Char(
        string="Website Route",
        help="Optional website route/endpoint where this channel is used, e.g. '/book/clinic'.",
    )

    # -------------------------------------------------------------------------
    # DEFAULT POLICY & COMMUNICATION TEMPLATES
    # -------------------------------------------------------------------------
    policy_id = fields.Many2one(
        "booking.policy",
        string="Default Policy",
        index=True,
        help="Default policy to be applied when a booking is created with this channel.",
    )

    reminder_template_id = fields.Many2one(
        "mail.template",
        string="Reminder Email Template",
        domain=[("model", "=", "booking.booking")],
        help="Default reminder email template used for bookings of this channel.",
    )

    feedback_template_id = fields.Many2one(
        "mail.template",
        string="Feedback Email Template",
        domain=[("model", "=", "booking.booking")],
        help="Default feedback email template used after the booking is done.",
    )

    # -------------------------------------------------------------------------
    # DEPOSIT / PREPAID SETTINGS (OPTIONAL)
    # -------------------------------------------------------------------------
    allow_prepaid_deposit = fields.Boolean(
        string="Allow Prepaid Deposit",
        help="Enable this to require or allow a deposit for bookings from this channel.",
    )

    deposit_is_required = fields.Boolean(
        string="Deposit Required",
        help="If enabled, a deposit is mandatory for bookings from this channel.",
    )

    deposit_fixed_amount = fields.Monetary(
        string="Deposit Fixed Amount",
        currency_field="currency_id",
        help="Fixed deposit amount to request for bookings in this channel. "
             "Leave 0.0 if using percentage.",
    )

    deposit_percent = fields.Float(
        string="Deposit Percentage",
        help="Deposit percentage to request for bookings in this channel (0 - 100). "
             "Leave 0.0 if using fixed amount.",
    )

    # -------------------------------------------------------------------------
    # AUTOMATION & BEHAVIOR
    # -------------------------------------------------------------------------
    auto_create_appointment = fields.Boolean(
        string="Auto-create Appointment on Confirm",
        help="When enabled, confirming a booking will attempt to create/link a clinic.appointment "
             "in the clinic_doctor module following configured handshake rules.",
    )

    lock_slot_on_confirm = fields.Boolean(
        string="Lock Slot on Confirm",
        help="If enabled, the selected slot becomes locked to prevent double-booking in parallel flows.",
    )

    # -------------------------------------------------------------------------
    # STATS / LINKS
    # -------------------------------------------------------------------------
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of bookings created under this channel (excluding archived).",
    )

    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recent booking made via this channel (by create date).",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Channel Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Channel Name must be unique per company.',
    )

    @api.constrains("code")
    def _check_code_format(self):
        for rec in self:
            if rec.code:
                if " " in rec.code:
                    raise ValidationError(_("Channel Technical Code must not contain spaces."))
                if not rec.code.replace("_", "").replace("-", "").isalnum():
                    raise ValidationError(_("Channel Technical Code must be alphanumeric (underscores/dashes allowed)."))

    @api.constrains("deposit_percent")
    def _check_deposit_percent(self):
        for rec in self:
            if rec.deposit_percent and (rec.deposit_percent < 0.0 or rec.deposit_percent > 100.0):
                raise ValidationError(_("Deposit Percentage must be between 0 and 100."))

    @api.constrains("allow_prepaid_deposit", "deposit_is_required", "deposit_fixed_amount", "deposit_percent")
    def _check_deposit_config(self):
        for rec in self:
            if not rec.allow_prepaid_deposit:
                # Reset enforced values (not strictly necessary but avoids confusion)
                if rec.deposit_is_required or rec.deposit_fixed_amount or rec.deposit_percent:
                    # No hard error; allow values to remain for quick toggling.
                    continue
            else:
                # At least one of fixed or percent should be non-zero when required
                if rec.deposit_is_required and not (rec.deposit_fixed_amount or rec.deposit_percent):
                    raise ValidationError(
                        _("When 'Deposit Required' is enabled, either a Fixed Amount or a Percentage must be set.")
                    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("channel_type")
    def _compute_is_online(self):
        online_types = {"website", "portal", "mobile_app", "marketplace"}
        for rec in self:
            rec.is_online = rec.channel_type in online_types

    def _domain_bookings(self):
        """Common domain for counting bookings of this channel."""
        return [("channel_id", "=", self.id), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search(rec._domain_bookings(), order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'channel_type', 'company_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        type_map = dict(self._fields["channel_type"].selection)
        for rec in self:
            tlabel = type_map.get(rec.channel_type, rec.channel_type)
            label = f"{rec.name} [{tlabel}]"
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # ACTIONS / HOOKS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """Open bookings filtered by this channel."""
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,pivot,graph,activity",
            "domain": [("channel_id", "=", self.id)],
            "context": {"default_channel_id": self.id},
        }
        # Try to use a predefined action (if present) for consistent view layouts
        try:
            action_def = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
            if action_def:
                action = action_def.read()[0]
                # Override domain/context to focus on this channel
                action.update({"domain": [("channel_id", "=", self.id)]})
                ctx = action.get("context", {}) or {}
                ctx.update({"default_channel_id": self.id})
                action["context"] = ctx
        except Exception:
            # Fall back to generic action dict above
            pass
        return action

    def apply_defaults_to_booking(self, booking):
        """Apply channel defaults into a booking record (not saved).
        This is a safe hook that can be called from booking.onchange/channel onchange.
        Only set fields when not already specified by the user or upstream logic."""
        self.ensure_one()
        if not booking:
            return

        # Policy
        if self.policy_id and not booking.policy_id:
            booking.policy_id = self.policy_id

        # Templates (store on booking if fields exist; otherwise, they will be picked by mail rules)
        if hasattr(booking, "reminder_template_id") and not booking.reminder_template_id and self.reminder_template_id:
            booking.reminder_template_id = self.reminder_template_id
        if hasattr(booking, "feedback_template_id") and not booking.feedback_template_id and self.feedback_template_id:
            booking.feedback_template_id = self.feedback_template_id

        # Optional flags (store if booking has these fields)
        if hasattr(booking, "lock_slot_on_confirm") and booking.lock_slot_on_confirm is None:
            booking.lock_slot_on_confirm = self.lock_slot_on_confirm
        if hasattr(booking, "auto_create_appointment") and booking.auto_create_appointment is None:
            booking.auto_create_appointment = self.auto_create_appointment

        # Deposit hints: only if booking has such fields (we keep this generic to avoid tight coupling)
        for fname, value in [
            ("allow_prepaid_deposit", self.allow_prepaid_deposit),
            ("deposit_is_required", self.deposit_is_required),
            ("deposit_fixed_amount", self.deposit_fixed_amount),
            ("deposit_percent", self.deposit_percent),
        ]:
            if hasattr(booking, fname):
                current = getattr(booking, fname)
                # Populate only if not explicitly set
                if current in (False, 0.0, None):
                    setattr(booking, fname, value)

    # -------------------------------------------------------------------------
    # DEFAULTS (HELPERS)
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals):
        # If no policy is provided, try to pick a sensible default by channel type
        if not vals.get("policy_id"):
            default_policy = self._find_default_policy_for_channel(vals.get("channel_type"))
            if default_policy:
                vals["policy_id"] = default_policy.id
        rec = super().create(vals)
        return rec

    def write(self, vals):
        # Small guard rails: normalize code
        if "code" in vals and vals["code"]:
            vals["code"] = vals["code"].strip()
        return super().write(vals)

    def _find_default_policy_for_channel(self, channel_type):
        """Find a default policy record suitable for a given channel type.
        We keep it resilient by trying known XML IDs then falling back to any active policy."""
        Policy = self.env["booking.policy"].sudo()
        # Try by XML-ID convention (if the data file defines them)
        xml_candidates_by_type = {
            "website": "clinic_booking.policy_online_default",
            "portal": "clinic_booking.policy_online_default",
            "mobile_app": "clinic_booking.policy_online_default",
            "marketplace": "clinic_booking.policy_online_default",
            "walkin": "clinic_booking.policy_walkin_default",
            "phone": "clinic_booking.policy_phone_default",
            "kiosk": "clinic_booking.policy_walkin_default",
        }
        xml_id = xml_candidates_by_type.get(channel_type or "", "clinic_booking.policy_default")
        rec = self.env.ref(xml_id, raise_if_not_found=False)
        if rec:
            return rec

        # Fallback: any active policy for the company
        company = self.env.company
        fallback = Policy.search([("company_id", "=", company.id), ("active", "=", True)], limit=1)
        return fallback

    # -------------------------------------------------------------------------
    # ONCHANGE & UX HELPERS
    # -------------------------------------------------------------------------
    @api.onchange("channel_type")
    def _onchange_channel_type(self):
        # Auto-toggle online flag and website exposure hint
        if self.channel_type in {"website", "portal", "mobile_app", "marketplace"}:
            self.website_published = True
        else:
            # Do not force-disable; user may choose to publish routing pages
            self.website_published = self.website_published

        # Suggest policy if none
        if not self.policy_id:
            pol = self._find_default_policy_for_channel(self.channel_type)
            if pol:
                self.policy_id = pol

    @api.onchange("allow_prepaid_deposit")
    def _onchange_allow_prepaid_deposit(self):
        if not self.allow_prepaid_deposit:
            # Keep values as-is; do not erase to avoid losing config upon toggling.
            pass

    @api.onchange("deposit_fixed_amount", "deposit_percent", "deposit_is_required")
    def _onchange_deposit_values(self):
        # Gentle user guidance; hard validation is in constrains
        if self.deposit_is_required and not (self.deposit_fixed_amount or self.deposit_percent):
            return {
                "warning": {
                    "title": _("Deposit Configuration"),
                    "message": _(
                        "When a deposit is required, please set either a Fixed Amount or a Percentage."
                    ),
                }
            }
        return {}

    # -------------------------------------------------------------------------
    # MESSAGING SHORTCUTS
    # -------------------------------------------------------------------------
    def message_post_channel_note(self, body):
        """Convenience helper for consistent chatter messages."""
        if not body:
            return False
        for rec in self:
            rec.message_post(body=body)
        return True


class BookingChannelMixin(models.AbstractModel):
    """
    Abstract mixin to provide a reusable channel_id field to other models
    (e.g., booking lines, wizards, or related objects) without redefining it.
    """
    _name = "booking.channel.mixin"
    _description = "Booking Channel Mixin"

    channel_id = fields.Many2one(
        "booking.channel",
        string="Channel",
        index=True,
        help="Booking channel associated with this record.",
    )

    @api.onchange("channel_id")
    def _onchange_channel_id(self):
        """Hook for inheriting models: apply channel defaults if the target model provides
        an 'apply_defaults_from_channel' method, otherwise do nothing."""
        if self.channel_id and hasattr(self, "apply_defaults_from_channel"):
            # implementors can define apply_defaults_from_channel(self, channel)
            try:
                self.apply_defaults_from_channel(self.channel_id)
            except Exception:
                # Silently ignore to keep the mixin generic/safe.
                pass
