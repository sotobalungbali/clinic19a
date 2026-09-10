



"""MASTER PROMPT 15 — Queue, Triage & Arrival Operations.

This generator is deliberately bounded to the front-to-clinical transition.
It consumes Prompt-14 demo bookings, uses owner workflow methods for queue/token/
triage lifecycle transitions, and never writes computed abnormal-vital flags.
"""

from datetime import timedelta

from odoo import _, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import (
    RESET_CANCEL_THEN_DELETE,
    RESET_DEACTIVATE,
    RESET_DELETE_SAFE,
    RESET_FRESH_DB_ONLY,
)
from ...services.generator_registry import GENERATOR_REGISTRY


BOOKING_SPECS = (
    {
        "booking_key": "DEMO-BOOK-TODAY-REF-001",
        "appointment_key": "DEMO-APPT-QUEUE-WAIT-001",
        "token_key": "DEMO-TOKEN-WAIT-001",
        "queue_key": "DEMO-QUEUE-WAIT-001",
        "wait_minutes": 24,
        "call": False,
        "start": False,
        "done": False,
        "serve": False,
        "assign_room": False,
    },
    {
        "booking_key": "DEMO-BOOK-TODAY-002",
        "appointment_key": "DEMO-APPT-QUEUE-SERVICE-001",
        "token_key": "DEMO-TOKEN-CALLED-001",
        "queue_key": "DEMO-QUEUE-SERVICE-001",
        "wait_minutes": 11,
        "call": True,
        "start": True,
        "done": False,
        "serve": False,
        "assign_room": True,
    },
    {
        "booking_key": "DEMO-BOOK-TODAY-003",
        "appointment_key": "DEMO-APPT-QUEUE-DONE-001",
        "token_key": "DEMO-TOKEN-DONE-001",
        "queue_key": "DEMO-QUEUE-DONE-001",
        "wait_minutes": 6,
        "call": True,
        "start": True,
        "done": True,
        "serve": True,
        "assign_room": False,
    },
    {
        "booking_key": "DEMO-BOOK-TODAY-006",
        "appointment_key": "DEMO-APPT-TRIAGE-ABN-001",
        "token_key": "DEMO-TOKEN-ABN-001",
        "queue_key": "DEMO-QUEUE-ABN-001",
        "wait_minutes": 18,
        "call": False,
        "start": False,
        "done": False,
        "serve": False,
        "assign_room": False,
    },
)


