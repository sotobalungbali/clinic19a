
"""MASTER PROMPT 16 — first-class Treatment Session service delivery.

Consumes Prompt-14 bookings and Prompt-16 encounters, generates sessions through
the Booking owner bridge, and uses Treatment Session/Line owner workflow methods.
Billing execution is deliberately deferred to Prompt 18.
"""

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import (
    RESET_CANCEL_THEN_DELETE,
    RESET_FRESH_DB_ONLY,
)
from ...services.generator_registry import GENERATOR_REGISTRY


SESSION_SPECS = (
    {
        "key": "DEMO-SESSION-001",
        "booking_key": "DEMO-BOOK-TODAY-002",
        "encounter_key": "DEMO-ENC-LIVE-001",
        "target": "done",
        "scenario": "SCN-SESSION-01",
    },
    {
        "key": "DEMO-SESSION-NOSHOW-001",
        "booking_key": "DEMO-BOOK-TODAY-004",
        "encounter_key": False,
        "target": "no_show",
        "scenario": "SCN-SESSION-02",
    },
    {
        "key": "DEMO-SESSION-CANCEL-001",
        "booking_key": "DEMO-BOOK-TODAY-005",
        "encounter_key": False,
        "target": "cancelled",
        "scenario": "SCN-SESSION-02",
    },
)


