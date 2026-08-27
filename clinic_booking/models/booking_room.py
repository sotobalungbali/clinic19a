# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_room.py
#
# Goal
# ----
# Provide a booking-focused wrapper around core clinical rooms by delegating to
# `clinic.room`, adding scheduling/availability rules, buffers, compatibility,
# and convenience actions for the booking workflow.
#
# Key points
# ----------
# - `booking.room` uses `_inherits` to delegate fields to `clinic.room`
#   (via `clinic_room_id`) to avoid data duplication and keep a single source
#   of truth for rooms across the ecosystem (queueing, encounters, etc.).
# - Adds booking-specific settings: buffers, compatibility, capacity overrides,
#   schedules/blackouts, resources, and quick availability checks.
# - Integrates softly with booking, doctor, treatment, inventory, and queueing
#   (without hard circular dependencies).
#
# Models
# ------
# - booking.room               : main booking wrapper for clinic.room
# - booking.room.schedule      : weekly opening hours / availability windows
# - booking.room.blackout      : ad-hoc or ranged closures (maintenance/cleaning)
# - booking.room.tag           : simple tagging for filtering and grouping
#
# Notes
# -----
# - All user-facing strings are in English (as requested).
# - Avoids hard-coded XML IDs except where guarded by raise_if_not_found=False.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# ---------------------------------------------------------------------------
# booking.room.tag (optional helper taxonomy)
# ---------------------------------------------------------------------------
class BookingRoomTag(models.Model):
    _name = "booking.room.tag"
    _description = "Booking Room Tag"
    _order = "name"

    name = fields.Char(
        string="Tag Name",
        required=True,
        help="Human-friendly tag name to classify rooms (e.g., Laser, VIP, Isolation).",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban and list indicators.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        help="Company that owns this tag.",
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Tag Name must be unique per company.',
    )


