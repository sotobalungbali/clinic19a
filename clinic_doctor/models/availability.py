
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/availability.py
# Module: clinic_doctor
#
# ClinicOne — Availability Slot (Odoo 19 CE ready)
#
# Purpose
# -------
# Concrete, bookable time window for a doctor (optionally bound to a room & specialty).
# Supports:
# - Capacity per slot (+ manual reserved seats)
# - State machine (open/reserved/booked/blocked/closed)
# - Optional buffers (before/after) and telemedicine flag
# - Cross-module counters (appointments, queue, devices) via guarded env checks
# - Helper actions (create appointment, block/unblock, reserve/release)
#
# Notes
# -----
# * All labels/help/messages use English.
# * Multi-company aware.
# * Timezone display uses Doctor's user tz (or company tz) for UX fields.
# * Designed to be generated from clinic.schedule.rule, but can be created ad-hoc.

from datetime import timedelta
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


SLOT_STATES = [
    ("open", "Open"),
    ("reserved", "Reserved"),   # partially or fully reserved (manual or via draft appointment)
    ("booked", "Booked"),       # fully booked (capacity reached)
    ("blocked", "Blocked"),     # intentionally blocked (maintenance/cleanup/hold)
    ("closed", "Closed"),       # past/archived or administratively closed
]