@GENERATOR_REGISTRY.register
class TreatmentSessionClinicalJourneyGenerator(BaseDemoGenerator):
    key = "operations.treatment_session"
    phase = "16_clinical"
    sequence = 640
    depends_on = ("operations.encounter",)
    scenario_keys = ("SCN-SESSION-01", "SCN-SESSION-02")
    owned_models = (
        "clinic.treatment.session",
        "clinic.treatment.session.line",
    )
    required_groups = ("base.group_user",)

    @staticmethod
    def _counters():
        return {
            "created": 0, "reused": 0, "updated": 0,
            "skipped": 0, "warning": 0, "error": 0,
        }

    def _resolve(self, ctx, key, model, missing_ok=False, record_user=None):
        return ctx.reference_service.resolve(
            ctx.run, key, model, missing_ok=missing_ok, record_user=record_user
        )

    def _preflight(self, ctx):
        requirements = {
            "booking.booking": {
                "patient_id", "doctor_id", "treatment_id",
                "start_datetime", "end_datetime", "treatment_session_ids",
            },
            "clinic.treatment.session": {
                "company_id", "patient_id", "clinic_doctor_id", "doctor_id",
                "treatment_id", "booking_id", "encounter_id",
                "start_datetime", "end_datetime", "state",
                "actual_start_datetime", "actual_end_datetime", "line_ids",
            },
            "clinic.treatment.session.line": {
                "session_id", "usage_type", "display_type", "name",
                "quantity", "consumed_qty", "is_billable",
                "consumption_state", "date_consumed",
            },
        }
        missing = []
        for model_name, wanted in requirements.items():
            Model = ctx.env[model_name]
            absent = sorted(wanted - set(Model._fields))
            if absent:
                missing.append(f"{model_name} missing fields {', '.join(absent)}")

        relations = {
            ("booking.booking", "patient_id"): "res.partner",
            ("booking.booking", "doctor_id"): "clinic.doctor",
            ("clinic.treatment.session", "patient_id"): "res.partner",
            ("clinic.treatment.session", "clinic_doctor_id"): "hr.employee",
            ("clinic.treatment.session", "doctor_id"): "clinic.doctor",
            ("clinic.treatment.session", "booking_id"): "booking.booking",
            ("clinic.treatment.session", "encounter_id"): "clinic.encounter",
            ("clinic.treatment.session.line", "session_id"): "clinic.treatment.session",
        }
        for (model_name, field_name), expected in relations.items():
            field = ctx.env[model_name]._fields.get(field_name)
            actual = getattr(field, "comodel_name", None) if field else None
            if actual != expected:
                missing.append(
                    f"{model_name}.{field_name} comodel is "
                    f"{actual or 'missing'}, expected {expected}"
                )

        owner_methods = {
            "booking.booking": ("generate_treatment_sessions",),
            "clinic.treatment.session": (
                "action_confirm", "action_start", "action_done",
                "action_no_show", "action_cancel",
            ),
            "clinic.treatment.session.line": (
                "action_mark_ready", "action_mark_consumed",
            ),
        }
        for model_name, methods in owner_methods.items():
            Model = ctx.env[model_name]
            for method in methods:
                if not hasattr(Model, method):
                    missing.append(f"{model_name} missing owner method {method}")

        for spec in SESSION_SPECS:
            booking = self._resolve(
                ctx, spec["booking_key"], "booking.booking", missing_ok=True
            )
            if not booking:
                missing.append(f"required Booking reference {spec['booking_key']} is missing")
                continue
            clinician = booking.doctor_id.user_id if booking.doctor_id else False
            if not clinician:
                missing.append(
                    f"{spec['booking_key']} Doctor has no linked res.users clinician."
                )
            elif not clinician.has_group(
                "clinic_treatment_session.group_treatment_session_clinician"
            ):
                missing.append(
                    f"{spec['booking_key']} Doctor user lacks Treatment Session Clinician access."
                )
        if not self._resolve(
            ctx, "DEMO-ENC-LIVE-001", "clinic.encounter", missing_ok=True
        ):
            missing.append("DEMO-ENC-LIVE-001 is missing")

        if missing:
            raise UserError(_(
                "MASTER PROMPT 16 Treatment Session preflight failed: %s"
            ) % "; ".join(missing))

    def _session_from_booking(self, ctx, counters, spec):
        booking = self._resolve(ctx, spec["booking_key"], "booking.booking")
        clinician = booking.doctor_id.user_id
        existing = self._resolve(
            ctx, spec["key"], "clinic.treatment.session",
            missing_ok=True, record_user=clinician,
        )
        if existing:
            counters["reused"] += 1
            return existing, clinician

        actor_booking = booking.with_user(clinician)
        before = actor_booking.treatment_session_ids
        if before:
            raise UserError(_(
                "Booking %s already has Treatment Session record(s) but demo key %s "
                "is not bound. Refusing fuzzy adoption or duplicate generation."
            ) % (booking.display_name, spec["key"]))

        owner_created = actor_booking.generate_treatment_sessions()
        created = actor_booking.treatment_session_ids - before
        if owner_created != created:
            raise UserError(_(
                "Booking %s owner generation result does not match the exact "
                "new Treatment Session delta."
            ) % booking.display_name)
        if len(created) != 1:
            raise UserError(_(
                "Booking %s must generate exactly one Treatment Session for %s; found %s."
            ) % (booking.display_name, spec["key"], len(created)))

        session = created.ensure_one()
        ctx.reference_service.bind(
            run=ctx.run,
            demo_key=spec["key"],
            record=session,
            generator_key=self.key,
            scenario_key=spec["scenario"],
            ownership_kind="created",
            reset_policy=(
                RESET_FRESH_DB_ONLY
                if spec["target"] == "done"
                else RESET_CANCEL_THEN_DELETE
            ),
            reset_sequence=970,
            record_user=clinician,
        )
        counters["created"] += 1
        return session, clinician

    def _line(self, ctx, counters, session, clinician):
        key = "DEMO-SESSION-LINE-001"
        existing = self._resolve(
            ctx, key, "clinic.treatment.session.line",
            missing_ok=True, record_user=clinician,
        )
        if existing:
            counters["reused"] += 1
            return existing

        line = ctx.env["clinic.treatment.session.line"].with_user(clinician).create({
            "session_id": session.id,
            "display_type": "line",
            "usage_type": "service",
            "name": "Synthetic clinical service execution",
            "quantity": 1.0,
            "is_billable": False,
            "price_unit": 0.0,
            "note_internal": (
                "Demo service-consumption line. Billing is intentionally deferred "
                "to MASTER PROMPT 18."
            ),
        })
        ctx.reference_service.bind(
            run=ctx.run,
            demo_key=key,
            record=line,
            generator_key=self.key,
            scenario_key="SCN-SESSION-01",
            ownership_kind="created",
            reset_policy=RESET_FRESH_DB_ONLY,
            reset_sequence=980,
            record_user=clinician,
        )
        counters["created"] += 1
        return line

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._preflight(ctx)
        for spec in SESSION_SPECS:
            session, clinician = self._session_from_booking(ctx, counters, spec)
            if spec["encounter_key"]:
                encounter = self._resolve(
                    ctx, spec["encounter_key"], "clinic.encounter"
                )
                if session.encounter_id != encounter:
                    session.write({"encounter_id": encounter.id})

            actor_session = session.with_user(clinician)
            target = spec["target"]

            if target == "done":
                line = self._line(ctx, counters, session, clinician)
                if line.consumption_state == "planned":
                    line.action_mark_ready()
                if line.consumption_state == "ready":
                    line.action_mark_consumed()

                if session.state == "draft":
                    actor_session.action_confirm()
                if session.state == "confirmed":
                    actor_session.action_start()
                if session.state == "in_progress":
                    actor_session.action_done()

                # Preserve anchor-relative business execution times without
                # changing create_date/write_date or bypassing state workflow.
                session.write({
                    "actual_start_datetime": session.start_datetime,
                    "actual_end_datetime": session.end_datetime,
                })

                encounter = session.encounter_id
                if encounter and encounter.state == "in_progress":
                    plan = encounter.procedure_line_ids[:1]
                    if plan and plan.state == "planned":
                        plan.action_start()
                    if plan and plan.state == "in_progress":
                        plan.action_done()
                    encounter.action_done()
                    encounter.write({
                        "date_start": session.start_datetime,
                        "date_end": session.end_datetime,
                    })

            elif target == "no_show":
                if session.state == "draft":
                    actor_session.action_confirm()
                if session.state == "confirmed":
                    actor_session.action_no_show()

            elif target == "cancelled":
                if session.state == "draft":
                    actor_session.action_confirm()
                if session.state in ("confirmed", "in_progress"):
                    actor_session.action_cancel()

        return counters

    def validate(self, ctx, scenario):
        issues = []
        expected = {
            "DEMO-SESSION-001": "done",
            "DEMO-SESSION-NOSHOW-001": "no_show",
            "DEMO-SESSION-CANCEL-001": "cancelled",
        }
        for key, state in expected.items():
            spec = next(item for item in SESSION_SPECS if item["key"] == key)
            booking = self._resolve(ctx, spec["booking_key"], "booking.booking")
            clinician = booking.doctor_id.user_id
            session = self._resolve(
                ctx, key, "clinic.treatment.session",
                missing_ok=True, record_user=clinician,
            )
            if not session:
                issues.append(f"{key} is missing.")
                continue
            if session.state != state:
                issues.append(f"{key} expected state {state}, found {session.state}.")
            if not session.patient_id or not session.booking_id:
                issues.append(f"{key} is missing Booking/patient linkage.")
            if session.booking_id.patient_id != session.patient_id:
                issues.append(f"{key} patient does not match Booking.")
            if session.doctor_id and session.booking_id.doctor_id != session.doctor_id:
                issues.append(f"{key} Clinic Doctor does not match Booking.")

        done_booking = self._resolve(ctx, "DEMO-BOOK-TODAY-002", "booking.booking")
        done_clinician = done_booking.doctor_id.user_id
        done = self._resolve(
            ctx, "DEMO-SESSION-001", "clinic.treatment.session",
            missing_ok=True, record_user=done_clinician,
        )
        line = self._resolve(
            ctx, "DEMO-SESSION-LINE-001",
            "clinic.treatment.session.line",
            missing_ok=True, record_user=done_clinician,
        )
        encounter = self._resolve(
            ctx, "DEMO-ENC-LIVE-001", "clinic.encounter", missing_ok=True
        )
        if not done or not line or line.session_id != done:
            issues.append("Completed Treatment Session consumption line is incomplete.")
        elif line.consumption_state != "consumed":
            issues.append("Completed Treatment Session line is not Consumed.")
        if done and encounter and done.encounter_id != encounter:
            issues.append("Completed Treatment Session is not linked to the live Encounter.")
        if encounter and encounter.state != "done":
            issues.append("Live Encounter was not completed after Treatment Session delivery.")

        return issues

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}









