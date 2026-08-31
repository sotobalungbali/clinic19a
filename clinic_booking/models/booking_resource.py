
# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_resource.py
#
# Purpose
# -------
# Define clinical resources (devices, tools, consumables) used in bookings:
# - Availability checks with buffers, weekly schedules, and blackouts
# - Concurrency capacity (how many parallel bookings a resource supports)
# - Optional stock/consumable linkage (soft-coupled to stock/account flows)
#
# Models
# ------
# - booking.resource           : main resource entity
# - booking.resource.tag       : taxonomy for filtering/grouping resources
# - booking.resource.schedule  : weekly availability windows
# - booking.resource.blackout  : closures/maintenance windows
# - booking.resource.mixin     : reusable M2M field helper for other models
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking.resource_ids (M2M)
# - booking.room.resource_ids (M2M, shared relation table with booking_room.py)
# - clinic_treatment (allowed_treatment_ids)
# - clinic_doctor (allowed_doctor_ids)
# - stock/product (product_id for consumables/equipment, optional)
#
# Notes
# -----
# - All user-facing strings are in English (per project requirement).
# - No hard-coded dependencies beyond what clinic_booking already declares.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# -----------------------------------------------------------------------------
# booking.resource.tag (simple taxonomy)
# -----------------------------------------------------------------------------
class BookingResourceTag(models.Model):
    _name = "booking.resource.tag"
    _description = "Booking Resource Tag"
    _order = "name"

    name = fields.Char(
        string="Tag Name",
        required=True,
        help="Human-friendly tag name to classify resources (e.g., Laser, RF, Cryo).",
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


# -----------------------------------------------------------------------------
# booking.resource (main entity)
# -----------------------------------------------------------------------------
class BookingResource(models.Model):
    _name = "booking.resource"
    _description = "Booking Resource"
    _order = "sequence, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Identity
    name = fields.Char(
        string="Resource Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the resource (e.g., 'Laser XYZ', 'RF Device #2').",
    )
    code = fields.Char(
        string="Resource Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique technical code for this resource (URL-safe).",
    )
    resource_type = fields.Selection(
        selection=[
            ("device", "Device"),
            ("tool", "Tool"),
            ("consumable", "Consumable"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="device",
        tracking=True,
        help="Classify the resource to enable type-specific behaviors.",
    )
    description = fields.Text(
        string="Description",
        help="Optional internal description of the resource.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to hide this resource while preserving historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values appear earlier in lists and suggestions.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in calendar/kanban indicators.",
    )

    # Company/Currency
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company that owns this resource.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Concurrency & Buffers
    capacity_concurrent = fields.Integer(
        string="Concurrent Capacity",
        default=1,
        help="How many bookings can use this resource simultaneously.",
    )
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Preparation time reserved before the session.",
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Cleaning/reset time reserved after the session.",
    )

    # Compatibility & Relations
    allowed_treatment_ids = fields.Many2many(
        "clinic.treatment",
        # "booking_resource_treatment_rel",
        # "resource_id",
        string="Allowed Treatments",
        help="Restrict which treatments can use this resource. Leave empty for all.",
    )
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "booking_resource_doctor_rel",
        "resource_id",
        "doctor_id",
        string="Allowed Doctors",
        help="Restrict which doctors can use this resource. Leave empty for all.",
    )
    tag_ids = fields.Many2many(
        "booking.resource.tag",
        "booking_resource_tag_rel",
        "resource_id",
        "tag_id",
        string="Tags",
        help="Classify this resource for filtering and reporting.",
    )

    # Cross-link to Rooms (symmetric M2M defined also in booking_room.py)
    room_ids = fields.Many2many(
        "booking.room",
        "booking_room_resource_rel",
        "resource_id",
        "room_id",
        string="Rooms",
        help="Rooms where this resource is typically available.",
    )

    # Scheduling aids
    schedule_ids = fields.One2many(
        "booking.resource.schedule",
        "resource_id",
        string="Weekly Schedules",
        help="Weekly opening hours for this resource. Leave empty to allow all hours.",
    )
    blackout_ids = fields.One2many(
        "booking.resource.blackout",
        "resource_id",
        string="Blackouts",
        help="Ad-hoc closures (maintenance/cleaning) when the resource is not available.",
    )

    # Optional stock/product linkage
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Product representing this device/consumable for inventory/accounting integration.",
    )
    product_tracking = fields.Selection(
        selection=[("none", "No Tracking"), ("lot", "By Lot"), ("serial", "By Unique Serial")],
        string="Product Tracking",
        compute="_compute_product_tracking",
        store=True,
        help="Tracking policy derived from the linked product.",
    )
    track_consumption = fields.Boolean(
        string="Track Consumption",
        help="Enable if the resource is a consumable and needs stock deduction.",
    )
    consumption_qty_per_booking = fields.Float(
        string="Consumption per Booking",
        default=0.0,
        help="Default quantity to consume per booking (for consumables).",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )

    # Stats / Links
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of active bookings using this resource.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking that uses this resource.",
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        help="Approximate next available time based on current bookings and blackouts.",
    )

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Resource Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Resource Name must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("product_id", "product_id.tracking")
    def _compute_product_tracking(self):
        for rec in self:
            tracking = (rec.product_id and rec.product_id.tracking) or "none"
            # product.tracking values in Odoo: 'none', 'lot', 'serial'
            rec.product_tracking = tracking or "none"

    def _domain_bookings(self):
        # Count confirmed/in_progress bookings that include this resource
        return [
            ("resource_ids", "in", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("active", "=", True),
        ]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("resource_ids", "in", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    def _compute_next_available_from(self):
        """Heuristic probing (15-min steps up to 14 hours) to suggest next free time."""
        for rec in self:
            now = fields.Datetime.now()
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
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'code', 'company_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Resource")
            code = rec.code and f"[{rec.code}] " or ""
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{code}{label} - {rec.company_id.name}"
            else:
                label = f"{code}{label}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # AVAILABILITY LOGIC
    # -------------------------------------------------------------------------
    def is_available(self, start_dt, end_dt, ignore_booking_id=None, required_units=1, consider_capacity=True):
        """
        Check if the resource is available between start_dt and end_dt.

        :param start_dt: datetime or string
        :param end_dt: datetime or string
        :param ignore_booking_id: optional booking id to exclude from overlap checks
        :param required_units: how many concurrent units are needed (>=1)
        :param consider_capacity: if False, only returns True when no overlap at all
        :return: bool
        """
        self.ensure_one()
        if not start_dt or not end_dt:
            return False

        start = fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt
        end = fields.Datetime.from_string(end_dt) if isinstance(end_dt, str) else end_dt
        if end <= start:
            return False

        # Apply buffers around requested window
        start_with_buffer = start - timedelta(minutes=self.buffer_before_minutes or 0)
        end_with_buffer = end + timedelta(minutes=self.buffer_after_minutes or 0)

        # Blackouts
        if self._overlaps_blackout(start_with_buffer, end_with_buffer):
            return False

        # Weekly schedules
        if not self._fits_weekly_schedule(start_with_buffer, end_with_buffer):
            return False

        # Overlapping bookings
        if consider_capacity:
            overlaps = self._count_overlapping_bookings(start_with_buffer, end_with_buffer, ignore_booking_id)
            cap = max(1, self.capacity_concurrent or 1)
            need = max(1, required_units or 1)
            # Available if concurrent overlaps + need <= capacity
            return (overlaps + need) <= cap
        else:
            return not self._has_overlapping_booking(start_with_buffer, end_with_buffer, ignore_booking_id)

    def _overlaps_blackout(self, start, end):
        Blackout = self.env["booking.resource.blackout"]
        overlapped = Blackout.search_count([
            ("resource_id", "=", self.id),
            ("active", "=", True),
            ("start_datetime", "<", end),
            ("end_datetime", ">", start),
        ])
        return bool(overlapped)

    def _fits_weekly_schedule(self, start, end):
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
            weekday = cursor.weekday()  # Monday=0..Sunday=6 in local time
            start_hours = cursor.hour + cursor.minute / 60.0
            end_hours = segment_end.hour + segment_end.minute / 60.0

            day_schedules = schedules.filtered(lambda s: s.weekday == str(weekday))
            fits = any((start_hours >= s.hour_from and end_hours <= s.hour_to) for s in day_schedules)
            if not fits:
                return False
            cursor = segment_end + timedelta(seconds=1)
        return True

    def _has_overlapping_booking(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("resource_ids", "in", self.id),
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
            ("resource_ids", "in", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return Booking.search_count(domain)

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
            "domain": [("resource_ids", "in", self.id)],
            "context": {"default_resource_ids": [(6, 0, [self.id])]},
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
            "context": {"default_resource_ids": [(6, 0, [self.id])]},
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("capacity_concurrent")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity_concurrent and rec.capacity_concurrent < 1:
                raise ValidationError(_("Concurrent capacity must be at least 1."))

    @api.constrains("resource_type", "track_consumption", "product_id", "consumption_qty_per_booking")
    def _check_consumption_config(self):
        for rec in self:
            if rec.track_consumption:
                if not rec.product_id:
                    raise ValidationError(_("Tracking consumption requires a linked Product."))
                if rec.consumption_qty_per_booking <= 0.0:
                    raise ValidationError(_("Consumption per Booking must be greater than 0."))
                if rec.resource_type != "consumable":
                    # Not an error, but warn users to align type with behavior
                    pass

    # -------------------------------------------------------------------------
    # STOCK HELPERS (SOFT-COUPLED)
    # -------------------------------------------------------------------------
    def prepare_stock_moves(self, booking, location_id=None, dest_location_id=None, qty=None):
        """
        Prepare stock.move values to consume this resource for a given booking.
        This does not create any records; callers must handle creation/posting.
        Intended for consumables. For devices (non-consumable), use maintenance flows.
        """
        self.ensure_one()
        if not self.track_consumption or not self.product_id:
            return []
        if not booking:
            return []

        # Determine quantity
        quantity = qty if qty is not None else (self.consumption_qty_per_booking or 0.0)
        if quantity <= 0.0:
            return []

        # Guess locations if not provided (very installation-specific; keep safe)
        StockLocation = self.env["stock.location"]
        if not location_id:
            src = StockLocation.search([("usage", "=", "internal"), ("company_id", "=", self.company_id.id)], limit=1)
            location_id = src.id if src else False
        if not dest_location_id:
            # For consumptions, destination could be a 'Customer' or 'Production' or 'Inventory loss' location.
            # Keep None to let caller decide; or pick first 'customer' as soft default.
            dest = StockLocation.search([("usage", "=", "customer")], limit=1)
            dest_location_id = dest.id if dest else False

        move_vals = {
            "name": f"[{self.product_id.display_name}] Booking {booking.name}",
            "product_id": self.product_id.id,
            "product_uom": self.uom_id.id or self.product_id.uom_id.id,
            "product_uom_qty": quantity,
            "location_id": location_id,
            "location_dest_id": dest_location_id,
            "company_id": self.company_id.id,
            "origin": booking.name,
            # link to picking (optional) left to caller
        }
        return [move_vals]


# -----------------------------------------------------------------------------
# booking.resource.schedule (weekly availability windows)
# -----------------------------------------------------------------------------
class BookingResourceSchedule(models.Model):
    _name = "booking.resource.schedule"
    _description = "Booking Resource Weekly Schedule"
    _order = "resource_id, weekday, hour_from"

    resource_id = fields.Many2one(
        "booking.resource",
        string="Resource",
        required=True,
        ondelete="cascade",
        index=True,
        help="Resource to which this schedule applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="resource_id.company_id",
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
        help="Optional note (e.g., 'Nurse required', 'Only after calibration').",
    )

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Schedule hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))


# -----------------------------------------------------------------------------
# booking.resource.blackout (closures / maintenance windows)
# -----------------------------------------------------------------------------
class BookingResourceBlackout(models.Model):
    _name = "booking.resource.blackout"
    _description = "Booking Resource Blackout"
    _order = "start_datetime desc"

    resource_id = fields.Many2one(
        "booking.resource",
        string="Resource",
        required=True,
        ondelete="cascade",
        index=True,
        help="Resource that is not available during this blackout window.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="resource_id.company_id",
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
        help="Short reason for the blackout (e.g., 'Maintenance', 'Calibration').",
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
                ("resource_ids", "in", self.resource_id.id),
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


# -----------------------------------------------------------------------------
# booking.resource.mixin (reusable field for other models)
# -----------------------------------------------------------------------------
class BookingResourceMixin(models.AbstractModel):
    _name = "booking.resource.mixin"
    _description = "Booking Resource Mixin"

    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_resource_rel",
        "booking_id",
        "resource_id",
        string="Resources",
        help="Resources (devices/tools/consumables) associated with this record.",
    )

    @api.onchange("resource_ids")
    def _onchange_resource_ids(self):
        """Hook for inheriting models: validate compatibility or apply defaults."""
        # Example: clear resources not allowed for selected treatment/doctor if those fields exist
        for rec in self:
            if not rec.resource_ids:
                continue

            # If the model has treatment_id/doctor_id, validate compatibility
            treatment = getattr(rec, "treatment_id", False)
            doctor = getattr(rec, "doctor_id", False)
            cleaned = rec.resource_ids
            if treatment:
                cleaned = cleaned.filtered(lambda r: not r.allowed_treatment_ids or treatment in r.allowed_treatment_ids)
            if doctor:
                cleaned = cleaned.filtered(lambda r: not r.allowed_doctor_ids or doctor in r.allowed_doctor_ids)
            if cleaned != rec.resource_ids:
                rec.resource_ids = cleaned
                return {
                    "warning": {
                        "title": _("Resource Compatibility"),
                        "message": _(
                            "Some resources were removed because they are not compatible with the selected "
                            "treatment or doctor."
                        ),
                    }
                }
        return {}


