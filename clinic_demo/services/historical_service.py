




"""Deterministic historical-time planning for MASTER PROMPT 13.

This service owns time distribution only. Domain generators in later Master
Prompts remain responsible for creating Booking, Encounter, Billing, Imaging,
eMAR, Incident, and other business transactions through their owner workflows.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pytz

from odoo import fields


@dataclass(frozen=True)
class HistoricalBucket:
    key: str
    label: str
    min_days_ago: int
    max_days_ago: int


HISTORICAL_BUCKETS = (
    HistoricalBucket("baseline", "Baseline History", 181, 365),
    HistoricalBucket("growth", "Growth Period", 91, 180),
    HistoricalBucket("recent_quarter", "Recent Quarter", 31, 90),
    HistoricalBucket("recent_activity", "Recent Activity", 8, 30),
    HistoricalBucket("latest_history", "Latest History", 1, 7),
)

# Nested profile positions inside each rolling 30-day segment. Compact is a
# subset of Standard, and Standard is a subset of Full Enterprise. This keeps
# scenario identities stable when profile budgets expand.
PROFILE_SEGMENT_POSITIONS = {
    "compact": (6, 21),
    "standard": (6, 14, 21, 28),
    "full_enterprise": (4, 6, 11, 14, 21, 28),
}

PROFILE_HISTORY_BUDGETS = {
    "compact": 24,
    "standard": 48,
    "full_enterprise": 72,
}

# Source-owned business date fields. Later domain generators consume this
# contract rather than manipulating create_date/write_date to fake history.
BUSINESS_DATE_FIELDS = {
    "booking.booking": ("start_datetime", "end_datetime", "checkin_time", "checkout_time"),
    "clinic.referral": ("date_referral", "date_received", "date_converted", "date_cancelled"),
    "clinic.encounter": ("date_planned_start", "date_planned_end", "date_start", "date_end"),
    "clinic.treatment.session": (
        "start_datetime", "end_datetime", "actual_start_datetime", "actual_end_datetime"
    ),
    "clinical.imaging.request": ("request_datetime", "desired_datetime", "expiry_date"),
    "clinical.imaging": (
        "request_datetime", "scheduled_datetime", "performed_datetime", "reviewed_datetime"
    ),
    "clinic.emar.order": (
        "date_prescribed", "date_start", "date_end", "date_approved", "date_dispensed", "date_completed"
    ),
    "clinic.care.plan": ("start_date", "end_date"),
    "clinic.postcare.plan": ("start_datetime", "start_date", "expected_end_date"),
    "clinic.billing.invoice": ("invoice_date", "invoice_date_due"),
    "clinic.billing.payment": ("date",),
    "clinic.feedback.request": ("request_date",),
    "clinic.incident": ("occurred_at", "detected_at", "reported_at", "closed_at"),
    "clinic.quality.check": ("planned_date", "started_at"),
    "clinic.patient.vital": ("measured_datetime",),
    "clinic.patient.condition.episode": ("episode_datetime",),
    "clinic.patient.allergy.reaction": ("onset_datetime", "recorded_date"),
}


class HistoricalTimelineService:
    """Build repeatable T-360..T-1 business dates from Demo Anchor Date."""

    def __init__(self, run, seed_service):
        self.run = run
        self.seed_service = seed_service
        self.anchor_date = fields.Date.to_date(run.anchor_date)
        self.timezone = pytz.timezone(run.timezone or "UTC")

    def bucket_for(self, date_value):
        """Return the Prompt-13 bucket for one historical business date."""
        days_ago = (self.anchor_date - fields.Date.to_date(date_value)).days
        for bucket in HISTORICAL_BUCKETS:
            if bucket.min_days_ago <= days_ago <= bucket.max_days_ago:
                return bucket
        return False

    @staticmethod
    def _avoid_sunday(date_value):
        # ClinicOne Prompt-12 operating baseline is Monday-Saturday.
        return date_value - timedelta(days=1) if date_value.weekday() == 6 else date_value

    def historical_dates(self, profile):
        """Return deterministic rolling dates with monthly-like coverage.

        Twelve 30-day segments are used instead of calendar months so the same
        anchor/seed/profile always yields the same history regardless of month
        length. All returned dates are strictly before T0.
        """
        positions = PROFILE_SEGMENT_POSITIONS[profile]
        dates = []
        for segment in range(11, -1, -1):  # oldest -> newest
            for position in positions:
                days_ago = (segment * 30) + position
                date_value = self._avoid_sunday(
                    self.anchor_date - timedelta(days=days_ago)
                )
                if date_value >= self.anchor_date:
                    date_value = self.anchor_date - timedelta(days=1)
                dates.append(date_value)

        # Guard against a Sunday shift ever collapsing two positions.
        deduped = []
        seen = set()
        for index, date_value in enumerate(dates, 1):
            candidate = date_value
            while candidate in seen:
                candidate -= timedelta(days=1)
                candidate = self._avoid_sunday(candidate)
            if candidate >= self.anchor_date:
                candidate = self.anchor_date - timedelta(days=index)
            seen.add(candidate)
            deduped.append(candidate)

        expected = PROFILE_HISTORY_BUDGETS[profile]
        if len(deduped) != expected:
            raise ValueError(
                f"Historical profile {profile} expected {expected} dates, "
                f"generated {len(deduped)}."
            )
        return tuple(deduped)

    def local_to_utc(self, date_value, namespace, hour_from=8, hour_to=15):
        """Return a naive UTC datetime for a deterministic local clinic time."""
        if hour_to <= hour_from:
            raise ValueError("hour_to must be greater than hour_from")
        window_minutes = (hour_to - hour_from) * 60
        minute_offset = self.seed_service.stable_int(namespace, window_minutes)
        local_hour = hour_from + (minute_offset // 60)
        local_minute = minute_offset % 60
        local = self.timezone.localize(
            datetime.combine(fields.Date.to_date(date_value), time(local_hour, local_minute))
        )
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def fixed_historical_datetime(self, days_ago, namespace, hour_from=8, hour_to=15):
        if days_ago <= 0:
            raise ValueError("Historical dates must be at least T-1.")
        date_value = self._avoid_sunday(
            self.anchor_date - timedelta(days=days_ago)
        )
        return self.local_to_utc(
            date_value, namespace, hour_from=hour_from, hour_to=hour_to
        )

    @staticmethod
    def business_date_fields(model_name):
        return BUSINESS_DATE_FIELDS.get(model_name, ())
























