
# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/clinic_doctor_inherit.py
#
# Purpose
# -------
# Extend clinic.doctor with booking-oriented capabilities:
# - Doctor-level weekly schedules & blackout windows (optional to use)
# - Availability checks that consider bookings, (optional) appointments, schedules, and blackouts
# - Buffers (handover/cleanup) and convenience defaults (preferred room/resources/channel/policy)
# - Quick stats (counts, last booking, next available, busy now) and actions
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking           (doctor_id overlap checks)
# - clinic.appointment        (optional overlap check if the module provides it)
# - booking.room / resource   (defaults/compatibility)
# - booking.channel / policy  (defaults)
# - booking.slot              (indirect; slot checks doctor availability)
#
# Notes
# -----
# - All user-facing strings are in English.
# - We DO NOT redefine fields that may exist in clinic_doctor (e.g., allowed_treatment_ids).
#   Booking code guards with hasattr(...) as needed.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# =============================================================================
# Inherit clinic.doctor
# =============================================================================
class ClinicDoctor(models.Model):
    _inherit = "clinic.doctor"

    # -------------------------------------------------------------------------
    # Booking defaults & preferences (safe, non-conflicting names)
    # -------------------------------------------------------------------------
    booking_default_channel_id = fields.Many2one(
        "booking.channel",
        string="Default Booking Channel",
        help="Channel suggested when creating a booking for this doctor.",
        tracking=True,
    )
    booking_default_policy_id = fields.Many2one(
        "booking.policy",
        string="Default Booking Policy",
        help="Policy suggested when creating a booking for this doctor.",
        tracking=True,
    )
    booking_default_room_ids = fields.Many2many(
        "booking.room",
        "doctor_booking_room_rel",
        "doctor_id",
        "room_id",
        string="Preferred Rooms",
        help="Rooms commonly used by this doctor (for suggestions and filtering).",
    )
    booking_default_resource_ids = fields.Many2many(
        "booking.resource",
        "doctor_booking_resource_rel",
        "doctor_id",
        "resource_id",
        string="Preferred Resources",
        help="Devices/tools commonly needed by this doctor.",
    )

    # Buffers at the doctor level (handover/prep/cleanup)
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Minimum minutes reserved before the session for preparation.",
        tracking=True,
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Minimum minutes reserved after the session for handover/notes.",
        tracking=True,
    )

    # Scheduling aids (optional)
    schedule_ids = fields.One2many(
        "booking.doctor.schedule",
        "doctor_id",
        string="Weekly Schedules",
        help="Weekly working hours for this doctor (optional). Leave empty to allow all hours.",
    )
    blackout_ids = fields.One2many(
        "booking.doctor.blackout",
        "doctor_id",
        string="Blackouts",
        help="Ad-hoc closures (leave, meeting, training) when the doctor is not available.",
    )

    # Stats
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_booking_stats",
        help="Number of active bookings assigned to this doctor.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_and_busy",
        help="Most recently created booking for this doctor.",
    )
    busy_now = fields.Boolean(
        string="Busy Now",
        compute="_compute_last_and_busy",
        help="True if the doctor is currently in a confirmed/in-progress booking.",
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        help="Approximate next available time based on bookings, schedules, and blackouts.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _domain_bookings(self):
        return [
            ("doctor_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("active", "=", True),
        ]

    def _compute_booking_stats(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_and_busy(self):
        Booking = self.env["booking.booking"]
        now = fields.Datetime.now()
        for rec in self:
            last = Booking.search([("doctor_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False
            busy = Booking.search_count([
                ("doctor_id", "=", rec.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<=", now),
                ("end_datetime", ">", now),
            ])
            rec.busy_now = bool(busy)

    def _compute_next_available_from(self):
        """Heuristic probing: 15-minute steps up to 14 hours ahead."""
        for rec in self:
            now = fields.Datetime.now()
            # If now is already available, return now
            if rec.is_available(now, now + timedelta(minutes=1)):
                rec.next_available_from = now
                continue

            step = timedelta(minutes=15)
            probe = now
            for _i in range(0, int((14 * 60) / 15)):
                window_end = probe + step
                if rec.is_available(probe, window_end):
                    rec.next_available_from = probe
                    break
                probe = window_end
            else:
                rec.next_available_from = False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY (optional enhancement)
    # -------------------------------------------------------------------------
    @api.depends("name", "company_id")
    def _compute_display_name(self):
        """Extend the canonical doctor display name without using removed base name_get()."""
        super()._compute_display_name()
        if len(self.env.companies) > 1:
            for rec in self:
                if rec.company_id:
                    rec.display_name = f"{rec.display_name} - {rec.company_id.name}"

    def name_get(self):
        """Compatibility wrapper for legacy ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]


    # -------------------------------------------------------------------------
    # AVAILABILITY
    # -------------------------------------------------------------------------
    def is_available(self, start_dt, end_dt, ignore_booking_id=None, check_appointments=True):
        """
        Check if the doctor is available between start_dt and end_dt, considering:
        - Doctor buffers (before/after)
        - Doctor blackouts
        - Doctor weekly schedules (if defined)
        - Overlapping bookings (confirmed/in_progress)
        - (Optional) Overlapping clinic.appointment (if model exists)
        """
        self.ensure_one()
        if not start_dt or not end_dt:
            return False

        # Normalize
        start = fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt
        end = fields.Datetime.from_string(end_dt) if isinstance(end_dt, str) else end_dt
        if end <= start:
            return False

        # Apply buffers
        start_with_buffer = start - timedelta(minutes=self.buffer_before_minutes or 0)
        end_with_buffer = end + timedelta(minutes=self.buffer_after_minutes or 0)

        # Blackouts
        if self._overlaps_blackout(start_with_buffer, end_with_buffer):
            return False

        # Weekly schedules
        if not self._fits_weekly_schedule(start_with_buffer, end_with_buffer):
            return False

        # Bookings overlap
        if self._has_overlapping_booking(start_with_buffer, end_with_buffer, ignore_booking_id=ignore_booking_id):
            return False

        # Appointments overlap (soft-coupled; only if model exists and check_appointments=True)
        if check_appointments and "clinic.appointment" in self.env:
            if self._has_overlapping_appointment(start_with_buffer, end_with_buffer):
                return False

        return True

    def _overlaps_blackout(self, start, end):
        Blackout = self.env["booking.doctor.blackout"]
        return bool(Blackout.search_count([
            ("doctor_id", "=", self.id),
            ("active", "=", True),
            ("start_datetime", "<", end),
            ("end_datetime", ">", start),
        ]))

    def _fits_weekly_schedule(self, start, end):
        """
        If schedules are defined, each day segment must be fully inside at least
        one schedule window for that weekday. If no schedules → allow all hours.
        """
        schedules = self.schedule_ids.filtered(lambda s: s.active)
        if not schedules:
            return True

        # Datetime fields are stored as UTC in Odoo, while weekly schedule hours
        # are business-local wall-clock hours. Evaluate the weekly window in the
        # caller/user timezone instead of comparing raw UTC hours to local hours.
        local_start = fields.Datetime.context_timestamp(self, start)
        local_end = fields.Datetime.context_timestamp(self, end)
        cursor = local_start
        while cursor < local_end:
            day_end = cursor.replace(hour=23, minute=59, second=59, microsecond=0)
            segment_end = min(local_end, day_end)

            weekday = str(cursor.weekday())  # '0'..'6' in local time
            start_hours = cursor.hour + cursor.minute / 60.0
            end_hours = segment_end.hour + segment_end.minute / 60.0

            day_schedules = schedules.filtered(lambda s: s.weekday == weekday)
            fits = any((start_hours >= s.hour_from and end_hours <= s.hour_to) for s in day_schedules)
            if not fits:
                return False

            cursor = segment_end + timedelta(seconds=1)
        return True

    def _has_overlapping_booking(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("doctor_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _has_overlapping_appointment(self, start, end):
        """Soft-check clinic.appointment using the fields owned by clinic_doctor.

        ClinicOne's canonical appointment model uses ``start``/``end`` and a
        lifecycle ``state``. Older optional appointment providers may expose
        ``start_datetime``/``end_datetime`` and/or ``active`` instead, so keep
        this bridge field-aware rather than issuing an invalid ORM domain.
        """
        if "clinic.appointment" not in self.env:
            return False

        Appointment = self.env["clinic.appointment"]
        app_fields = Appointment._fields
        if "doctor_id" not in app_fields:
            return False

        start_field = "start" if "start" in app_fields else "start_datetime" if "start_datetime" in app_fields else False
        end_field = "end" if "end" in app_fields else "end_datetime" if "end_datetime" in app_fields else False
        if not start_field or not end_field:
            return False

        domain = [
            ("doctor_id", "=", self.id),
            (start_field, "<", fields.Datetime.to_string(end)),
            (end_field, ">", fields.Datetime.to_string(start)),
        ]
        if "state" in app_fields:
            domain.append(("state", "not in", ["canceled", "no_show"]))
        elif "active" in app_fields:
            domain.append(("active", "=", True))
        return bool(Appointment.search_count(domain))

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("doctor_id", "=", self.id)],
            "context": {
                "default_doctor_id": self.id,
                "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
                "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
                "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
                "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
            },
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        self.ensure_one()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": {
                "default_doctor_id": self.id,
                "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
                "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
                "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
                "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
            },
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("buffer_before_minutes", "buffer_after_minutes")
    def _check_buffers(self):
        for rec in self:
            if rec.buffer_before_minutes is not None and rec.buffer_before_minutes < 0:
                raise ValidationError(_("Buffer Before must be 0 or a positive number."))
            if rec.buffer_after_minutes is not None and rec.buffer_after_minutes < 0:
                raise ValidationError(_("Buffer After must be 0 or a positive number."))


# =============================================================================
# booking.doctor.schedule — Weekly schedules for doctor availability
# =============================================================================
class BookingDoctorSchedule(models.Model):
    _name = "booking.doctor.schedule"
    _description = "Booking Doctor Weekly Schedule"
    _order = "doctor_id, weekday, hour_from"

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        required=True,
        ondelete="cascade",
        index=True,
        help="Doctor to which this schedule applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="doctor_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this schedule window.",
    )

    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week when this schedule applies.",
    )
    hour_from = fields.Float(
        string="From (hour)",
        required=True,
        default=9.0,
        help="Start time (0.0 - 24.0). Example: 9.0 = 09:00.",
    )
    hour_to = fields.Float(
        string="To (hour)",
        required=True,
        default=17.0,
        help="End time (0.0 - 24.0). Example: 17.0 = 17:00.",
    )
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'AM clinic', 'Telemedicine only').",
    )

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Schedule hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))


# =============================================================================
# booking.doctor.blackout — Ad-hoc closures for doctor availability
# =============================================================================
class BookingDoctorBlackout(models.Model):
    _name = "booking.doctor.blackout"
    _description = "Booking Doctor Blackout"
    _order = "start_datetime desc"

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        required=True,
        ondelete="cascade",
        index=True,
        help="Doctor that is not available during this blackout window.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="doctor_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to ignore this blackout without deleting it.",
    )

    start_datetime = fields.Datetime(
        string="Start",
        required=True,
        help="Start datetime of the blackout window.",
    )
    end_datetime = fields.Datetime(
        string="End",
        required=True,
        help="End datetime of the blackout window.",
    )
    reason = fields.Char(
        string="Reason",
        help="Short reason for the blackout (e.g., 'Leave', 'Training', 'Conference').",
    )
    internal_notes = fields.Text(
        string="Internal Notes",
        help="Additional notes for staff about this blackout.",
    )

    @api.constrains("start_datetime", "end_datetime")
    def _check_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End time must be greater than start time."))

    def action_view_conflicting_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Conflicting Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity",
            "domain": [
                ("doctor_id", "=", self.doctor_id.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ],
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action


