# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_recurring_rule.py
#
# Purpose
# -------
# Provide a reusable, lightweight recurrence engine (RRULE-lite) to define
# repeatable availability windows (dates or datetimes) for Slots, Templates,
# or other booking constructs.
#
# Scope
# -----
# FREQ: Daily / Weekly / Monthly  (+ interval)
# WEEKLY: by weekday(s)
# MONTHLY: by monthday(s) and/or by weekday(s) with setpos (e.g., 1st Monday, last Friday)
# LIMITS: until date and/or count
# EXDATE: explicit exclusion dates
#
# Integration (soft-coupled)
# --------------------------
# - booking.slot.recurring_rule_id (M2O to this rule)
# - Any model can reuse the mixin/iterators to build occurrences
#
# Notes
# -----
# - All user-facing strings are in English.
# - No external libraries; pure Python + Odoo fields/methods.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date as dt_date, datetime, timedelta
import calendar


# -----------------------------------------------------------------------------
# booking.recurring.rule
# -----------------------------------------------------------------------------
class BookingRecurringRule(models.Model):
    _name = "booking.recurring.rule"
    _description = "Booking Recurring Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    # Identity
    name = fields.Char(
        string="Rule Name",
        required=True,
        tracking=True,
        help="Human-friendly name of this recurring rule.",
    )
    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code for this rule.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to stop usage while keeping historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values sort earlier in lists.",
    )

    # Company context
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

    # Frequency & interval
    freq = fields.Selection(
        selection=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        string="Frequency",
        required=True,
        default="weekly",
        help="Overall recurrence frequency.",
    )
    interval = fields.Integer(
        string="Interval",
        default=1,
        help="Repeat every N days/weeks/months depending on the frequency.",
    )

    # Effective date range
    date_start = fields.Date(
        string="Effective From",
        required=True,
        default=lambda self: fields.Date.context_today(self),
        help="The first day this rule can produce occurrences.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional last day this rule can produce occurrences.",
    )

    # Limiters
    count = fields.Integer(
        string="Max Occurrences",
        default=0,
        help="If > 0, stop after producing this many occurrences.",
    )

    # Time window (optional, for models that want start/end datetime directly)
    hour_from = fields.Float(
        string="From (hour)",
        default=9.0,
        help="Optional start time for each occurrence (0.0 - 24.0).",
    )
    hour_to = fields.Float(
        string="To (hour)",
        default=10.0,
        help="Optional end time for each occurrence (0.0 - 24.0). Must be greater than start.",
    )
    duration_minutes = fields.Integer(
        string="Default Duration (min)",
        default=60,
        help="Default duration for a single occurrence. Used when hour_to is not set.",
    )

    # WEEKLY selectors
    weekday_ids = fields.One2many(
        "booking.recurring.weekday",
        "rule_id",
        string="Weekly Weekdays",
        help="For WEEKLY rules: choose one or more weekdays.",
    )

    # MONTHLY selectors
    monthday_ids = fields.One2many(
        "booking.recurring.monthday",
        "rule_id",
        string="Monthly Monthdays",
        help="For MONTHLY rules: one or more month days (1..31).",
    )
    byweekday_ids = fields.One2many(
        "booking.recurring.byweekday",
        "rule_id",
        string="Monthly Weekdays",
        help="For MONTHLY rules: one or more weekdays (e.g., Monday, Friday).",
    )
    bysetpos = fields.Integer(
        string="Set Position (Monthly)",
        default=0,
        help="When using Monthly with weekdays, choose Nth occurrence in the month. "
             "Supported values: -1 (last) or 1..5. 0 means 'all occurrences'.",
    )

    # Exclusions
    exdate_ids = fields.One2many(
        "booking.recurring.exdate",
        "rule_id",
        string="Exception Dates",
        help="Explicit dates to exclude from the recurrence.",
    )

    # Reverse many2one to slots (for convenience navigation)
    slot_ids = fields.One2many(
        "booking.slot",
        "recurring_rule_id",
        string="Linked Slots",
        help="Slots that use this rule for advanced recurrence.",
    )
    slots_count = fields.Integer(
        string="Slots",
        compute="_compute_slots_count",
    )

    # Preview helpers
    next_occurrence_date = fields.Date(
        string="Next Occurrence (Date)",
        compute="_compute_next_occurrence_date",
        help="Next occurrence date on/after today within rule limits.",
    )

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Rule Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Rule Name must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS & COMPUTES
    # -------------------------------------------------------------------------
    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))

    @api.constrains("interval", "duration_minutes", "hour_from", "hour_to", "bysetpos")
    def _check_numeric(self):
        for rec in self:
            if rec.interval < 1:
                raise ValidationError(_("Interval must be at least 1."))
            if rec.duration_minutes is not None and rec.duration_minutes <= 0:
                raise ValidationError(_("Default Duration must be greater than 0 minutes."))
            if rec.hour_from is not None and (rec.hour_from < 0.0 or rec.hour_from > 24.0):
                raise ValidationError(_("Start hour must be within 0.0 and 24.0."))
            if rec.hour_to is not None and (rec.hour_to < 0.0 or rec.hour_to > 24.0):
                raise ValidationError(_("End hour must be within 0.0 and 24.0."))
            if rec.hour_from is not None and rec.hour_to is not None and rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))
            if rec.bysetpos not in (-1, 0, 1, 2, 3, 4, 5):
                raise ValidationError(_("Set Position must be -1 (last) or 0/1/2/3/4/5."))

    @api.constrains("freq", "weekday_ids", "monthday_ids", "byweekday_ids")
    def _check_selector_requirements(self):
        for rec in self:
            if rec.freq == "weekly" and not rec.weekday_ids:
                raise ValidationError(_("Weekly rules require at least one weekday."))
            if rec.freq == "monthly":
                # Need at least one of monthday or weekday
                if not rec.monthday_ids and not rec.byweekday_ids:
                    raise ValidationError(_("Monthly rules require Monthdays and/or Weekdays."))
                # Monthday must be valid 1..31
                for md in rec.monthday_ids:
                    if md.day < 1 or md.day > 31:
                        raise ValidationError(_("Monthday must be between 1 and 31."))

    def _compute_slots_count(self):
        for rec in self:
            rec.slots_count = len(rec.slot_ids)

    def _compute_next_occurrence_date(self):
        today = fields.Date.context_today(self)
        for rec in self:
            nxt = rec._next_date_on_or_after(today)
            rec.next_occurrence_date = nxt

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'company_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # PUBLIC API — DATE GENERATION
    # -------------------------------------------------------------------------
    def iter_dates(self, date_from, date_to=None, max_count=None):
        """
        Yield dt_date occurrences within [date_from, date_to] applying:
        - freq/interval
        - weekly/monthly selectors
        - date_start/date_end
        - exdate
        - count limiter

        If date_to is None, generate until date_end or max_count (whichever comes first).
        """
        self.ensure_one()
        if not date_from:
            return
        start = max(date_from, self.date_start or date_from)

        # Guardrails to avoid runaway loops in misconfiguration
        max_count = int(max_count or 0)
        hard_cap = 2000  # safety
        yielded = 0

        cursor = start
        while True:
            # Stop conditions
            if date_to and cursor > date_to:
                break
            if self.date_end and cursor > self.date_end:
                break
            if max_count and yielded >= max_count:
                break
            if yielded >= hard_cap:
                break

            # Test cursor date for match
            if self._matches(cursor) and not self._is_exdate(cursor):
                yield cursor
                yielded += 1

            # Advance cursor based on frequency
            cursor = self._advance(cursor)

    def iter_windows(self, date_from, date_to=None, max_count=None, hour_from=None, hour_to=None, duration_minutes=None):
        """
        Yield (start_dt, end_dt) windows for each occurrence date,
        using the rule's configured time or provided overrides.
        """
        self.ensure_one()
        hour_from = self._sanitize_hour(hour_from, self.hour_from or 9.0)
        hour_to = self._sanitize_hour(hour_to, self.hour_to or None)
        duration_minutes = duration_minutes if duration_minutes is not None else (self.duration_minutes or 60)

        for occ_date in self.iter_dates(date_from=date_from, date_to=date_to, max_count=max_count):
            start_dt = self._combine_date_hour(occ_date, hour_from)
            if hour_to is not None:
                end_dt = self._combine_date_hour(occ_date, hour_to)
            else:
                end_dt = start_dt + timedelta(minutes=max(1, duration_minutes))
            yield (start_dt, end_dt)

    def next_date(self, after_date=None):
        """
        Return the next occurrence date strictly AFTER 'after_date'.
        If after_date is None, use today-1 to get the first date on/after today.
        """
        self.ensure_one()
        if not after_date:
            after_date = (self.date_start or fields.Date.context_today(self)) - timedelta(days=1)
        probe = after_date + timedelta(days=1)
        nxt = self._next_date_on_or_after(probe)
        return nxt

    # -------------------------------------------------------------------------
    # CORE MATCHING / ADVANCE
    # -------------------------------------------------------------------------
    def _matches(self, d: dt_date) -> bool:
        """Return True if date 'd' matches the rule selectors (freq, weekly, monthly)."""
        if d < (self.date_start or d):
            return False
        if self.date_end and d > self.date_end:
            return False

        if self.freq == "daily":
            # date interval aligned to start
            return self._is_daily_match(d)

        if self.freq == "weekly":
            if not self.weekday_ids:
                return False
            return self._is_weekly_match(d)

        if self.freq == "monthly":
            # By monthday and/or weekdays (+ optional bysetpos)
            return self._is_monthly_match(d)

        return False

    def _is_daily_match(self, d: dt_date) -> bool:
        base = self.date_start or d
        delta_days = (d - base).days
        return (delta_days % max(1, self.interval)) == 0 and delta_days >= 0

    def _is_weekly_match(self, d: dt_date) -> bool:
        # interval measured in weeks from the week of date_start (ISO Monday=0..Sunday=6)
        base = self.date_start or d
        # Monday of base week
        base_monday = base - timedelta(days=base.weekday())
        d_monday = d - timedelta(days=d.weekday())
        weeks = (d_monday - base_monday).days // 7
        if weeks < 0 or (weeks % max(1, self.interval)) != 0:
            return False
        wds = set(self.weekday_ids.mapped("weekday"))
        return str(d.weekday()) in wds

    def _is_monthly_match(self, d: dt_date) -> bool:
        base = self.date_start or d
        # difference in months from base (year*12 + month index)
        months = (d.year - base.year) * 12 + (d.month - base.month)
        if months < 0 or (months % max(1, self.interval)) != 0:
            return False

        # 1) Monthday rule
        md_ok = False
        if self.monthday_ids:
            days = set(mo.day for mo in self.monthday_ids if 1 <= mo.day <= 31)
            last_day = calendar.monthrange(d.year, d.month)[1]
            md_ok = (d.day in days and d.day <= last_day)

        # 2) Weekday rule (optionally with bysetpos)
        wd_ok = False
        if self.byweekday_ids:
            target_wds = set(bw.weekday for bw in self.byweekday_ids)  # '0'..'6'
            if self.bysetpos:
                # Build list of all dates in month matching the weekdays, pick nth or last
                occs = []
                for day in range(1, calendar.monthrange(d.year, d.month)[1] + 1):
                    cand = dt_date(d.year, d.month, day)
                    if str(cand.weekday()) in target_wds:
                        occs.append(cand)
                if occs:
                    if self.bysetpos == -1:
                        wd_ok = (d == occs[-1])
                    else:
                        idx = self.bysetpos - 1
                        wd_ok = (0 <= idx < len(occs) and d == occs[idx])
            else:
                # No setpos: any weekday match in month
                wd_ok = (str(d.weekday()) in target_wds)

        if self.monthday_ids and self.byweekday_ids:
            # If both provided, either condition can validate the date (common expectation)
            return md_ok or wd_ok
        elif self.monthday_ids:
            return md_ok
        elif self.byweekday_ids:
            return wd_ok
        return False

    def _advance(self, d: dt_date) -> dt_date:
        """Advance cursor date by one 'tick' according to frequency, preserving limits."""
        if self.freq == "daily":
            return d + timedelta(days=max(1, self.interval))
        if self.freq == "weekly":
            return d + timedelta(weeks=max(1, self.interval))
        if self.freq == "monthly":
            # Advance month by 'interval'
            months = max(1, self.interval)
            y, m = d.year, d.month
            m += months
            y += (m - 1) // 12
            m = ((m - 1) % 12) + 1
            # Preserve day when possible; clamp to last day of target month
            last = calendar.monthrange(y, m)[1]
            day = min(d.day, last)
            return dt_date(y, m, day)
        # default fallback
        return d + timedelta(days=1)

    def _is_exdate(self, d: dt_date) -> bool:
        return bool(self.exdate_ids.filtered(lambda e: e.date == d and e.active))

    def _next_date_on_or_after(self, start_date: dt_date):
        """Find the next occurrence ON or AFTER 'start_date' (None if none)."""
        # Short-circuit with iter_dates
        it = self.iter_dates(date_from=start_date, date_to=None, max_count=1 if not self.count else self.count)
        for d in it:
            return d
        return None

    # -------------------------------------------------------------------------
    # PUBLIC API — DATETIME HELPERS
    # -------------------------------------------------------------------------
    def _sanitize_hour(self, val, default_val):
        if val is None:
            return default_val
        return max(0.0, min(24.0, float(val)))

    def _combine_date_hour(self, d: dt_date, hour_float: float) -> datetime:
        h = int(hour_float or 0.0)
        m = int(round(((hour_float or 0.0) - h) * 60.0))
        return datetime(d.year, d.month, d.day, h, m, 0)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_slots(self):
        """Open slots linked to this recurring rule."""
        self.ensure_one()
        action = {
            "name": _("Slots"),
            "type": "ir.actions.act_window",
            "res_model": "booking.slot",
            "view_mode": "list,form,calendar,kanban",
            "domain": [("recurring_rule_id", "=", self.id)],
            "context": {"default_recurring_rule_id": self.id},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_slot_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action


# -----------------------------------------------------------------------------
# WEEKLY SELECTOR LINE (weekday)
# -----------------------------------------------------------------------------
class BookingRecurringWeekday(models.Model):
    _name = "booking.recurring.weekday"
    _description = "Recurring Rule Weekday"
    _order = "rule_id, weekday, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    # Monday=0 .. Sunday=6 (string storage to simplify domains)
    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week included in the recurrence.",
    )

    _weekday_unique = models.Constraint(
        'unique(rule_id, weekday)',
        'Weekday already added to this rule.',
    )


