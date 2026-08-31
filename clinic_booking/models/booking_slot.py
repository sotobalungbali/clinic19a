
# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_slot.py
#
# Purpose
# -------
# Provide bookable time slots that can be attached to a booking or used as
# a template for recurring availability windows (per doctor/room/channel).
#
# Models
# ------
# - booking.slot            : primary slot definition (can be one-off or recurring)
# - booking.slot.exception  : per-date exceptions that disable or modify slots
#
# Key Integrations (soft-coupled, no circular deps)
# -------------------------------------------------
# - booking.booking.slot_id (prefill booking fields from slot)
# - clinic.doctor (doctor availability checks)
# - booking.room / booking.resource (availability checks with buffers/capacity)
# - booking.policy / booking.channel (defaults)
# - Optional: booking.recurring.rule (if present in this module set)
#
# Notes
# -----
# - All user-facing strings are in English (per project requirement).
# - We avoid hard-coded XML-IDs; where needed, guard with raise_if_not_found=False.
# - Recurrence is kept simple here (weekday + time window + date range). A richer
#   RRULE can be provided by 'booking.recurring.rule' (if implemented separately).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# -----------------------------------------------------------------------------
# booking.slot (primary model)
# -----------------------------------------------------------------------------
class BookingSlot(models.Model):
    _name = "booking.slot"
    _description = "Booking Slot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, weekday, hour_from, id"

    # Identity
    name = fields.Char(
        string="Slot Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the slot (e.g., 'Morning Slot (Dr. A) Room 1').",
    )
    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code of this slot.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable the slot while preserving historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values show earlier in lists and suggestions.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in calendar/kanban indicators.",
    )

    # Company / Currency
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Scope / Participants / Defaults
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor primarily associated with this slot (optional).",
    )
    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        index=True,
        help="Room primarily used by this slot (optional).",
    )
    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_slot_resource_rel",
        "slot_id",
        "resource_id",
        string="Resources",
        help="Devices/tools typically needed in this slot (optional).",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Default Treatment",
        help="Optional default treatment when booking is created from this slot.",
    )
    channel_id = fields.Many2one(
        "booking.channel",
        string="Default Channel",
        help="Default booking channel for bookings created from this slot.",
    )
    policy_id = fields.Many2one(
        "booking.policy",
        string="Default Policy",
        help="Default booking policy for bookings created from this slot.",
    )

    # Time window (weekday + hour range) — recurrence-lite
    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week when the slot is normally available.",
    )
    hour_from = fields.Float(
        string="From (hour)",
        required=True,
        default=9.0,
        help="Start time in 24-hour decimal (0.0 - 24.0). Example: 9.0 = 09:00.",
    )
    hour_to = fields.Float(
        string="To (hour)",
        required=True,
        default=12.0,
        help="End time in 24-hour decimal (0.0 - 24.0). Example: 12.0 = 12:00.",
    )
    duration_minutes = fields.Integer(
        string="Default Duration (min)",
        default=60,
        help="Default appointment duration created from this slot.",
    )

    # Effectivity range
    date_start = fields.Date(
        string="Effective From",
        help="Optional start date when this slot becomes effective.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional end date after which this slot no longer applies.",
    )

    # Capacity & Buffers (override defaults of room/resources if needed)
    capacity = fields.Integer(
        string="Capacity",
        default=1,
        help="How many bookings can be created in parallel within this slot.",
    )
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Preparation time before each booking created from this slot.",
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Cleaning/reset time after each booking created from this slot.",
    )

    # Optional richer recurrence (if model exists)
    recurring_rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Recurring Rule",
        help="Optional advanced recurrence rule if available (daily/weekly/custom).",
    )

    # Stats / Links
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of bookings linked to this slot (active ones).",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking made via this slot.",
    )

    # UI / Notes
    description = fields.Text(
        string="Description",
        help="Optional description or internal notes about this slot.",
    )

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Slot Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Slot Name must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Slot hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))

    @api.constrains("capacity", "duration_minutes", "buffer_before_minutes", "buffer_after_minutes")
    def _check_positive_values(self):
        for rec in self:
            if rec.capacity < 1:
                raise ValidationError(_("Capacity must be at least 1."))
            if rec.duration_minutes <= 0:
                raise ValidationError(_("Default Duration must be greater than 0 minutes."))
            if rec.buffer_before_minutes < 0 or rec.buffer_after_minutes < 0:
                raise ValidationError(_("Buffer values must not be negative."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _domain_bookings(self):
        return [("slot_id", "=", self.id), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("slot_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'weekday', 'hour_from', 'hour_to', 'company_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        weekday_map = dict(self._fields["weekday"].selection)
        for rec in self:
            w = weekday_map.get(rec.weekday, rec.weekday)
            hh_from = self._float_hour_to_str(rec.hour_from)
            hh_to = self._float_hour_to_str(rec.hour_to)
            label = f"{rec.name} [{w} {hh_from}-{hh_to}]"
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # HELPERS: Time & Occurrence
    # -------------------------------------------------------------------------
    def _float_hour_to_str(self, value):
        """Convert 13.5 -> '13:30'"""
        hours = int(value or 0.0)
        minutes = int(round(((value or 0.0) - hours) * 60.0))
        return f"{hours:02d}:{minutes:02d}"

    def _make_datetime(self, any_date, hour_float):
        """Combine a date and float hour to a naive datetime (server TZ handling is delegated to Odoo)."""
        h = int(hour_float)
        m = int(round((hour_float - h) * 60.0))
        return datetime.combine(any_date, dt_time(hour=h, minute=m))

    def _is_effective_on(self, date_obj):
        """Return True if the slot is effective on this date according to weekday and date range."""
        if str(date_obj.weekday()) != (self.weekday or "0"):
            return False
        if self.date_start and date_obj < self.date_start:
            return False
        if self.date_end and date_obj > self.date_end:
            return False
        # Exceptions
        if self._is_exception_on(date_obj):
            return False
        return True

    def _is_exception_on(self, date_obj):
        ExceptionModel = self.env["booking.slot.exception"]
        count = ExceptionModel.search_count([
            ("slot_id", "=", self.id),
            ("date", "=", date_obj),
            ("active", "=", True),
        ])
        return bool(count)

    def iter_occurrences(self, date_from, date_to):
        """
        Yield (start_dt, end_dt) naive datetimes for each day within [date_from, date_to]
        where the slot is effective. This is a lightweight generator; heavy RRULE logic
        is intentionally left to 'booking.recurring.rule' if present.
        """
        self.ensure_one()
        if not date_from or not date_to or date_to < date_from:
            return
        cursor = date_from
        while cursor <= date_to:
            if self._is_effective_on(cursor):
                start_dt = self._make_datetime(cursor, self.hour_from)
                end_dt = self._make_datetime(cursor, self.hour_to)
                yield (start_dt, end_dt)
            cursor += timedelta(days=1)

    # -------------------------------------------------------------------------
    # AVAILABILITY: Doctor / Room / Resources / Capacity
    # -------------------------------------------------------------------------
    def is_bookable_window(self, start_dt, end_dt, ignore_booking_id=None):
        """
        Return (bool, reason) if the slot can accept a booking for [start_dt, end_dt].
        This checks:
          - the window falls inside slot's allowed hours on that day
          - slot still effective (date range and exceptions)
          - room availability (if provided)
          - doctor availability (if provided)
          - resources availability (if provided)
          - capacity overlap for existing bookings with this slot
        """
        self.ensure_one()
        if not start_dt or not end_dt or end_dt <= start_dt:
            return (False, _("Invalid start/end time."))

        date_obj = (fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt).date()
        if not self._is_effective_on(date_obj):
            return (False, _("Slot is not effective on this date."))

        # Inside slot hours?
        start_h = (start_dt.hour + start_dt.minute / 60.0) if isinstance(start_dt, datetime) else fields.Datetime.from_string(start_dt).hour
        end_h = (end_dt.hour + end_dt.minute / 60.0) if isinstance(end_dt, datetime) else fields.Datetime.from_string(end_dt).hour
        if not (start_h >= self.hour_from and end_h <= self.hour_to):
            return (False, _("Requested time is outside slot hours."))

        # Room availability
        if self.room_id:
            ok = self.room_id.is_available(
                start_dt, end_dt, ignore_booking_id=ignore_booking_id, consider_capacity=True
            )
            if not ok:
                return (False, _("Room is not available for the requested time."))

        # Doctor availability (search overlaps in booking.booking)
        if self.doctor_id:
            if self._doctor_overlaps(start_dt, end_dt, ignore_booking_id=ignore_booking_id):
                return (False, _("Doctor is not available for the requested time."))

        # Resources availability
        for res in self.resource_ids:
            ok = res.is_available(
                start_dt, end_dt, ignore_booking_id=ignore_booking_id, required_units=1, consider_capacity=True
            )
            if not ok:
                return (False, _("A required resource is not available."))

        # Capacity at slot level (other bookings linked to the same slot)
        overlaps = self._count_overlapping_bookings(start_dt, end_dt, ignore_booking_id=ignore_booking_id)
        if overlaps >= max(1, self.capacity or 1):
            return (False, _("Slot capacity has been reached for the requested time."))

        return (True, _("Available."))

    # Doctor overlap (confirmed/in_progress)
    def _doctor_overlaps(self, start_dt, end_dt, ignore_booking_id=None):
        if not self.doctor_id:
            return False
        Booking = self.env["booking.booking"]
        domain = [
            ("doctor_id", "=", self.doctor_id.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end_dt)),
            ("end_datetime", ">", fields.Datetime.to_string(start_dt)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _count_overlapping_bookings(self, start_dt, end_dt, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("slot_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end_dt)),
            ("end_datetime", ">", fields.Datetime.to_string(start_dt)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return Booking.search_count(domain)

    # -------------------------------------------------------------------------
    # APPLY DEFAULTS TO BOOKING
    # -------------------------------------------------------------------------
    def apply_defaults_to_booking_vals(self, vals=None, start_dt=None, end_dt=None):
        """
        Return a dict of booking values prefilled from this slot.
        Caller can merge with manual input before create().
        """
        self.ensure_one()
        vals = dict(vals or {})
        if "slot_id" not in vals:
            vals["slot_id"] = self.id

        # Parties and context
        if self.doctor_id and not vals.get("doctor_id"):
            vals["doctor_id"] = self.doctor_id.id
        if self.room_id and not vals.get("room_id"):
            vals["room_id"] = self.room_id.id
        if self.treatment_id and not vals.get("treatment_id"):
            vals["treatment_id"] = self.treatment_id.id
        if self.channel_id and not vals.get("channel_id"):
            vals["channel_id"] = self.channel_id.id
        if self.policy_id and not vals.get("policy_id"):
            vals["policy_id"] = self.policy_id.id

        # Resources
        if self.resource_ids and not vals.get("resource_ids"):
            vals["resource_ids"] = [(6, 0, self.resource_ids.ids)]

        # Timing
        if start_dt and not vals.get("start_datetime"):
            vals["start_datetime"] = fields.Datetime.to_string(start_dt)
        if end_dt and not vals.get("end_datetime"):
            vals["end_datetime"] = fields.Datetime.to_string(end_dt)

        # Buffers: copy down only if target model has those fields later; otherwise ignored
        # (we keep them in slot; booking uses room/resource buffers at availability time)

        return vals

    # -------------------------------------------------------------------------
    # ACTIONS (Open related bookings / Create from slot)
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("slot_id", "=", self.id)],
            "context": {"default_slot_id": self.id},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        """Open a new booking form prefilled with slot defaults and next occurrence time if available."""
        self.ensure_one()
        default_start, default_end = self._suggest_next_window()
        ctx = {
            "default_slot_id": self.id,
            "default_doctor_id": self.doctor_id.id if self.doctor_id else False,
            "default_room_id": self.room_id.id if self.room_id else False,
            "default_treatment_id": self.treatment_id.id if self.treatment_id else False,
            "default_channel_id": self.channel_id.id if self.channel_id else False,
            "default_policy_id": self.policy_id.id if self.policy_id else False,
        }
        if default_start and default_end:
            ctx.update({
                "default_start_datetime": fields.Datetime.to_string(default_start),
                "default_end_datetime": fields.Datetime.to_string(default_end),
            })
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": ctx,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # SUGGESTION ENGINE
    # -------------------------------------------------------------------------
    def _suggest_next_window(self):
        """
        Suggest the next available [start, end] for this slot on or after today.
        We check today first; if not effective, we advance to the next matching weekday
        within the date range and test room/doctor/resources/capacity.
        """
        self.ensure_one()
        now = fields.Date.context_today(self)
        search_days = 21  # look ahead up to 3 weeks
        for i in range(search_days):
            day = now + timedelta(days=i)
            if not self._is_effective_on(day):
                continue
            start_dt = self._make_datetime(day, self.hour_from)
            # Use default duration when proposing a single booking window
            duration = timedelta(minutes=max(1, self.duration_minutes or 1))
            end_dt = start_dt + duration
            ok, _reason = self.is_bookable_window(start_dt, end_dt, ignore_booking_id=None)
            if ok:
                return (start_dt, end_dt)
        return (None, None)


# -----------------------------------------------------------------------------
# booking.slot.exception (per-date disable/modify)
# -----------------------------------------------------------------------------
class BookingSlotException(models.Model):
    _name = "booking.slot.exception"
    _description = "Booking Slot Exception"
    _order = "date, id"

    slot_id = fields.Many2one(
        "booking.slot",
        string="Slot",
        required=True,
        index=True,
        ondelete="cascade",
        help="Slot to which this exception applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="slot_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to ignore this exception without deleting.",
    )

    date = fields.Date(
        string="Date",
        required=True,
        help="Date of the exception (slot is disabled or altered on this date).",
    )
    is_disabled = fields.Boolean(
        string="Disable Slot on Date",
        default=True,
        help="If enabled, the slot is disabled for the given date.",
    )
    # Optional hour override (if slot partially available on that date)
    hour_override_from = fields.Float(
        string="From (hour override)",
        help="Optional start time override (0.0 - 24.0) for this date only.",
    )
    hour_override_to = fields.Float(
        string="To (hour override)",
        help="Optional end time override (0.0 - 24.0) for this date only.",
    )
    capacity_override = fields.Integer(
        string="Capacity Override",
        help="Optional capacity override for this date only.",
    )
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'Doctor in training', 'Room maintenance').",
    )

    @api.constrains("hour_override_from", "hour_override_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_override_from is not None:
                if rec.hour_override_from < 0.0 or rec.hour_override_from > 24.0:
                    raise ValidationError(_("Override hours must be between 0.0 and 24.0."))
            if rec.hour_override_to is not None:
                if rec.hour_override_to < 0.0 or rec.hour_override_to > 24.0:
                    raise ValidationError(_("Override hours must be between 0.0 and 24.0."))
            if rec.hour_override_from is not None and rec.hour_override_to is not None:
                if rec.hour_override_to <= rec.hour_override_from:
                    raise ValidationError(_("Override end hour must be greater than start hour."))

    @api.constrains("capacity_override")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity_override is not None and rec.capacity_override < 1:
                raise ValidationError(_("Capacity Override must be at least 1."))

    # Future extension: method to return effective window/capacity for the date,
    # merging slot defaults with overrides. For now, slot uses simple 'disabled' check.


# -----------------------------------------------------------------------------
# OPTIONAL MIXIN (for other records that want to reference a slot)
# -----------------------------------------------------------------------------
class BookingSlotMixin(models.AbstractModel):
    _name = "booking.slot.mixin"
    _description = "Booking Slot Mixin"

    slot_id = fields.Many2one(
        "booking.slot",
        string="Slot",
        index=True,
        help="Slot associated with this record.",
    )

    @api.onchange("slot_id")
    def _onchange_slot_id(self):
        """Inheriting models (e.g., booking) can override or consume slot defaults."""
        # Example: for booking.booking we will fill defaults in form view onchange via RPC.
        return