@GENERATOR_REGISTRY.register
class QueueTriageArrivalOperationsGenerator(BaseDemoGenerator):
    key = "operations.queue_triage"
    phase = "15_arrival"
    sequence = 620
    depends_on = ("operations.booking",)
    scenario_keys = ("SCN-QUEUE-01", "SCN-TRIAGE-ABN-01")
    owned_models = (
        "clinic.queue.token",
        "clinic.queue",
        "clinic.room.assignment",
        "clinic.triage.level",
        "clinic.triage.session",
        "clinic.vitals.intake",
    )
    required_groups = ("base.group_user",)

    @staticmethod
    def _counters():
        return {
            "created": 0,
            "reused": 0,
            "updated": 0,
            "skipped": 0,
            "warning": 0,
            "error": 0,
        }

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _resolve(self, ctx, key, model, missing_ok=False):
        return ctx.reference_service.resolve(
            ctx.run, key, model, missing_ok=missing_ok
        )

    def _bind_created(
        self,
        ctx,
        counters,
        key,
        record,
        policy,
        reset_sequence,
        scenario_key="SCN-QUEUE-01",
    ):
        ref = ctx.reference_service._reference(ctx.run, key)
        if ref:
            existing = self._resolve(ctx, key, record._name, missing_ok=True)
            if existing:
                counters["reused"] += 1
                return existing

        ctx.reference_service.bind(
            run=ctx.run,
            demo_key=key,
            record=record,
            generator_key=self.key,
            scenario_key=scenario_key,
            ownership_kind="created",
            reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        counters["created"] += 1
        return record

    def _bind_reused(
        self,
        ctx,
        counters,
        key,
        record,
        scenario_key="SCN-QUEUE-01",
    ):
        if not ctx.reference_service._reference(ctx.run, key):
            ctx.reference_service.bind_reused(
                run=ctx.run,
                demo_key=key,
                record=record,
                generator_key=self.key,
                scenario_key=scenario_key,
                reset_policy=RESET_FRESH_DB_ONLY,
                reset_sequence=500,
            )
        counters["reused"] += 1
        return record

    def _ensure_record(
        self,
        ctx,
        counters,
        key,
        model,
        values,
        policy,
        reset_sequence,
        scenario_key,
        update=False,
    ):
        Model = ctx.env[model].with_company(ctx.run.company_id)

        def create():
            return Model.create(dict(values))

        def update_record(record):
            record.write(dict(values))

        record, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=scenario_key,
            create_callback=create,
            update_callback=update_record if update else None,
            reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record, status

    def _preflight(self, ctx):
        requirements = {
            "booking.booking": {
                "patient_id", "doctor_id", "treatment_id", "room_id",
                "appointment_id", "state", "is_no_show",
            },
            "clinic.appointment": {
                "patient_id", "doctor_id", "state",
            },
            "clinic.patient": {
                "partner_id", "company_id",
            },
            "clinic.queue.token": {
                "company_id", "patient_id", "appointment_id", "treatment_id",
                "doctor_id", "room_id", "state", "queue_id", "issued_at",
                "called_at", "served_at", "queue_type", "channel", "priority",
                "notes",
            },
            "clinic.queue": {
                "patient_id", "doctor_id", "treatment_id", "appointment_id",
                "token_id", "room_id", "room_assignment_id", "state",
                "checkin_time", "start_time", "end_time",
            },
            "clinic.triage.level": {
                "name", "code", "company_id", "active", "sequence",
                "sla_minutes", "description", "temp_min_c", "temp_max_c",
                "hr_min_bpm", "hr_max_bpm", "rr_min_bpm", "rr_max_bpm",
                "spo2_min_percent", "sbp_min_mm_hg", "sbp_max_mm_hg",
                "dbp_min_mm_hg", "dbp_max_mm_hg",
            },
            "clinic.triage.session": {
                "company_id", "patient_id", "appointment_id",
                "assigned_nurse_id", "assigned_doctor_id", "arrival_datetime",
                "triage_level_id", "state", "has_abnormal_vitals", "vitals_ids",
                "reason_for_visit", "chief_complaint", "internal_notes",
            },
            "clinic.vitals.intake": {
                "company_id", "triage_session_id", "measure_datetime",
                "measured_by_id", "temperature_c", "heart_rate_bpm",
                "respiratory_rate_bpm", "spo2_percent", "sbp_mm_hg",
                "dbp_mm_hg", "pain_score", "is_abnormal", "notes",
            },
        }
        missing = []
        for model_name, required_fields in requirements.items():
            if model_name not in ctx.env:
                missing.append(f"missing model {model_name}")
                continue
            absent = sorted(required_fields - set(ctx.env[model_name]._fields))
            if absent:
                missing.append(
                    f"{model_name} missing fields {', '.join(absent)}"
                )

        relation_contracts = {
            "booking.booking": {
                "patient_id": "res.partner",
                "doctor_id": "clinic.doctor",
                "appointment_id": "clinic.appointment",
            },
            "clinic.appointment": {
                "patient_id": "clinic.patient",
                "doctor_id": "clinic.doctor",
            },
            "clinic.queue.token": {
                "patient_id": "res.partner",
                "doctor_id": "hr.employee",
                "appointment_id": "clinic.appointment",
            },
            "clinic.queue": {
                "patient_id": "res.partner",
                "doctor_id": "hr.employee",
                "appointment_id": "clinic.appointment",
            },
            "clinic.triage.session": {
                "patient_id": "clinic.patient",
                "appointment_id": "clinic.appointment",
                "assigned_nurse_id": "res.users",
                "assigned_doctor_id": "clinic.doctor",
            },
            "clinic.vitals.intake": {
                "triage_session_id": "clinic.triage.session",
                "measured_by_id": "res.users",
            },
        }
        for model_name, field_contracts in relation_contracts.items():
            Model = ctx.env[model_name]
            for field_name, expected_comodel in field_contracts.items():
                field = Model._fields.get(field_name)
                actual_comodel = getattr(field, "comodel_name", None) if field else None
                if actual_comodel != expected_comodel:
                    missing.append(
                        f"{model_name}.{field_name} comodel is "
                        f"{actual_comodel or 'missing'}, expected {expected_comodel}"
                    )

        booking_model = ctx.env["booking.booking"]
        if not hasattr(booking_model, "_create_or_link_appointment"):
            missing.append(
                "booking.booking missing owner method _create_or_link_appointment"
            )

        for model_name, method_names in {
            "clinic.queue.token": (
                "action_issue", "action_call", "action_create_queue",
                "action_serve",
            ),
            "clinic.queue": (
                "action_start", "action_done", "action_assign_room",
            ),
            "clinic.triage.session": (
                "action_start", "action_complete",
            ),
        }.items():
            Model = ctx.env[model_name]
            for method_name in method_names:
                if not hasattr(Model, method_name):
                    missing.append(f"{model_name} missing owner method {method_name}")

        for spec in BOOKING_SPECS:
            booking = self._resolve(
                ctx, spec["booking_key"], "booking.booking", missing_ok=True
            )
            if not booking:
                missing.append(f"missing Prompt-14 booking {spec['booking_key']}")
            elif booking.state in {"cancelled"} or booking.is_no_show:
                missing.append(
                    f"{spec['booking_key']} is cancelled/no-show and cannot be used "
                    "for Prompt-15 arrival operations"
                )

        self._resolve(ctx, "DEMO-USER-NUR-001", "res.users")
        if missing:
            raise UserError(
                _("MASTER PROMPT 15 preflight failed: %s") % "; ".join(missing)
            )

    @staticmethod
    def _clinic_room_from_booking(booking):
        booking_room = booking.room_id
        if not booking_room:
            return False
        if "clinic_room_id" in booking_room._fields:
            return booking_room.clinic_room_id
        return False

    @staticmethod
    def _queue_employee_from_doctor(doctor):
        if not doctor:
            return False
        if "staff_id" in doctor._fields and doctor.staff_id:
            staff = doctor.staff_id
            if "employee_id" in staff._fields and staff.employee_id:
                return staff.employee_id
        if "employee_id" in doctor._fields and doctor.employee_id:
            return doctor.employee_id
        if "user_id" in doctor._fields and doctor.user_id:
            user = doctor.user_id
            if "employee_id" in user._fields and user.employee_id:
                return user.employee_id
            if "employee_ids" in user._fields and len(user.employee_ids) == 1:
                return user.employee_ids
        return False

    def _clinic_patient_from_partner(self, ctx, partner):
        records = ctx.env["clinic.patient"].with_company(ctx.run.company_id).search([
            ("partner_id", "=", partner.id),
            ("company_id", "=", ctx.run.company_id.id),
        ], limit=2)
        if len(records) != 1:
            raise UserError(_(
                "Prompt 15 requires exactly one clinic.patient for partner %(partner)s; "
                "found %(count)s."
            ) % {"partner": partner.display_name, "count": len(records)})
        return records

    def _ensure_appointment(self, ctx, counters, spec, booking):
        existing_ref = ctx.reference_service._reference(
            ctx.run, spec["appointment_key"]
        )
        if existing_ref:
            return self._resolve(
                ctx, spec["appointment_key"], "clinic.appointment"
            )

        if booking.appointment_id:
            return self._bind_reused(
                ctx, counters, spec["appointment_key"], booking.appointment_id
            )

        booking._create_or_link_appointment()
        booking.invalidate_recordset(["appointment_id"])
        appointment = booking.appointment_id
        if not appointment:
            raise UserError(_(
                "Owner booking workflow did not create/link an Appointment for %s."
            ) % booking.display_name)

        return self._bind_created(
            ctx,
            counters,
            spec["appointment_key"],
            appointment,
            RESET_CANCEL_THEN_DELETE,
            1060,
        )

    def _ensure_token_and_queue(self, ctx, counters, spec):
        booking = self._resolve(ctx, spec["booking_key"], "booking.booking")
        appointment = self._ensure_appointment(ctx, counters, spec, booking)

        patient_partner = booking.patient_id
        queue_employee = self._queue_employee_from_doctor(booking.doctor_id)
        if booking.doctor_id and not queue_employee:
            raise UserError(_(
                "Prompt 15 cannot resolve the exact hr.employee identity for doctor %s."
            ) % booking.doctor_id.display_name)

        token_values = {
            "company_id": ctx.run.company_id.id,
            "patient_id": patient_partner.id,
            "appointment_id": appointment.id,
            "treatment_id": booking.treatment_id.id if booking.treatment_id else False,
            "doctor_id": queue_employee.id if queue_employee else False,
            "queue_type": "general",
            "channel": "walkin",
            "priority": "1",
            "notes": (
                "Synthetic ClinicOne MASTER PROMPT 15 arrival token; "
                "no real patient or outbound side effect."
            ),
        }
        token, _token_status = self._ensure_record(
            ctx,
            counters,
            spec["token_key"],
            "clinic.queue.token",
            {k: v for k, v in token_values.items() if v or k in {
                "company_id", "queue_type", "channel",
            }},
            RESET_CANCEL_THEN_DELETE,
            1090,
            "SCN-QUEUE-01",
            update=False,
        )
        if token.state == "draft":
            token.action_issue()

        queue_ref = ctx.reference_service._reference(ctx.run, spec["queue_key"])
        if queue_ref:
            queue = self._resolve(ctx, spec["queue_key"], "clinic.queue")
        else:
            if not token.queue_id:
                token.action_create_queue()
                token.invalidate_recordset(["queue_id"])
            queue = token.queue_id
            if not queue:
                raise UserError(_(
                    "Queue Token %s did not produce a Queue through action_create_queue()."
                ) % token.display_name)
            self._bind_created(
                ctx,
                counters,
                spec["queue_key"],
                queue,
                RESET_CANCEL_THEN_DELETE,
                1130,
            )

        if not queue.checkin_time:
            queue.write({
                "checkin_time": fields.Datetime.now()
                - timedelta(minutes=int(spec["wait_minutes"]))
            })
            counters["updated"] += 1

        clinic_room = self._clinic_room_from_booking(booking)
        if spec["assign_room"] and clinic_room and not queue.room_assignment_id:
            queue.action_assign_room(clinic_room.id)
            queue.invalidate_recordset(["room_id", "room_assignment_id"])
            if queue.room_assignment_id:
                self._bind_created(
                    ctx,
                    counters,
                    f"{spec['queue_key']}-ROOM-ASSIGNMENT",
                    queue.room_assignment_id,
                    RESET_CANCEL_THEN_DELETE,
                    1120,
                )

        if spec["call"] and token.state == "issued":
            token.action_call()

        if spec["start"] and queue.state not in {"in_progress", "done"}:
            queue.action_start()

        if spec["done"] and queue.state != "done":
            if queue.state != "in_progress":
                queue.action_start()
            queue.action_done()

        if spec["serve"] and token.state != "served":
            if token.state == "issued":
                token.action_call()
            token.action_serve()

        return booking, appointment, token, queue

    def _ensure_triage_level(self, ctx, counters):
        values = {
            "name": "Demo Standard Clinical Attention",
            "code": "DEMO-STD",
            "company_id": ctx.run.company_id.id,
            "active": True,
            "sequence": 30,
            "sla_minutes": 30,
            "temp_min_c": 35.5,
            "temp_max_c": 38.0,
            "hr_min_bpm": 50,
            "hr_max_bpm": 100,
            "rr_min_bpm": 10,
            "rr_max_bpm": 24,
            "spo2_min_percent": 95,
            "sbp_min_mm_hg": 90,
            "sbp_max_mm_hg": 160,
            "dbp_min_mm_hg": 55,
            "dbp_max_mm_hg": 100,
            "description": (
                "Synthetic demo triage threshold profile. It supports presentation "
                "of normal and mild attention-required vital patterns only."
            ),
        }
        level, _status = self._ensure_record(
            ctx,
            counters,
            "DEMO-TRIAGE-LEVEL-STANDARD",
            "clinic.triage.level",
            values,
            RESET_DEACTIVATE,
            700,
            "SCN-QUEUE-01",
            update=True,
        )
        return level

    def _ensure_triage(
        self,
        ctx,
        counters,
        appointment,
        booking,
        queue,
        level,
        triage_key,
        vitals_key,
        abnormal=False,
    ):
        patient = self._clinic_patient_from_partner(ctx, booking.patient_id)
        nurse = self._resolve(ctx, "DEMO-USER-NUR-001", "res.users")
        scenario_key = "SCN-TRIAGE-ABN-01" if abnormal else "SCN-QUEUE-01"

        triage_values = {
            "company_id": ctx.run.company_id.id,
            "patient_id": patient.id,
            "appointment_id": appointment.id,
            "assigned_nurse_id": nurse.id,
            "assigned_doctor_id": booking.doctor_id.id if booking.doctor_id else False,
            "arrival_datetime": queue.checkin_time or fields.Datetime.now(),
            "triage_level_id": level.id,
            "reason_for_visit": (
                "Synthetic demo arrival assessment."
                if not abnormal
                else "Synthetic demo vital review requiring clinical attention."
            ),
            "chief_complaint": (
                "Routine scheduled visit."
                if not abnormal
                else "Mild synthetic oxygen saturation / pulse alert for demonstration."
            ),
            "internal_notes": (
                "Synthetic MASTER PROMPT 15 triage data. "
                "This record is not a diagnosis or clinical advice."
            ),
        }
        triage, _triage_status = self._ensure_record(
            ctx,
            counters,
            triage_key,
            "clinic.triage.session",
            triage_values,
            RESET_CANCEL_THEN_DELETE,
            1100,
            scenario_key,
            update=False,
        )
        if triage.state == "draft":
            triage.action_start()

        if abnormal:
            vital_values = {
                "triage_session_id": triage.id,
                "company_id": ctx.run.company_id.id,
                "measure_datetime": fields.Datetime.now(),
                "measured_by_id": nurse.id,
                "temperature_c": 37.2,
                "heart_rate_bpm": 104,
                "respiratory_rate_bpm": 18,
                "spo2_percent": 93,
                "sbp_mm_hg": 132,
                "dbp_mm_hg": 84,
                "pain_score": 3,
                "notes": (
                    "Synthetic mild attention-required vital pattern for demo. "
                    "No diagnosis is inferred."
                ),
            }
        else:
            vital_values = {
                "triage_session_id": triage.id,
                "company_id": ctx.run.company_id.id,
                "measure_datetime": fields.Datetime.now(),
                "measured_by_id": nurse.id,
                "temperature_c": 36.7,
                "heart_rate_bpm": 78,
                "respiratory_rate_bpm": 16,
                "spo2_percent": 98,
                "sbp_mm_hg": 118,
                "dbp_mm_hg": 76,
                "pain_score": 2,
                "notes": "Synthetic normal vital pattern for ClinicOne demo.",
            }

        vitals, _vital_status = self._ensure_record(
            ctx,
            counters,
            vitals_key,
            "clinic.vitals.intake",
            vital_values,
            RESET_DELETE_SAFE,
            1110,
            scenario_key,
            update=False,
        )

        triage.invalidate_recordset(["has_abnormal_vitals", "vitals_ids"])
        if abnormal:
            if not vitals.is_abnormal or not triage.has_abnormal_vitals:
                raise UserError(_(
                    "Prompt 15 abnormal scenario did not compute abnormality through "
                    "the owner triage/vitals threshold engine."
                ))
            # Deliberately keep the session in progress: attention-required lane.
        else:
            if vitals.is_abnormal or triage.has_abnormal_vitals:
                raise UserError(_(
                    "Prompt 15 normal scenario was unexpectedly flagged abnormal."
                ))
            if triage.state == "in_progress":
                triage.action_complete()

        return triage, vitals

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        counters = self._counters()
        level = self._ensure_triage_level(ctx, counters)

        generated = {}
        for spec in BOOKING_SPECS:
            generated[spec["booking_key"]] = self._ensure_token_and_queue(
                ctx, counters, spec
            )

        normal_booking, normal_appointment, _token, normal_queue = generated[
            "DEMO-BOOK-TODAY-002"
        ]
        self._ensure_triage(
            ctx,
            counters,
            normal_appointment,
            normal_booking,
            normal_queue,
            level,
            "DEMO-TRIAGE-NORMAL-001",
            "DEMO-VITALS-NORMAL-001",
            abnormal=False,
        )

        abnormal_booking, abnormal_appointment, _token, abnormal_queue = generated[
            "DEMO-BOOK-TODAY-006"
        ]
        self._ensure_triage(
            ctx,
            counters,
            abnormal_appointment,
            abnormal_booking,
            abnormal_queue,
            level,
            "DEMO-TRIAGE-ABN-001",
            "DEMO-VITALS-ABN-001",
            abnormal=True,
        )

        return counters

    def validate(self, ctx, scenario):
        issues = []

        waiting = self._resolve(
            ctx, "DEMO-QUEUE-WAIT-001", "clinic.queue", missing_ok=True
        )
        service = self._resolve(
            ctx, "DEMO-QUEUE-SERVICE-001", "clinic.queue", missing_ok=True
        )
        done = self._resolve(
            ctx, "DEMO-QUEUE-DONE-001", "clinic.queue", missing_ok=True
        )
        called_token = self._resolve(
            ctx, "DEMO-TOKEN-CALLED-001", "clinic.queue.token", missing_ok=True
        )
        done_token = self._resolve(
            ctx, "DEMO-TOKEN-DONE-001", "clinic.queue.token", missing_ok=True
        )

        if not waiting or waiting.state != "waiting":
            issues.append("Waiting-patient queue scenario is missing or not waiting.")
        if not service or service.state != "in_progress":
            issues.append("Called/in-service queue scenario is missing or not in progress.")
        if not called_token or called_token.state != "called":
            issues.append("Called token scenario is missing or not called.")
        if not done or done.state != "done":
            issues.append("Completed queue scenario is missing or not done.")
        if not done_token or done_token.state != "served":
            issues.append("Completed queue token is missing or not served.")

        for queue in [record for record in (waiting, service, done) if record]:
            if not queue.token_id:
                issues.append(f"{queue.display_name} is an orphan queue without Token.")
            if not queue.appointment_id:
                issues.append(f"{queue.display_name} is missing its Appointment.")
            if queue.start_time and queue.checkin_time and queue.start_time < queue.checkin_time:
                issues.append(f"{queue.display_name} has start before check-in.")
            if queue.end_time and queue.start_time and queue.end_time < queue.start_time:
                issues.append(f"{queue.display_name} has end before start.")

        normal_triage = self._resolve(
            ctx, "DEMO-TRIAGE-NORMAL-001", "clinic.triage.session",
            missing_ok=True,
        )
        normal_vitals = self._resolve(
            ctx, "DEMO-VITALS-NORMAL-001", "clinic.vitals.intake",
            missing_ok=True,
        )
        abnormal_triage = self._resolve(
            ctx, "DEMO-TRIAGE-ABN-001", "clinic.triage.session",
            missing_ok=True,
        )
        abnormal_vitals = self._resolve(
            ctx, "DEMO-VITALS-ABN-001", "clinic.vitals.intake",
            missing_ok=True,
        )

        if not normal_triage or normal_triage.state != "completed":
            issues.append("Normal triage scenario is missing or not completed.")
        if not normal_vitals or normal_vitals.is_abnormal:
            issues.append("Normal vitals scenario is missing or incorrectly abnormal.")
        if not abnormal_triage or abnormal_triage.state != "in_progress":
            issues.append("Attention-required triage must remain in progress.")
        if not abnormal_vitals or not abnormal_vitals.is_abnormal:
            issues.append("Abnormal vitals scenario is missing or not owner-computed abnormal.")

        for triage, vitals in (
            (normal_triage, normal_vitals),
            (abnormal_triage, abnormal_vitals),
        ):
            if triage and vitals and vitals.triage_session_id != triage:
                issues.append(f"{vitals.display_name} is linked to the wrong Triage Session.")
            if triage and triage.appointment_id:
                if triage.appointment_id.patient_id != triage.patient_id:
                    issues.append(
                        f"{triage.display_name} patient does not match its Appointment."
                    )

        return issues

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return True









