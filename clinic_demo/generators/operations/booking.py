




"""MASTER PROMPT 14 — Booking & Front Office Operations."""

from datetime import datetime, time, timedelta

import pytz
from odoo import _, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_CANCEL_THEN_DELETE, RESET_DEACTIVATE, RESET_DELETE_SAFE, RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.historical_service import HistoricalTimelineService

PROFILE_HISTORICAL_BOOKINGS = {"compact": 12, "standard": 18, "full_enterprise": 24}
PROFILE_CURRENT_BOOKINGS = {"compact": 6, "standard": 8, "full_enterprise": 10}
PROFILE_FUTURE_BOOKINGS = {"compact": 6, "standard": 8, "full_enterprise": 12}

PATIENT_KEYS = (
    "DEMO-PAT-RET-001", "DEMO-PAT-FREQ-001", "DEMO-PAT-PKG-001", "DEMO-PAT-IMG-001",
    "DEMO-PAT-EMAR-001", "DEMO-PAT-TELE-001", "DEMO-PAT-MEM-001", "DEMO-PAT-INS-001",
    "DEMO-PAT-INC-001", "DEMO-PAT-NOSHOW-001", "DEMO-PAT-VIP-001", "DEMO-PAT-REF-001",
    "DEMO-PAT-NEW-001", "DEMO-PAT-ELDER-001", "DEMO-PAT-PED-001", "DEMO-PAT-CHRON-001",
)
TREATMENT_KEYS = (
    "DEMO-TREAT-CONSULT-GEN", "DEMO-TREAT-FOLLOW-UP", "DEMO-TREAT-CONSULT-SPEC",
    "DEMO-TREAT-PHYSIO", "DEMO-TREAT-TELE-CONSULT", "DEMO-TREAT-WELLNESS",
)