# -----------------------------------------------------------------------------
# MONTHLY SELECTOR LINE (monthday 1..31)
# -----------------------------------------------------------------------------
class BookingRecurringMonthday(models.Model):
    _name = "booking.recurring.monthday"
    _description = "Recurring Rule Monthday"
    _order = "rule_id, day, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    day = fields.Integer(
        string="Day of Month",
        required=True,
        help="Day of the month (1..31). Values above the month length will be ignored.",
    )

    @api.constrains("day")
    def _check_day(self):
        for rec in self:
            if rec.day < 1 or rec.day > 31:
                raise ValidationError(_("Day of month must be between 1 and 31."))

    _monthday_unique = models.Constraint(
        'unique(rule_id, day)',
        'This day is already included for the rule.',
    )


# -----------------------------------------------------------------------------
# MONTHLY SELECTOR LINE (weekday)
# -----------------------------------------------------------------------------
class BookingRecurringByWeekday(models.Model):
    _name = "booking.recurring.byweekday"
    _description = "Recurring Rule Monthly Weekday"
    _order = "rule_id, weekday, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Weekday selector to be used for Monthly rules (optionally with Set Position).",
    )

    _byweekday_unique = models.Constraint(
        'unique(rule_id, weekday)',
        'This weekday is already included for the rule.',
    )