# ---------------------------------------------------------------------------
# booking.room
# ---------------------------------------------------------------------------
class BookingRoom(models.Model):
    _name = "booking.room"
    _description = "Booking Room"
    _order = "sequence, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    # Delegate to clinic.room (keeps clinic.room as source of truth)
    _inherits = {"clinic.room": "clinic_room_id"}

    # Delegation handle
    clinic_room_id = fields.Many2one(
        "clinic.room",
        string="Clinic Room",
        required=True,
        ondelete="restrict",
        index=True,
        help="Backing clinical room record (delegated).",
    )

    # Basic mirrors / convenience
    name = fields.Char(
        string="Room Name",
        related="clinic_room_id.name",
        store=True,
        readonly=False,
        help="Display name of the room (delegated from Clinic Room).",
    )
    code = fields.Char(
        string="Room Code",
        related="clinic_room_id.code",
        store=True,
        readonly=False,
        help="Unique code of the room (delegated from Clinic Room).",
    )
    active = fields.Boolean(
        string="Active",
        related="clinic_room_id.active",
        store=True,
        readonly=False,
        help="If unchecked, the room is hidden from selection but kept historically.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="clinic_room_id.company_id",
        store=True,
        readonly=False,
    )

    # Booking-specific configuration
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower value → higher priority in suggestions and lists.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used for calendar/kanban indicators.",
    )
    notes = fields.Text(
        string="Notes",
        help="Internal notes relevant for booking or preparation.",
    )

    # Capacity (can be delegated or overridden)
    capacity = fields.Integer(
        string="Capacity",
        default=1,
        help="How many patients can be booked simultaneously in this room.",
    )

    # Buffers (pre/post cleanup, preparation time)
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Minimum minutes reserved before the session for preparation.",
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=10,
        help="Minimum minutes reserved after the session for cleaning/reset.",
    )

    # Compatibility and defaults
    allowed_treatment_ids = fields.Many2many(
        "clinic.treatment",
        # "booking_room_treatment_rel",
        # "room_id",
        string="Allowed Treatments",
        help="Restrict which treatments can be performed in this room. Leave empty for all.",
    )
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "booking_room_doctor_rel",
        "room_id",
        "doctor_id",
        string="Allowed Doctors",
        help="Restrict which doctors can be assigned to this room. Leave empty for all.",
    )
    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_room_resource_rel",
        "room_id",
        "resource_id",
        string="Required Resources",
        help="Devices/machines/tools usually required for this room.",
    )
    tag_ids = fields.Many2many(
        "booking.room.tag",
        "booking_room_tag_rel",
        "room_id",
        "tag_id",
        string="Tags",
        help="Classify this room for filtering and reporting.",
    )

    # Scheduling aids
    schedule_ids = fields.One2many(
        "booking.room.schedule",
        "room_id",
        string="Weekly Schedules",
        help="Weekly opening hours for this room. Leave empty to allow all hours.",
    )
    blackout_ids = fields.One2many(
        "booking.room.blackout",
        "room_id",
        string="Blackouts",
        help="Ad-hoc closures (maintenance/cleaning) when the room is not available.",
    )

    # Stats / Links
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of active bookings assigned to this room.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking for this room.",
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        help="Approximate next available time based on current bookings and blackouts.",
    )

    _clinic_room_company_unique = models.Constraint(
        'unique(clinic_room_id, company_id)',
        'This Clinic Room is already wrapped for the company.',
    )

    # ---------------------------------------------------------------------
    # COMPUTES
    # ---------------------------------------------------------------------
    def _domain_bookings(self):
        return [("room_id", "=", self.id), ("state", "in", ["confirmed", "in_progress"]), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("room_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    def _compute_next_available_from(self):
        """A lightweight heuristic that returns now() if free, or end of the
        latest overlapping booking/blackout + buffer."""
        for rec in self:
            now = fields.Datetime.now()
            # If currently available, return now.
            if rec.is_available(now, now + timedelta(minutes=1)):
                rec.next_available_from = now
                continue

            # Find the smallest future time >= now where availability is true,
            # scanning in small steps (not too heavy).
            # NOTE: For performance in large DBs, a more sophisticated query is recommended.
            step = timedelta(minutes=15)
            probe = now
            # Cap the probing window to avoid long loops (e.g., 14 hours ahead)
            # Adjust as needed in real deployments.
            for _i in range(0, int((14 * 60) / 15)):
                window_end = probe + step
                if rec.is_available(probe, window_end):
                    rec.next_available_from = probe
                    break
                probe = window_end
            else:
                rec.next_available_from = False

    # ---------------------------------------------------------------------
    # NAME / DISPLAY
    # ---------------------------------------------------------------------
    @api.depends('name', 'code', 'company_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Room")
            # Add code and company name for clarity in multi-company contexts
            code = rec.code and f"[{rec.code}] " or ""
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{code}{label} - {rec.company_id.name}"
            else:
                label = f"{code}{label}"
            res.append((rec.id, label))
        return res

    # ---------------------------------------------------------------------
    # CORE LOGIC: Availability checks
    # ---------------------------------------------------------------------
    def is_available(self, start_dt, end_dt, ignore_booking_id=None, consider_capacity=True):
        """
        Check if the room is available between start_dt and end_dt,
        considering buffers, blackouts, weekly schedules, and overlapping bookings.

        :param start_dt: datetime or string (UTC-aware recommended)
        :param end_dt: datetime or string
        :param ignore_booking_id: optional booking id to exclude from overlap checks
        :param consider_capacity: if True, evaluates capacity (>= number of overlaps)
        :return: bool
        """
        self.ensure_one()
        if not start_dt or not end_dt:
            return False

        # Normalize to datetime objects
        start = fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt
        end = fields.Datetime.from_string(end_dt) if isinstance(end_dt, str) else end_dt
        if end <= start:
            return False

        # Apply buffers
        start_with_buffer = start - timedelta(minutes=self.buffer_before_minutes or 0)
        end_with_buffer = end + timedelta(minutes=self.buffer_after_minutes or 0)

        # Check blackouts first
        if self._overlaps_blackout(start_with_buffer, end_with_buffer):
            return False

        # Check weekly schedule windows
        if not self._fits_weekly_schedule(start_with_buffer, end_with_buffer):
            return False

        # Check overlapping bookings
        if consider_capacity:
            overlaps = self._count_overlapping_bookings(start_with_buffer, end_with_buffer, ignore_booking_id=ignore_booking_id)
            return overlaps < max(1, self.capacity or 1)
        else:
            return not self._has_overlapping_booking(start_with_buffer, end_with_buffer, ignore_booking_id=ignore_booking_id)

    def _overlaps_blackout(self, start, end):
        """Return True if any blackout overlaps with [start, end)."""
        Blackout = self.env["booking.room.blackout"]
        overlapped = Blackout.search_count([
            ("room_id", "=", self.id),
            ("active", "=", True),
            ("start_datetime", "<", end),
            ("end_datetime", ">", start),
        ])
        return bool(overlapped)

    def _fits_weekly_schedule(self, start, end):
        """
        If schedules are defined, require that the entire interval falls within at least
        one schedule window per day crossed. If no schedules -> allow all hours.
        """
        schedules = self.schedule_ids.filtered(lambda s: s.active)
        if not schedules:
            return True

        # Iterate day by day; require full fit within some window each day
        cursor = start
        # Use 1-minute step at day boundaries to ensure inclusive logic
        while cursor < end:
            day_end = datetime.combine(cursor.date(), dt_time.max).replace(microsecond=0)
            segment_end = min(end, day_end)
            # Convert to local day-of-week and times in hours
            weekday = cursor.weekday()  # Monday=0 .. Sunday=6
            start_hours = cursor.hour + cursor.minute / 60.0
            end_hours = segment_end.hour + segment_end.minute / 60.0

            day_schedules = schedules.filtered(lambda s: s.weekday == str(weekday))
            # The day's interval must be fully contained in at least one schedule window
            fits = any((start_hours >= s.hour_from and end_hours <= s.hour_to) for s in day_schedules)
            if not fits:
                return False

            cursor = segment_end + timedelta(seconds=1)
        return True

    def _has_overlapping_booking(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("room_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _count_overlapping_bookings(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("room_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return Booking.search_count(domain)

    # ---------------------------------------------------------------------
    # ACTIONS
    # ---------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
        }
        # Try to reuse predefined action if available
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            action = act_ref.read()[0]
            action.update({"domain": [("room_id", "=", self.id)]})
            ctx = action.get("context", {}) or {}
            ctx.update({"default_room_id": self.id})
            action["context"] = ctx
        return action

    def action_new_booking(self):
        """Quick-create action to start a booking with this room prefilled."""
        self.ensure_one()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": {"default_room_id": self.id},
            "target": "current",
        }

    # ---------------------------------------------------------------------
    # VALIDATIONS / CONSTRAINS
    # ---------------------------------------------------------------------
    @api.constrains("capacity")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity and rec.capacity < 1:
                raise ValidationError(_("Room capacity must be at least 1."))


# ---------------------------------------------------------------------------
# booking.room.schedule (weekly availability windows)
# ---------------------------------------------------------------------------
class BookingRoomSchedule(models.Model):
    _name = "booking.room.schedule"
    _description = "Booking Room Weekly Schedule"
    _order = "room_id, weekday, hour_from"

    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        required=True,
        ondelete="cascade",
        index=True,
        help="Room to which this schedule applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="room_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this schedule window.",
    )

    # Monday=0 .. Sunday=6 (string to ease domain filters in XML)
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

    # Optional comments/notes about this window (e.g., lunch breaks, staff rotations)
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'AM shift', 'Senior doctor required', etc.).",
    )

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Schedule hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))


# ---------------------------------------------------------------------------
# booking.room.blackout (closures / maintenance windows)
# ---------------------------------------------------------------------------
class BookingRoomBlackout(models.Model):
    _name = "booking.room.blackout"
    _description = "Booking Room Blackout"
    _order = "start_datetime desc"

    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        required=True,
        ondelete="cascade",
        index=True,
        help="Room that is not available during this blackout window.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="room_id.company_id",
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
        help="Short reason for the blackout (e.g., 'Maintenance', 'Deep cleaning').",
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

    # Convenience action to view bookings colliding with this blackout
    def action_view_conflicting_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Conflicting Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity",
            "domain": [
                ("room_id", "=", self.room_id.id),
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