@GENERATOR_REGISTRY.register
class BookingOperationsGenerator(BaseDemoGenerator):
    key = "operations.booking"
    phase = "14_frontoffice"
    sequence = 610
    depends_on = ("operations.referral",)
    scenario_keys = ("SCN-BOOKING-HIST-01", "SCN-BOOKING-TODAY-01", "SCN-PIPELINE-01", "SCN-REFERRAL-01")
    owned_models = ("booking.channel", "booking.booking")
    required_groups = ("base.group_user",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _ensure(self, ctx, counters, key, model, values, policy, reset_sequence, scenario, update=True):
        Model = ctx.env[model].with_context(tz=ctx.run.timezone or "UTC").with_company(ctx.run.company_id)
        def create():
            return Model.create(dict(values))
        def update_record(record):
            safe = dict(values)
            if model == "booking.booking" and record.state in {"in_progress", "done", "cancelled"}:
                for field_name in ("patient_id", "doctor_id", "room_id", "start_datetime", "end_datetime"):
                    safe.pop(field_name, None)
            if safe:
                record.write(safe)
        record, _ref, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name=model, generator_key=self.key,
            scenario_key=scenario, create_callback=create,
            update_callback=update_record if update else None, reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record.with_context(tz=ctx.run.timezone or "UTC"), status

    def _preflight(self, ctx):
        required = {"patient_id", "doctor_id", "treatment_id", "room_id", "resource_ids", "start_datetime", "end_datetime", "state", "is_no_show", "checkin_time", "checkout_time", "auto_create_appointment", "lock_slot_on_confirm", "referral_id"}
        missing = sorted(required - set(ctx.env["booking.booking"]._fields))
        if missing:
            raise UserError(_("MASTER PROMPT 14 booking preflight missing fields: %s") % ", ".join(missing))
        if not ctx.env["ir.sequence"].search_count([("code", "=", "booking.booking"), ("company_id", "in", [False, ctx.run.company_id.id])]):
            raise UserError(_("MASTER PROMPT 14 booking preflight failed: missing sequence booking.booking"))
        for key, model in (("DEMO-PAT-RET-001", "clinic.patient"), ("DEMO-DOC-001", "clinic.doctor"), ("DEMO-TREAT-CONSULT-GEN", "clinic.treatment"), ("DEMO-BROOM-B001-CONS-01", "booking.room")):
            ctx.reference_service.resolve(ctx.run, key, model)

    def _channel(self, ctx, counters, code, name, channel_type, sequence):
        return self._ensure(ctx, counters, f"DEMO-BOOK-CHANNEL-{code}", "booking.channel", {
            "name": name, "code": f"demo-{code.lower()}", "channel_type": channel_type,
            "active": True, "sequence": sequence, "company_id": ctx.run.company_id.id,
            "website_published": False, "auto_create_appointment": False,
            "lock_slot_on_confirm": False, "allow_prepaid_deposit": False,
            "description": "Synthetic Prompt-14 booking channel; outbound communication/payment is disabled.",
        }, RESET_DEACTIVATE, 690, "SCN-BOOKING-TODAY-01")[0]

    def _doctor_for_patient(self, ctx, patient, index=0):
        count = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        doctors = [ctx.reference_service.resolve(ctx.run, f"DEMO-DOC-{i:03d}", "clinic.doctor") for i in range(1, count + 1)]
        same_branch = [doctor for doctor in doctors if doctor.branch_id == patient.partner_id.branch_id]
        pool = same_branch or doctors
        return pool[index % len(pool)]

    def _doctor_index(self, ctx, doctor):
        count = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        for index in range(1, count + 1):
            if doctor == ctx.reference_service.resolve(ctx.run, f"DEMO-DOC-{index:03d}", "clinic.doctor"):
                return index
        raise UserError(_("Prompt 14 doctor %s is outside the generated provider roster.") % doctor.display_name)

    def _treatment(self, ctx, index):
        keys = [key for key in TREATMENT_KEYS if ctx.reference_service.resolve(ctx.run, key, "clinic.treatment", missing_ok=True)]
        return ctx.reference_service.resolve(ctx.run, keys[index % len(keys)], "clinic.treatment")

    def _resource_bundle(self, doctor, treatment):
        rooms = doctor.booking_default_room_ids
        if treatment.booking_default_room_ids:
            common = rooms & treatment.booking_default_room_ids
            if common:
                rooms = common
        room = rooms[:1]
        resources = doctor.booking_default_resource_ids
        if treatment.booking_default_resource_ids:
            common_res = resources & treatment.booking_default_resource_ids
            if common_res:
                resources = common_res
        if room:
            room_res = resources.filtered(lambda r: not r.room_ids or room in r.room_ids)
            if room_res:
                resources = room_res
        return room, resources[:1]

    def _local_utc(self, ctx, date_value, hour, minute=0):
        tz = pytz.timezone(ctx.run.timezone or "UTC")
        local = tz.localize(datetime.combine(date_value, time(hour=hour, minute=minute)))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    @staticmethod
    def _operating_day(date_value, direction=0):
        candidate = date_value
        if candidate.weekday() == 6:
            candidate += timedelta(days=1 if direction > 0 else -1)
        return candidate

    def _base_values(self, ctx, patient, doctor, treatment, start_dt, end_dt, channel, referral=False):
        room, resources = self._resource_bundle(doctor, treatment)
        return {
            "company_id": ctx.run.company_id.id, "patient_id": patient.partner_id.id,
            "doctor_id": doctor.id, "treatment_id": treatment.id,
            "room_id": room.id if room else False,
            "resource_ids": [(6, 0, resources.ids)], "start_datetime": start_dt,
            "end_datetime": end_dt, "channel_id": channel.id,
            "auto_create_appointment": False, "lock_slot_on_confirm": False,
            "referral_id": referral.id if referral else False,
            "notes": "Synthetic MASTER PROMPT 14 front-office booking; no real patient data or outbound side effect.",
        }

    def _confirm(self, ctx, booking):
        """Confirm through owner workflow after enforcing provider roster availability."""
        booking = booking.with_context(tz=ctx.run.timezone or "UTC")
        if booking.doctor_id and not booking.doctor_id.with_context(
            tz=ctx.run.timezone or "UTC"
        ).is_available(
            booking.start_datetime, booking.end_datetime,
            ignore_booking_id=booking.id, check_appointments=True,
        ):
            raise UserError(_(
                "Prompt 14 provider %s is not available for %s - %s in timezone %s."
            ) % (
                booking.doctor_id.display_name, booking.start_datetime, booking.end_datetime,
                ctx.run.timezone or "UTC",
            ))
        booking.action_confirm()
        return booking

    def _historical(self, ctx, counters, channel):
        timeline = HistoricalTimelineService(ctx.run, ctx.seed_service)
        dates = timeline.historical_dates(ctx.profile)
        count = PROFILE_HISTORICAL_BOOKINGS[ctx.profile]
        for idx, date_value in enumerate(dates[-count:], 1):
            patient = ctx.reference_service.resolve(ctx.run, PATIENT_KEYS[(idx - 1) % len(PATIENT_KEYS)], "clinic.patient")
            doctor = self._doctor_for_patient(ctx, patient, idx)
            treatment = self._treatment(ctx, idx)
            doctor_index = self._doctor_index(ctx, doctor)
            # Respect the Prompt-12 local doctor roster (09/10/11 start) and keep
            # the full buffered window inside Saturday closing when applicable.
            minute_offset = ctx.seed_service.stable_int(f"prompt14.booking.hist.{idx:03d}.minute", 36)
            start = self._local_utc(ctx, date_value, 8 + doctor_index, minute_offset)
            duration = min(45, int(treatment.booking_default_duration_minutes or 30))
            end = start + timedelta(minutes=duration)
            values = self._base_values(ctx, patient, doctor, treatment, start, end, channel)
            state_kind = "done" if idx % 6 not in {0, 5} else ("cancelled" if idx % 6 == 5 else "no_show")
            if state_kind == "done":
                values.update({"checkin_time": start - timedelta(minutes=8), "checkout_time": end + timedelta(minutes=5)})
                policy = RESET_FRESH_DB_ONLY
            elif state_kind == "cancelled":
                policy = RESET_DELETE_SAFE
            else:
                policy = RESET_CANCEL_THEN_DELETE
            booking, status = self._ensure(ctx, counters, f"DEMO-BOOK-HIST-{idx:03d}", "booking.booking", values, policy, 820, "SCN-BOOKING-HIST-01", update=False)
            if status == "created":
                self._confirm(ctx, booking)
                if state_kind == "done":
                    booking.action_done()
                elif state_kind == "cancelled":
                    booking.action_cancel(reason="Synthetic historical cancellation")
                else:
                    booking.action_mark_no_show()

    def _current(self, ctx, counters, channels):
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        operating = self._operating_day(anchor, direction=-1)
        count = PROFILE_CURRENT_BOOKINGS[ctx.profile]
        # Actual per-doctor lane counters avoid overlap even when patient branch
        # routing does not follow a modulo distribution. Durations are capped at
        # 30 minutes so a +15 minute reschedule remains inside the 55-minute lane.
        lane_minutes = {1: 9 * 60, 2: 10 * 60, 3: 11 * 60}
        lane_counts = {}
        for idx in range(1, count + 1):
            patient_key = "DEMO-PAT-REF-001" if idx == 1 else PATIENT_KEYS[(idx + 3) % len(PATIENT_KEYS)]
            patient = ctx.reference_service.resolve(ctx.run, patient_key, "clinic.patient")
            doctor = self._doctor_for_patient(ctx, patient, idx)
            treatment = self._treatment(ctx, idx % 3)  # consultation/follow-up mix for live day
            lane = self._doctor_index(ctx, doctor)
            slot_no = lane_counts.get(lane, 0)
            lane_counts[lane] = slot_no + 1
            minute_of_day = lane_minutes[lane] + slot_no * 55
            start = self._local_utc(ctx, operating, minute_of_day // 60, minute_of_day % 60)
            duration = min(30, int(treatment.booking_default_duration_minutes or 30))
            end = start + timedelta(minutes=duration)
            referral = ctx.reference_service.resolve(ctx.run, "DEMO-REF-001", "clinic.referral") if idx == 1 else False
            values = self._base_values(ctx, patient, doctor, treatment, start, end, channels[idx % len(channels)], referral=referral)
            scenario = "SCN-REFERRAL-01" if idx == 1 else "SCN-BOOKING-TODAY-01"
            booking, status = self._ensure(ctx, counters, "DEMO-BOOK-TODAY-REF-001" if idx == 1 else f"DEMO-BOOK-TODAY-{idx:03d}", "booking.booking", values, RESET_CANCEL_THEN_DELETE, 840, scenario, update=False)
            if status == "created":
                if idx % 5 == 0:
                    self._confirm(ctx, booking); booking.action_cancel(reason="Synthetic current-day cancellation")
                elif idx % 4 == 0:
                    self._confirm(ctx, booking); booking.action_mark_no_show()
                elif idx % 3 == 0:
                    self._confirm(ctx, booking)
                    booking.action_apply_reschedule(start + timedelta(minutes=15), end + timedelta(minutes=15))
                elif idx % 2 == 0 or idx == 1:
                    self._confirm(ctx, booking)
            if idx == 1 and referral.state in {"draft", "confirmed"}:
                if referral.state == "draft":
                    referral.action_confirm(effective_datetime=start - timedelta(hours=1))
                referral.mark_converted(source_record=booking, effective_datetime=start, conversion_value=0.0)

    def _future(self, ctx, counters, channel):
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        count = PROFILE_FUTURE_BOOKINGS[ctx.profile]
        offsets = (1, 3, 7, 10, 14, 21, 30, 45, 60, 75, 82, 90)
        for idx, offset in enumerate(offsets[:count], 1):
            date_value = self._operating_day(anchor + timedelta(days=offset), direction=1)
            patient = ctx.reference_service.resolve(ctx.run, PATIENT_KEYS[(idx + 7) % len(PATIENT_KEYS)], "clinic.patient")
            doctor = self._doctor_for_patient(ctx, patient, idx)
            treatment = self._treatment(ctx, idx)
            doctor_index = self._doctor_index(ctx, doctor)
            start = self._local_utc(ctx, date_value, 8 + doctor_index, 20)
            duration = min(30, int(treatment.booking_default_duration_minutes or 30))
            end = start + timedelta(minutes=duration)
            values = self._base_values(ctx, patient, doctor, treatment, start, end, channel)
            booking, status = self._ensure(ctx, counters, f"DEMO-FUT-BOOK-{idx:03d}", "booking.booking", values, RESET_CANCEL_THEN_DELETE, 830, "SCN-PIPELINE-01", update=False)
            if status == "created" and idx % 3 != 0:
                self._confirm(ctx, booking)

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._preflight(ctx)
        channels = (
            self._channel(ctx, counters, "WALKIN", "Demo Walk-in", "walkin", 10),
            self._channel(ctx, counters, "PHONE", "Demo Phone", "phone", 20),
            self._channel(ctx, counters, "PORTAL", "Demo Portal", "portal", 30),
        )
        self._historical(ctx, counters, channels[0])
        self._current(ctx, counters, channels)
        self._future(ctx, counters, channels[2])
        return counters

    def validate(self, ctx, scenario):
        issues = []
        expected = PROFILE_HISTORICAL_BOOKINGS[ctx.profile] + PROFILE_CURRENT_BOOKINGS[ctx.profile] + PROFILE_FUTURE_BOOKINGS[ctx.profile]
        refs = ctx.env["clinic.demo.reference"].search([("run_id", "=", ctx.run.id), ("generator_key", "=", self.key), ("model_name", "=", "booking.booking"), ("record_status", "=", "bound")])
        if len(refs) != expected:
            issues.append(f"Prompt-14 booking budget expected {expected}, found {len(refs)}.")
        golden = ctx.reference_service.resolve(ctx.run, "DEMO-BOOK-TODAY-REF-001", "booking.booking", missing_ok=True)
        referral = ctx.reference_service.resolve(ctx.run, "DEMO-REF-001", "clinic.referral", missing_ok=True)
        if not golden or not referral or golden.referral_id != referral or referral.state != "converted":
            issues.append("Golden Referral → Booking conversion anchor is incomplete.")
        return issues









