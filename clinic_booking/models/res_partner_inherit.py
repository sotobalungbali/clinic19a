# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/res_partner_inherit.py
#
# Purpose
# -------
# Extend res.partner (Patient/Customer) with booking-centric fields:
# - Preferences (doctor, treatment, channel, policy, reminders)
# - Quick statistics (counts, last/next booking, no-shows, cancellations)
# - Actions to view/create bookings with sensible defaults
# - Feedback summary (average rating from submitted feedback)
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking (patient_id link)
# - booking.room / booking.resource (indirect through bookings)
# - booking.channel / booking.policy (defaults)
# - clinic.doctor / clinic.treatment (preferences & validations)
# - booking.feedback.link (feedback analytics)
#
# Notes
# -----
# - All user-facing strings are in English.
# - The model works even if some sibling modules are not installed; all cross-
#   model access is guarded to avoid hard crashes.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # BOOKING RELATION / QUICK ACCESS
    # -------------------------------------------------------------------------
    booking_ids = fields.One2many(
        "booking.booking",
        "patient_id",
        string="Bookings",
        help="All bookings related to this patient.",
    )
    booking_count = fields.Integer(
        string="Bookings",
        compute="_compute_booking_stats",
        help="Total number of bookings for this patient.",
    )
    booking_confirmed_count = fields.Integer(
        string="Confirmed/In Progress",
        compute="_compute_booking_stats",
        help="Number of active (confirmed or in-progress) bookings.",
    )
    booking_done_count = fields.Integer(
        string="Completed",
        compute="_compute_booking_stats",
        help="Number of completed bookings.",
    )
    booking_cancel_count = fields.Integer(
        string="Cancelled",
        compute="_compute_booking_stats",
        help="Number of cancelled bookings.",
    )
    booking_noshow_count = fields.Integer(
        string="No-shows",
        compute="_compute_booking_stats",
        help="Number of bookings marked as no-show.",
    )

    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_next_booking",
        help="Most recent booking in the past.",
    )
    next_booking_id = fields.Many2one(
        "booking.booking",
        string="Next Booking",
        compute="_compute_last_next_booking",
        help="Nearest upcoming booking.",
    )
    next_booking_start = fields.Datetime(
        string="Next Booking Start",
        compute="_compute_last_next_booking",
        help="Start time of the next booking.",
    )

    # -------------------------------------------------------------------------
    # PREFERENCES / DEFAULTS
    # -------------------------------------------------------------------------
    preferred_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Preferred Doctor",
        help="Doctor preferred by the patient for new bookings.",
        tracking=True,
    )
    preferred_treatment_ids = fields.Many2many(
        "clinic.treatment",
        # "partner_preferred_treatment_rel",
        # "partner_id",
        string="Preferred Treatments",
        help="Treatments commonly requested by the patient.",
        tracking=True,
    )
    preferred_channel_id = fields.Many2one(
        "booking.channel",
        string="Preferred Channel",
        help="Default booking channel used when creating a new booking for this patient.",
        tracking=True,
    )
    preferred_policy_id = fields.Many2one(
        "booking.policy",
        string="Preferred Policy",
        help="Default booking policy applied when creating a new booking for this patient.",
        tracking=True,
    )

    booking_reminder_method = fields.Selection(
        selection=[
            ("none", "None"),
            ("email", "Email"),
            ("sms", "SMS (if available)"),
            ("email_sms", "Email + SMS"),
        ],
        string="Reminder Method",
        default="email",
        help="Preferred reminder method for upcoming bookings. SMS requires an SMS module.",
        tracking=True,
    )
    booking_reminder_hours_before = fields.Float(
        string="Reminder Hours Before",
        default=24.0,
        help="How many hours before the start time a reminder should be sent (informational).",
        tracking=True,
    )
    allow_portal_booking = fields.Boolean(
        string="Allow Portal Booking",
        default=True,
        help="If enabled, the patient can create/manage bookings from the portal (subject to access).",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # FEEDBACK SUMMARY
    # -------------------------------------------------------------------------
    feedback_count = fields.Integer(
        string="Feedback Entries",
        compute="_compute_feedback_stats",
        help="Number of submitted feedback entries from this patient.",
    )
    feedback_avg_rating = fields.Float(
        string="Average Rating",
        compute="_compute_feedback_stats",
        help="Average 1..5 rating from submitted feedback links.",
        digits=(16, 2),
    )

    # -------------------------------------------------------------------------
    # COMPUTES — BOOKING STATS
    # -------------------------------------------------------------------------
    def _booking_domain_base(self):
        self.ensure_one()
        return [("patient_id", "=", self.id), ("active", "=", True)]

    def _compute_booking_stats(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            base = rec._booking_domain_base()
            rec.booking_count = Booking.search_count(base)
            rec.booking_confirmed_count = Booking.search_count(base + [("state", "in", ["confirmed", "in_progress"])])
            rec.booking_done_count = Booking.search_count(base + [("state", "=", "done")])
            rec.booking_cancel_count = Booking.search_count(base + [("state", "=", "cancelled")])
            rec.booking_noshow_count = Booking.search_count(base + [("is_no_show", "=", True)])

    def _compute_last_next_booking(self):
        Booking = self.env["booking.booking"]
        now = fields.Datetime.now()
        for rec in self:
            base = rec._booking_domain_base()
            # Last booking (past, not cancelled)
            last = Booking.search(
                base + [("start_datetime", "<", now), ("state", "!=", "cancelled")],
                order="start_datetime desc, id desc",
                limit=1,
            )
            # Next booking (future, not cancelled)
            nxt = Booking.search(
                base + [("start_datetime", ">=", now), ("state", "!=", "cancelled")],
                order="start_datetime asc, id asc",
                limit=1,
            )
            rec.last_booking_id = last.id if last else False
            rec.next_booking_id = nxt.id if nxt else False
            rec.next_booking_start = nxt.start_datetime if nxt else False

    # -------------------------------------------------------------------------
    # COMPUTES — FEEDBACK STATS
    # -------------------------------------------------------------------------
    def _compute_feedback_stats(self):
        Feedback = self.env["booking.feedback.link"]
        for rec in self:
            links = Feedback.search([("patient_id", "=", rec.id), ("state", "=", "submitted")])
            rec.feedback_count = len(links)
            if links:
                # rating_value stored as selection of strings '1'..'5'
                ratings = []
                for l in links:
                    try:
                        ratings.append(float(l.rating_value or 0))
                    except Exception:
                        pass
                rec.feedback_avg_rating = (sum(ratings) / len(ratings)) if ratings else 0.0
            else:
                rec.feedback_avg_rating = 0.0

    # -------------------------------------------------------------------------
    # ONCHANGE — CHAINED DEFAULTS
    # -------------------------------------------------------------------------
    @api.onchange("preferred_channel_id")
    def _onchange_preferred_channel_id(self):
        """
        If the selected channel has a default policy/template, use them as hints.
        """
        for rec in self:
            ch = rec.preferred_channel_id
            if not ch:
                continue
            # If channel defines default policy, adopt it (do not overwrite if already set)
            if hasattr(ch, "default_policy_id") and ch.default_policy_id and not rec.preferred_policy_id:
                rec.preferred_policy_id = ch.default_policy_id.id

    @api.onchange("preferred_doctor_id")
    def _onchange_preferred_doctor_id(self):
        """
        Optionally clean preferred treatments to those allowed by the doctor (if configured).
        """
        for rec in self:
            doc = rec.preferred_doctor_id
            if not doc:
                continue
            if hasattr(doc, "allowed_treatment_ids") and doc.allowed_treatment_ids and rec.preferred_treatment_ids:
                rec.preferred_treatment_ids = rec.preferred_treatment_ids.filtered(
                    lambda t: t in doc.allowed_treatment_ids
                )

    # -------------------------------------------------------------------------
    # CONSTRAINTS — PREFERENCES VALIDATION
    # -------------------------------------------------------------------------
    @api.constrains("preferred_doctor_id", "preferred_treatment_ids")
    def _check_preferred_pairs(self):
        """
        If doctor has an 'allowed_treatment_ids' policy, ensure preferred treatments don't violate it.
        """
        for rec in self:
            doc = rec.preferred_doctor_id
            if not doc or not hasattr(doc, "allowed_treatment_ids"):
                continue
            allowed = doc.allowed_treatment_ids
            if allowed and any(t not in allowed for t in rec.preferred_treatment_ids):
                raise ValidationError(_("Some preferred treatments are not allowed for the selected doctor."))

    @api.constrains("booking_reminder_hours_before")
    def _check_reminder_hours(self):
        for rec in self:
            if rec.booking_reminder_hours_before is not None and rec.booking_reminder_hours_before < 0.0:
                raise ValidationError(_("Reminder Hours Before must be 0 or a positive number."))

    # -------------------------------------------------------------------------
    # ACTIONS — NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """
        Open bookings list filtered to this patient.
        """
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_view_next_booking(self):
        """
        Open the next upcoming booking (if any).
        """
        self.ensure_one()
        if not self.next_booking_id:
            raise UserError(_("There is no upcoming booking for this patient."))
        return {
            "name": _("Next Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.next_booking_id.id,
            "target": "current",
        }

    def action_view_last_booking(self):
        """
        Open the latest past booking (if any).
        """
        self.ensure_one()
        if not self.last_booking_id:
            raise UserError(_("There is no past booking for this patient."))
        return {
            "name": _("Last Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.last_booking_id.id,
            "target": "current",
        }

    def action_new_booking(self):
        """
        Start a new booking form with patient & preferences pre-filled.
        """
        self.ensure_one()
        ctx = self._prepare_default_booking_context()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": ctx,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # HELPERS — DEFAULT CONTEXT/VALS FOR NEW BOOKING
    # -------------------------------------------------------------------------
    def _prepare_default_booking_context(self):
        """
        Prepare default context for creating a new booking from this partner.
        """
        self.ensure_one()
        ctx = {
            "default_patient_id": self.id,
            "default_channel_id": self.preferred_channel_id.id if self.preferred_channel_id else False,
            "default_policy_id": self.preferred_policy_id.id if self.preferred_policy_id else False,
            "default_doctor_id": self.preferred_doctor_id.id if self.preferred_doctor_id else False,
        }
        # Default treatment: if only one preferred, prefill
        if len(self.preferred_treatment_ids) == 1:
            ctx["default_treatment_id"] = self.preferred_treatment_ids.id
        # If the channel has 'apply_defaults_to_booking' mixin methods, they'll run on onchange in booking form
        return ctx

    # -------------------------------------------------------------------------
    # UTILITIES — COMMUNICATION
    # -------------------------------------------------------------------------
    def action_send_next_booking_reminder(self):
        """
        Minimal example: post a message to chatter with next booking time.
        Real email/SMS reminders should be implemented in a dedicated scheduler.
        """
        for rec in self:
            if not rec.next_booking_id:
                raise UserError(_("No upcoming booking to remind."))
            nb = rec.next_booking_id
            rec.message_post(
                body=_(
                    "Reminder — Next booking: <b>%s</b> with <b>%s</b> on <b>%s</b>."
                )
                % (
                    nb.name or _("Booking"),
                    (nb.doctor_id and nb.doctor_id.display_name) or _("(no doctor)"),
                    fields.Datetime.to_string(nb.start_datetime),
                )
            )

    # -------------------------------------------------------------------------
    # SMART BUTTON HELPERS (optional in views)
    # -------------------------------------------------------------------------
    def _get_smart_button_label(self):
        """
        Optional helper if you want to compute a smart button label dynamically.
        """
        self.ensure_one()
        if self.next_booking_id:
            return _("Next: %s") % (fields.Datetime.to_string(self.next_booking_id.start_datetime),)
        return _("Bookings")