# -----------------------------------------------------------------------------
# EXDATE (exclusion date)
# -----------------------------------------------------------------------------
class BookingRecurringExdate(models.Model):
    _name = "booking.recurring.exdate"
    _description = "Recurring Rule Exclusion Date"
    _order = "date, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this exclusion date.",
    )

    date = fields.Date(
        string="Date",
        required=True,
        help="Date to exclude from occurrence generation.",
    )
    reason = fields.Char(
        string="Reason",
        help="Optional reason or note for this exclusion.",
    )

    _exdate_unique = models.Constraint(
        'unique(rule_id, date)',
        'This date is already excluded for the rule.',
    )


# -----------------------------------------------------------------------------
# (Optional) Abstract Mixin to attach recurrence to other models
# -----------------------------------------------------------------------------
class BookingRecurringRuleMixin(models.AbstractModel):
    _name = "booking.recurring.rule.mixin"
    _description = "Recurring Rule Mixin"

    recurring_rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Recurring Rule",
        index=True,
        help="Advanced recurrence rule used to generate occurrences.",
    )

    def generate_occurrence_windows(self, date_from, date_to=None, max_count=None,
                                    hour_from=None, hour_to=None, duration_minutes=None):
        """
        Convenience wrapper to iterate (start_dt, end_dt) from attached rule.
        """
        self.ensure_one()
        rule = self.recurring_rule_id
        if not rule:
            return []
        return list(rule.iter_windows(
            date_from=date_from,
            date_to=date_to,
            max_count=max_count,
            hour_from=hour_from,
            hour_to=hour_to,
            duration_minutes=duration_minutes,
        ))