class ClinicAvailabilitySlot(models.Model):
    _name = "clinic.availability.slot"
    _description = "Availability Slot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start asc, doctor_id, id"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # CORE LINKS & SCOPE
    # -------------------------------------------------------------------------
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="Doctor available for this time window."
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company to which this slot belongs."
    )

    # Optional context links
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
        help="Room associated with this slot (when onsite)."
    )
    specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        index=True,
        help="Specialty context used for filtering and eligibility checks."
    )

    # Window & properties (UTC storage)
    start = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Slot start time (stored in UTC)."
    )
    end = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Slot end time (stored in UTC)."
    )
    duration_minutes = fields.Integer(
        compute="_compute_duration",
        store=False,
        help="Duration in minutes (computed from start/end)."
    )

    state = fields.Selection(
        SLOT_STATES,
        default="open",
        index=True,
        tracking=True,
        help="Lifecycle state of the slot."
    )
    capacity = fields.Integer(
        default=1,
        tracking=True,
        help="Maximum number of concurrent patients allowed in this slot."
    )
    # manual reservation seats (independent from appointments, used when appointment module is absent)
    manual_reserved = fields.Integer(
        default=0,
        help="Manually reserved seats in this slot (in addition to appointment reservations)."
    )

    # Optional buffers & flags (aligns with schedule_rule and other modules)
    buffer_before_min = fields.Integer(
        default=0,
        help="Preparation buffer (minutes) before the slot."
    )
    buffer_after_min = fields.Integer(
        default=0,
        help="Cleanup buffer (minutes) after the slot."
    )
    telemedicine = fields.Boolean(
        default=False,
        help="If enabled, this slot is dedicated to telemedicine (virtual) sessions."
    )

    # Reason for blocking (when state = blocked)
    block_reason = fields.Char(
        help="Optional reason/explanation when this slot is blocked."
    )

    # -------------------------------------------------------------------------
    # KPIs & COUNTERS (computed via read_group if the related models are installed)
    # -------------------------------------------------------------------------
    appointment_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Total appointments linked to this slot (if the appointment model exposes slot linkage)."
    )
    appointment_open_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Non-terminal appointments linked to this slot."
    )
    queue_token_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Queue tokens linked/overlapping this slot (if queue module is installed)."
    )
    device_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Devices mapped to the room during this window (if device module is installed)."
    )
    reserved_seats = fields.Integer(
        compute="_compute_reserved_seats",
        store=False,
        help="Total reserved seats = manual_reserved + appointment reservations (if available)."
    )
    available_seats = fields.Integer(
        compute="_compute_reserved_seats",
        store=False,
        help="Remaining seats available for booking (not less than zero)."
    )

    # -------------------------------------------------------------------------
    # UX PRESENTATION (localized labels, non-stored)
    # -------------------------------------------------------------------------
    display_name = fields.Char(
        compute="_compute_display_name",
        store=False
    )
    tz_name = fields.Char(
        compute="_compute_tz_name",
        store=False,
        help="Timezone name used for localizing display labels."
    )
    start_local = fields.Char(
        compute="_compute_local_labels",
        store=False,
        help="Start time localized to the user's/doctor's timezone (string)."
    )
    end_local = fields.Char(
        compute="_compute_local_labels",
        store=False,
        help="End time localized to the user's/doctor's timezone (string)."
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _check_start_end = models.Constraint(
        "CHECK (start < end)",
        "End time must be greater than Start time.",
    )
    _uniq_doctor_window_company_room = models.Constraint(
        "UNIQUE (doctor_id, company_id, start, end, room_id)",
        "A duplicate slot exists for the same doctor, room, and time window.",
    )

    # -------------------------------------------------------------------------
    # BASIC CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("capacity", "manual_reserved")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 1:
                raise ValidationError(_("Capacity must be at least 1."))
            if rec.manual_reserved < 0:
                raise ValidationError(_("Manual reserved seats cannot be negative."))
            if rec.manual_reserved > rec.capacity:
                raise ValidationError(_("Manual reserved seats cannot exceed capacity."))

    @api.constrains("doctor_id", "room_id", "specialty_id")
    def _check_room_specialty_policy(self):
        """
        If room enforces allowed_specialty_ids, ensure the specialty is allowed.
        This is a soft rule in many clinics; convert to 'Warning' in views if needed.
        """
        for rec in self:
            room = rec.room_id
            if not room:
                continue
            if "allowed_specialty_ids" in room._fields and room.allowed_specialty_ids:
                if rec.specialty_id and rec.specialty_id.id not in room.allowed_specialty_ids.ids:
                    raise ValidationError(_(
                        "Specialty '%(spec)s' is not allowed in room '%(room)s'.",
                        spec=rec.specialty_id.display_name,
                        room=room.display_name,
                    ))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_duration(self):
        for rec in self:
            if rec.start and rec.end:
                delta = rec.end - rec.start
                rec.duration_minutes = int(delta.total_seconds() // 60)
            else:
                rec.duration_minutes = 0

    def _compute_tz_name(self):
        for rec in self:
            tzname = False
            # 1) Doctor's user tz
            if rec.doctor_id and rec.doctor_id.user_id and rec.doctor_id.user_id.tz:
                tzname = rec.doctor_id.user_id.tz
            # 2) Company tz
            elif rec.company_id and rec.company_id.partner_id and rec.company_id.partner_id.tz:
                tzname = rec.company_id.partner_id.tz
            # 3) Fallback
            rec.tz_name = tzname or "UTC"

    def _localize_dt(self, dt, tzname):
        if not dt:
            return False
        tz = timezone(tzname)
        # as Odoo stores naive UTC, localize assuming UTC then convert
        dt_utc = UTC.localize(dt)
        return dt_utc.astimezone(tz)

    def _compute_local_labels(self):
        for rec in self:
            if not rec.start or not rec.end:
                rec.start_local = ""
                rec.end_local = ""
                continue
            tzname = rec.tz_name or "UTC"
            s_local = rec._localize_dt(rec.start, tzname)
            e_local = rec._localize_dt(rec.end, tzname)
            rec.start_local = s_local.strftime("%Y-%m-%d %H:%M")
            rec.end_local = e_local.strftime("%Y-%m-%d %H:%M")

    def _compute_display_name(self):
        for rec in self:
            doc = rec.doctor_id.display_name if rec.doctor_id else _("Unknown Doctor")
            room = rec.room_id.display_name if rec.room_id else _("No Room")
            mode = _("Telemedicine") if rec.telemedicine else _("Onsite")
            rec.display_name = f"{doc} — {rec.start_local} → {rec.end_local} ({mode}, {room})"

    def _compute_counters(self):
        ids = self.ids or []
        app_map = {sid: 0 for sid in ids}
        app_open_map = {sid: 0 for sid in ids}
        queue_map = {sid: 0 for sid in ids}
        dev_map = {sid: 0 for sid in ids}

        # Appointments (optional): requires clinic.appointment having M2O 'slot_id'
        # if ids and "clinic.appointment" in self.env and "slot_id" in self.env["clinic.appointment"]._fields:
        #     App = self.env["clinic.appointment"]
        #     groups_all = App.read_group(
        #         [("slot_id", "in", ids)],
        #         ["slot_id"],
        #         ["slot_id"],
        #     )
        #     app_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups_all})
        #     groups_open = App.read_group(
        #         [("slot_id", "in", ids), ("state", "not in", ["canceled", "done", "no_show"])],
        #         ["slot_id"],
        #         ["slot_id"],
        #     )
        #     app_open_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups_open})

        # Queue tokens (optional): link by slot_id if provided, else by window overlap
        # if ids and "clinic.queue.token" in self.env:
        #     Token = self.env["clinic.queue.token"]
        #     if "slot_id" in Token._fields:
        #         groups_q = Token.read_group(
        #             [("slot_id", "in", ids)],
        #             ["slot_id"],
        #             ["slot_id"],
        #         )
        #         queue_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups_q})
        #     else:
        #         # Overlap by window if slot linkage not present
        #         for rec in self:
        #             queue_map[rec.id] = Token.search_count([
        #                 ("room_id", "=", rec.room_id.id) if rec.room_id else ("id", "!=", 0),
        #                 ("scheduled_start", "<", rec.end),
        #                 ("scheduled_end", ">", rec.start),
        #             ])

        # Devices (optional): count devices bound to the room (not time-aware)
        if ids and "clinic.device" in self.env and self:
            groups_d = self.env["clinic.device"].read_group(
                [("room_id", "in", self.mapped("room_id").ids)],
                ["room_id"],
                ["room_id"],
            )
            tmp = {g["room_id"][0]: g["room_id_count"] for g in groups_d}
            for rec in self:
                dev_map[rec.id] = tmp.get(rec.room_id.id, 0)

        for rec in self:
            rec.appointment_count = app_map.get(rec.id, 0)
            rec.appointment_open_count = app_open_map.get(rec.id, 0)
            rec.queue_token_count = queue_map.get(rec.id, 0)
            rec.device_count = dev_map.get(rec.id, 0)

    def _compute_reserved_seats(self):
        ids = self.ids or []
        app_res_map = {sid: 0 for sid in ids}
        # if ids and "clinic.appointment" in self.env and "slot_id" in self.env["clinic.appointment"]._fields:
        #     # Count only active bookings
        #     groups = self.env["clinic.appointment"].read_group(
        #         [("slot_id", "in", ids), ("state", "not in", ["canceled", "no_show"])],
        #         ["slot_id"],
        #         ["slot_id"],
        #     )
        #     app_res_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups})

        for rec in self:
            reserved = (rec.manual_reserved or 0) + app_res_map.get(rec.id, 0)
            rec.reserved_seats = reserved
            rem = (rec.capacity or 0) - reserved
            rec.available_seats = max(0, rem)

    # -------------------------------------------------------------------------
    # BUSINESS POLICY CHECKS
    # -------------------------------------------------------------------------
    def _check_doctor_leave_overlap(self):
        """Return a map id->bool whether slot overlaps any doctor leave."""
        res = {sid: False for sid in self.ids}
        if "clinic.doctor.leave" not in self.env:
            return res
        Leave = self.env["clinic.doctor.leave"]
        for rec in self:
            has = Leave.search_count([
                ("doctor_id", "=", rec.doctor_id.id),
                ("date_from", "<", rec.end),
                ("date_to", ">", rec.start),
            ], limit=1)
            res[rec.id] = bool(has)
        return res

    # def _check_appointment_overlap(self):
    #     """Return a map id->bool whether slot overlaps any non-terminal appointment."""
    #     res = {sid: False for sid in self.ids}
    #     if "clinic.appointment" not in self.env:
    #         return res
    #     App = self.env["clinic.appointment"]
    #     for rec in self:
    #         has = App.search_count([
    #             ("doctor_id", "=", rec.doctor_id.id),
    #             ("state", "not in", ["canceled", "done", "no_show"]),
    #             ("start", "<", rec.end),
    #             ("end", ">", rec.start),
    #         ], limit=1)
    #         res[rec.id] = bool(has)
    #     return res

    # -------------------------------------------------------------------------
    # STATE MACHINE / TRANSITIONS
    # -------------------------------------------------------------------------
    def _update_state_from_capacity(self):
        """Auto-advance state based on seats."""
        for rec in self:
            if rec.state in ("blocked", "closed"):
                continue
            if rec.available_seats <= 0:
                rec.state = "booked"
            elif rec.reserved_seats > 0:
                rec.state = "reserved"
            else:
                rec.state = "open"

    def action_block(self):
        """Block the slot (with optional reason in context 'block_reason')."""
        for rec in self:
            if rec.state == "closed":
                raise UserError(_("Closed slots cannot be blocked."))
            rec.state = "blocked"
            reason = (self.env.context or {}).get("block_reason")
            if reason:
                rec.block_reason = reason
        return True

    def action_unblock(self):
        """Reopen a previously blocked slot."""
        for rec in self:
            if rec.state != "blocked":
                continue
            rec.state = "open"
            rec.block_reason = False
            rec._update_state_from_capacity()
        return True

    def action_close(self):
        """Administratively close this slot (e.g., at end of day)."""
        for rec in self:
            rec.state = "closed"
        return True

    def action_reopen(self):
        """Reopen a closed slot if still valid."""
        for rec in self:
            if rec.end and rec.end < fields.Datetime.now():
                raise UserError(_("You cannot reopen a past slot."))
            rec.state = "open"
            rec._update_state_from_capacity()
        return True

    def action_reserve_seats(self, qty=1):
        """Manually reserve seats (when appointment module is not used)."""
        if qty <= 0:
            raise UserError(_("Quantity must be a positive integer."))
        for rec in self:
            if rec.state in ("blocked", "closed"):
                raise UserError(_("Cannot reserve seats on blocked/closed slots."))
            if rec.available_seats < qty:
                raise UserError(_("Not enough available seats to reserve."))
            rec.manual_reserved += qty
            rec._update_state_from_capacity()
        return True

    def action_release_seats(self, qty=1):
        """Release manual reservations."""
        if qty <= 0:
            raise UserError(_("Quantity must be a positive integer."))
        for rec in self:
            if rec.manual_reserved < qty:
                raise UserError(_("Cannot release more seats than reserved."))
            rec.manual_reserved -= qty
            rec._update_state_from_capacity()
        return True

    # -------------------------------------------------------------------------
    # BOOKING HELPERS
    # -------------------------------------------------------------------------
    # def action_create_appointment(self):
    #     """
    #     Open appointment form pre-filled with this slot data.
    #     Requires clinic.appointment; if slot_id is supported, it will be set.
    #     """
    #     self.ensure_one()
    #     model_name = "clinic.appointment"
    #     if model_name not in self.env:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {"title": _("Not Available"),
    #                        "message": _("Appointment module is not installed."),
    #                        "sticky": False},
    #         }
    #     ctx = {
    #         "default_doctor_id": self.doctor_id.id,
    #         "default_start": self.start,
    #         "default_end": self.end,
    #         "default_company_id": self.company_id.id,
    #     }
    #     if self.room_id and "room_id" in self.env[model_name]._fields:
    #         ctx["default_room_id"] = self.room_id.id
    #     if self.specialty_id and "specialty_id" in self.env[model_name]._fields:
    #         ctx["default_specialty_id"] = self.specialty_id.id
    #     if "slot_id" in self.env[model_name]._fields:
    #         ctx["default_slot_id"] = self.id

    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Create Appointment"),
    #         "res_model": model_name,
    #         "view_mode": "form",
    #         "target": "current",
    #         "context": ctx,
    #     }

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Auto-correct states after creation
        records._update_state_from_capacity()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._update_state_from_capacity()
        return res

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.display_name or _("Availability Slot")))
        return res
