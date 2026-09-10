
"""MASTER PROMPT 16 — Encounter & Core Clinical Journey.

This bounded generator creates source-valid Encounter journeys only after the
Prompt-15 arrival/triage checkpoint is complete.  It uses owner business methods
for Encounter, SOAP, diagnosis, procedure and Post-Care lifecycle transitions.
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import _, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import (
    RESET_DEACTIVATE,
    RESET_FRESH_DB_ONLY,
)
from ...services.generator_registry import GENERATOR_REGISTRY


ENCOUNTER_SPECS = (
    {
        "key": "DEMO-ENC-001",
        "patient_key": "DEMO-PAT-NEW-001",
        "booking_key": False,
        "treatment_key": "DEMO-TREAT-CONSULT-GEN",
        "procedure_key": "DEMO-PROC-CONSULT",
        "offset_days": 0,
        "hour": 13,
        "state": "done",
        "diagnosis": "Synthetic routine clinical assessment",
        "chronicity": "acute",
        "scenario": "SCN-ENCOUNTER-01",
    },
    {
        "key": "DEMO-ENC-LIVE-001",
        "patient_key": False,
        "booking_key": "DEMO-BOOK-TODAY-002",
        "treatment_key": False,
        "procedure_key": "DEMO-PROC-CONSULT",
        "offset_days": 0,
        "hour": 14,
        "state": "in_progress",
        "diagnosis": "Synthetic active-visit assessment",
        "chronicity": "acute",
        "scenario": "SCN-ENCOUNTER-01",
    },
    {
        "key": "DEMO-ENC-RET-001",
        "patient_key": "DEMO-PAT-RET-001",
        "booking_key": "DEMO-BOOK-HIST-001",
        "treatment_key": False,
        "procedure_key": "DEMO-PROC-FOLLOWUP",
        "offset_days": -30,
        "hour": 10,
        "state": "done",
        "diagnosis": "Synthetic returning-patient follow-up assessment",
        "chronicity": "subacute",
        "scenario": "SCN-ENCOUNTER-RET-01",
    },
    {
        "key": "DEMO-ENC-CHRON-001",
        "patient_key": "DEMO-PAT-CHRON-001",
        "booking_key": False,
        "treatment_key": "DEMO-TREAT-PHYSIO",
        "procedure_key": "DEMO-PROC-THERAPY",
        "offset_days": -90,
        "hour": 11,
        "state": "done",
        "diagnosis": "Synthetic recurring-care functional review",
        "chronicity": "chronic",
        "scenario": "SCN-ENCOUNTER-RET-01",
    },
    {
        "key": "DEMO-ENC-PKG-001",
        "patient_key": "DEMO-PAT-PKG-001",
        "booking_key": False,
        "treatment_key": "DEMO-TREAT-SKIN-PROC",
        "procedure_key": "DEMO-PROC-SKIN",
        "offset_days": -7,
        "hour": 15,
        "state": "done",
        "diagnosis": "Synthetic package-service eligibility review",
        "chronicity": "acute",
        "scenario": "SCN-ENCOUNTER-01",
    },
)

PROCEDURES = (
    ("DEMO-PROC-CONSULT", "DEMO-CONSULT", "Clinical Consultation Procedure", 30, 250000.0),
    ("DEMO-PROC-FOLLOWUP", "DEMO-FOLLOWUP", "Clinical Follow-up Procedure", 20, 180000.0),
    ("DEMO-PROC-THERAPY", "DEMO-THERAPY", "Recurring Therapy Procedure", 60, 350000.0),
    ("DEMO-PROC-SKIN", "DEMO-SKIN", "Skin Rejuvenation Procedure", 60, 850000.0),
)


@GENERATOR_REGISTRY.register
class EncounterCoreClinicalJourneyGenerator(BaseDemoGenerator):
    key = "operations.encounter"
    phase = "16_clinical"
    sequence = 630
    depends_on = ("operations.queue_triage",)
    scenario_keys = ("SCN-ENCOUNTER-01", "SCN-ENCOUNTER-RET-01")
    owned_models = (
        "clinic.encounter.stage",
        "clinic.procedure.category",
        "clinic.procedure.catalog",
        "clinic.encounter",
        "clinic.soap.note",
        "clinic.diagnosis",
        "clinic.encounter.procedure",
        "clinic.postcare.protocol",
        "clinic.postcare.plan",
    )
    required_groups = ("base.group_user",)

    @staticmethod
    def _counters():
        return {
            "created": 0, "reused": 0, "updated": 0,
            "skipped": 0, "warning": 0, "error": 0,
        }

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _resolve(self, ctx, key, model, missing_ok=False, record_user=None):
        return ctx.reference_service.resolve(
            ctx.run, key, model, missing_ok=missing_ok, record_user=record_user
        )

    def _ensure(
        self, ctx, counters, key, model, values, policy,
        reset_sequence, scenario_key, update=False, model_env=None,
        record_user=None,
    ):
        Model = model_env or ctx.env[model].with_company(ctx.run.company_id)

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
            record_user=record_user,
        )
        self._bump(counters, status)
        return record, status

    @staticmethod
    def _local_utc(ctx, date_value, hour, minute=0):
        tz = pytz.timezone(ctx.run.timezone or "UTC")
        local = tz.localize(datetime.combine(date_value, time(hour, minute)))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _preflight(self, ctx):
        requirements = {
            "clinic.encounter": {
                "company_id", "patient_id", "doctor_id", "appointment_id",
                "stage_id", "state", "date_planned_start", "date_planned_end",
                "date_start", "date_end", "diagnosis_note",
                "procedure_line_ids", "treatment_id",
            },
            "clinic.encounter.stage": {
                "name", "company_id", "state", "sequence", "active",
            },
            "clinic.soap.note": {
                "encounter_id", "company_id", "date_note", "state",
                "chief_complaint", "subjective", "objective",
                "assessment", "plan", "assessment_diagnosis_ids",
            },
            "clinic.diagnosis": {
                "name", "company_id", "encounter_id", "code_system",
                "source", "type", "certainty", "severity", "chronicity",
                "status", "date_diagnosed", "description",
            },
            "clinic.procedure.category": {
                "name", "code", "company_id", "active", "sequence",
            },
            "clinic.procedure.catalog": {
                "name", "code", "company_id", "category_id", "list_price",
                "billing_policy", "default_duration_min", "default_sessions",
                "require_consent", "require_checklist",
            },
            "clinic.encounter.procedure": {
                "encounter_id", "diagnosis_id", "procedure_id",
                "planned_sessions", "planned_duration", "price_unit",
                "billing_policy", "state", "performer_user_id",
                "performer_doctor_id",
            },
            "clinic.postcare.protocol": {
                "name", "code", "company_id", "state", "risk_level",
                "default_assignee_id", "default_duration_days",
                "auto_generate_tasks", "instruction_html",
            },
            "clinic.postcare.plan": {
                "patient_id", "protocol_id", "source_type",
                "encounter_id", "start_datetime", "state",
            },
        }
        missing = []
        for model_name, fields_required in requirements.items():
            Model = ctx.env[model_name]
            absent = sorted(fields_required - set(Model._fields))
            if absent:
                missing.append(f"{model_name} missing fields {', '.join(absent)}")

        relations = {
            ("clinic.encounter", "patient_id"): "clinic.patient",
            ("clinic.encounter", "doctor_id"): "clinic.doctor",
            ("clinic.encounter", "appointment_id"): "booking.booking",
            ("clinic.encounter", "treatment_id"): "clinic.treatment",
            ("clinic.soap.note", "encounter_id"): "clinic.encounter",
            ("clinic.diagnosis", "encounter_id"): "clinic.encounter",
            ("clinic.encounter.procedure", "encounter_id"): "clinic.encounter",
            ("clinic.encounter.procedure", "procedure_id"): "clinic.procedure.catalog",
            ("clinic.postcare.plan", "encounter_id"): "clinic.encounter",
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
            "clinic.encounter": (
                "action_start", "action_done", "action_create_postcare_plan",
            ),
            "clinic.soap.note": ("action_finalize",),
            "clinic.diagnosis": ("action_set_primary",),
            "clinic.encounter.procedure": (
                "action_plan", "action_start", "action_done",
            ),
            "clinic.postcare.protocol": ("action_activate",),
        }
        for model_name, methods in owner_methods.items():
            Model = ctx.env[model_name]
            for method in methods:
                if not hasattr(Model, method):
                    missing.append(f"{model_name} missing owner method {method}")

        for key, model in (
            ("DEMO-PAT-NEW-001", "clinic.patient"),
            ("DEMO-PAT-RET-001", "clinic.patient"),
            ("DEMO-PAT-CHRON-001", "clinic.patient"),
            ("DEMO-PAT-PKG-001", "clinic.patient"),
            ("DEMO-DOC-001", "clinic.doctor"),
            ("DEMO-USER-DOC-001", "res.users"),
            ("DEMO-USER-MGR", "res.users"),
            ("DEMO-STAFF-MGR", "clinic.staff"),
            ("DEMO-TREAT-CONSULT-GEN", "clinic.treatment"),
            ("DEMO-TREAT-FOLLOW-UP", "clinic.treatment"),
            ("DEMO-TREAT-PHYSIO", "clinic.treatment"),
            ("DEMO-TREAT-SKIN-PROC", "clinic.treatment"),
            ("DEMO-BOOK-TODAY-002", "booking.booking"),
            ("DEMO-BOOK-HIST-001", "booking.booking"),
            ("DEMO-TRIAGE-NORMAL-001", "clinic.triage.session"),
        ):
            if not self._resolve(ctx, key, model, missing_ok=True):
                missing.append(f"required demo reference {key} ({model}) is missing")

        doctor_user = self._resolve(ctx, "DEMO-USER-DOC-001", "res.users", missing_ok=True)
        if doctor_user and not doctor_user.has_group(
            "clinic_treatment_session.group_treatment_session_clinician"
        ):
            missing.append("DEMO-USER-DOC-001 lacks Treatment Session Clinician access")

        manager_user = self._resolve(ctx, "DEMO-USER-MGR", "res.users", missing_ok=True)
        if manager_user and not manager_user.has_group(
            "clinic_post_care_followup.group_postcare_manager"
        ):
            missing.append("DEMO-USER-MGR lacks Post-Care Manager access")

        if missing:
            raise UserError(_(
                "MASTER PROMPT 16 Encounter preflight failed: %s"
            ) % "; ".join(missing))

    def _ensure_stages(self, ctx, counters):
        for sequence, state, label in (
            (1, "draft", "Demo Draft"),
            (2, "in_progress", "Demo In Progress"),
            (3, "done", "Demo Done"),
            (4, "cancelled", "Demo Cancelled"),
        ):
            self._ensure(
                ctx, counters, f"DEMO-ENC-STAGE-{state.upper()}",
                "clinic.encounter.stage",
                {
                    "name": label,
                    "sequence": sequence,
                    "active": True,
                    "company_id": ctx.run.company_id.id,
                    "state": state,
                    "fold": state in ("done", "cancelled"),
                    "allow_edit": state not in ("done", "cancelled"),
                },
                RESET_DEACTIVATE, 410,
                "SCN-ENCOUNTER-01",
            )

    def _ensure_procedures(self, ctx, counters):
        category, _ = self._ensure(
            ctx, counters, "DEMO-PROC-CAT-CLINICAL",
            "clinic.procedure.category",
            {
                "name": "ClinicOne Demo — Core Clinical Procedures",
                "code": "DEMO-CLINICAL",
                "sequence": 10,
                "active": True,
                "company_id": ctx.run.company_id.id,
                "description": "Synthetic procedure masters for MASTER PROMPT 16 only.",
            },
            RESET_DEACTIVATE, 420, "SCN-ENCOUNTER-01",
        )
        for key, code, name, duration, price in PROCEDURES:
            self._ensure(
                ctx, counters, key, "clinic.procedure.catalog",
                {
                    "name": name,
                    "code": code,
                    "sequence": 10,
                    "active": True,
                    "company_id": ctx.run.company_id.id,
                    "category_id": category.id,
                    "list_price": price,
                    "standard_price": 0.0,
                    "billing_policy": "per_plan",
                    "default_duration_min": duration,
                    "default_sessions": 1,
                    "require_consent": False,
                    "require_checklist": False,
                    "instructions_pre": "<p>Synthetic demo preparation instructions.</p>",
                    "instructions_post": "<p>Synthetic demo after-care instructions.</p>",
                    "note": "MASTER PROMPT 16 synthetic procedure master.",
                },
                RESET_DEACTIVATE, 430, "SCN-ENCOUNTER-01",
            )

    def _patient_for_booking(self, ctx, booking):
        Patient = ctx.env["clinic.patient"].with_company(ctx.run.company_id)
        candidates = Patient.search([
            ("partner_id", "=", booking.patient_id.id),
            ("company_id", "=", ctx.run.company_id.id),
        ], limit=2)
        if len(candidates) != 1:
            raise UserError(_(
                "Prompt 16 requires exactly one clinic.patient for Booking %s; found %s."
            ) % (booking.display_name, len(candidates)))
        return candidates

    def _ensure_postcare_protocol(self, ctx, counters):
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        manager_staff = self._resolve(ctx, "DEMO-STAFF-MGR", "clinic.staff")
        Model = (
            ctx.env["clinic.postcare.protocol"]
            .with_user(manager)
            .with_company(ctx.run.company_id)
        )
        protocol, status = self._ensure(
            ctx, counters, "DEMO-POSTCARE-PROTOCOL-CORE",
            "clinic.postcare.protocol",
            {
                "name": "ClinicOne Demo — Core Encounter Follow-up",
                "code": "DEMO-ENC-FOLLOWUP",
                "sequence": 5,
                "active": True,
                "company_id": ctx.run.company_id.id,
                "risk_level": "routine",
                "default_assignee_id": manager_staff.id,
                "default_duration_days": 14,
                "auto_generate_tasks": False,
                "instruction_html": (
                    "<p>Synthetic follow-up instructions for the ClinicOne demo. "
                    "This is not medical advice.</p>"
                ),
                "warning_signs_html": (
                    "<p>Contact the clinic if the synthetic demo scenario requires review.</p>"
                ),
                "internal_note": "Demo-only generic protocol for Encounter follow-up linkage.",
            },
            RESET_DEACTIVATE, 440, "SCN-ENCOUNTER-01",
            model_env=Model,
            record_user=manager,
        )
        if protocol.state == "draft":
            protocol.with_user(manager).action_activate()
        if protocol.state != "active":
            raise UserError(_("Prompt 16 Post-Care Protocol did not reach Active state."))
        return protocol

    def _encounter_context(self, ctx, spec):
        booking = (
            self._resolve(ctx, spec["booking_key"], "booking.booking")
            if spec["booking_key"] else False
        )
        if booking:
            patient = self._patient_for_booking(ctx, booking)
            doctor = booking.doctor_id
            treatment = booking.treatment_id
            planned_start = booking.start_datetime
            planned_end = booking.end_datetime
        else:
            patient = self._resolve(ctx, spec["patient_key"], "clinic.patient")
            doctor = self._resolve(ctx, "DEMO-DOC-001", "clinic.doctor")
            treatment = self._resolve(ctx, spec["treatment_key"], "clinic.treatment")
            date_value = fields.Date.to_date(ctx.run.anchor_date) + timedelta(
                days=spec["offset_days"]
            )
            planned_start = self._local_utc(ctx, date_value, spec["hour"])
            duration = int(
                getattr(treatment, "booking_default_duration_minutes", 30) or 30
            )
            planned_end = planned_start + timedelta(minutes=min(max(duration, 20), 60))
        return booking, patient, doctor, treatment, planned_start, planned_end

    def _ensure_encounter_bundle(self, ctx, counters, spec):
        booking, patient, doctor, treatment, start_dt, end_dt = self._encounter_context(
            ctx, spec
        )
        draft_stage = self._resolve(
            ctx, "DEMO-ENC-STAGE-DRAFT", "clinic.encounter.stage"
        )
        encounter, status = self._ensure(
            ctx, counters, spec["key"], "clinic.encounter",
            {
                "company_id": ctx.run.company_id.id,
                "patient_id": patient.id,
                "doctor_id": doctor.id,
                "user_id": doctor.user_id.id or ctx.env.user.id,
                "appointment_id": booking.id if booking else False,
                "treatment_id": treatment.id,
                "stage_id": draft_stage.id,
                "date_planned_start": start_dt,
                "date_planned_end": end_dt,
                "planned_duration": max(
                    (end_dt - start_dt).total_seconds() / 60.0, 0.0
                ),
                "priority": "0",
                "diagnosis_note": (
                    "Synthetic assessment only; no real patient diagnosis is implied."
                ),
                "internal_note": (
                    "MASTER PROMPT 16 synthetic clinical encounter. "
                    "All identities and clinical values are fictional."
                ),
            },
            RESET_FRESH_DB_ONLY, 900, spec["scenario"],
        )

        dx_key = spec["key"].replace("DEMO-ENC-", "DEMO-DX-")
        diagnosis, _ = self._ensure(
            ctx, counters, dx_key, "clinic.diagnosis",
            {
                "name": spec["diagnosis"],
                "company_id": ctx.run.company_id.id,
                "encounter_id": encounter.id,
                "code_system": "free_text",
                "source": "manual",
                "type": "secondary",
                "certainty": "suspected",
                "severity": "mild",
                "chronicity": spec["chronicity"],
                "status": "active",
                "date_diagnosed": fields.Datetime.to_datetime(start_dt).date(),
                "description": (
                    "Synthetic demonstration classification; not a medical diagnosis."
                ),
            },
            RESET_FRESH_DB_ONLY, 910, spec["scenario"],
        )
        if diagnosis.type != "primary":
            diagnosis.action_set_primary()

        soap_key = spec["key"].replace("DEMO-ENC-", "DEMO-SOAP-")
        soap, soap_status = self._ensure(
            ctx, counters, soap_key, "clinic.soap.note",
            {
                "company_id": ctx.run.company_id.id,
                "encounter_id": encounter.id,
                "user_id": doctor.user_id.id or ctx.env.user.id,
                "date_note": start_dt + timedelta(minutes=5),
                "priority": "0",
                "chief_complaint": "Synthetic demonstration visit",
                "subjective": "<p>Synthetic patient-reported information for demo purposes.</p>",
                "objective": "<p>Source-linked clinical review completed in the demo workflow.</p>",
                "assessment": "<p>Synthetic assessment; no real diagnosis is asserted.</p>",
                "plan": "<p>Proceed with the source-supported demo procedure and follow-up.</p>",
                "assessment_diagnosis_ids": [(6, 0, [diagnosis.id])],
            },
            RESET_FRESH_DB_ONLY, 920, spec["scenario"],
        )
        if soap.state == "draft":
            soap.action_finalize(create_free_dx=False)

        procedure = self._resolve(ctx, spec["procedure_key"], "clinic.procedure.catalog")
        proc_key = spec["key"].replace("DEMO-ENC-", "DEMO-ENCPROC-")
        proc_vals = procedure.prepare_plan_vals(encounter, diagnosis=diagnosis)
        proc_vals.update({
            "performer_user_id": doctor.user_id.id or False,
            "performer_doctor_id": doctor.id,
        })
        plan, plan_status = self._ensure(
            ctx, counters, proc_key, "clinic.encounter.procedure",
            proc_vals,
            RESET_FRESH_DB_ONLY, 930, spec["scenario"],
        )
        if plan.state == "draft":
            plan.action_plan()

        if spec["state"] in ("in_progress", "done") and encounter.state == "draft":
            encounter.action_start()
            encounter.write({"date_start": start_dt})

        if spec["state"] == "done":
            if plan.state == "planned":
                plan.action_start()
            if plan.state == "in_progress":
                plan.action_done()
            if encounter.state == "in_progress":
                encounter.action_done()
            # Historical/current business date fields may be anchor-relative;
            # technical create/write audit timestamps are never backdated.
            encounter.write({
                "date_start": start_dt,
                "date_end": end_dt,
            })

        return encounter

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._preflight(ctx)
        self._ensure_stages(ctx, counters)
        self._ensure_procedures(ctx, counters)
        self._ensure_postcare_protocol(ctx, counters)

        encounters = {}
        for spec in ENCOUNTER_SPECS:
            encounters[spec["key"]] = self._ensure_encounter_bundle(
                ctx, counters, spec
            )

        # Source-supported follow-up linkage is created only after a completed
        # Encounter.  Detailed future task/check-in population remains Prompt 20.
        encounter = encounters["DEMO-ENC-001"]
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        postcare = self._resolve(
            ctx, "DEMO-POSTCARE-ENC-001", "clinic.postcare.plan",
            missing_ok=True, record_user=manager,
        )
        if not postcare:
            manager_encounter = encounter.with_user(manager)
            manager_encounter.action_create_postcare_plan()
            postcare = manager_encounter.postcare_plan_ids.filtered(
                lambda plan: plan.state != "cancelled"
            )[:1]
            if not postcare:
                raise UserError(_("Prompt 16 failed to create Encounter Post-Care linkage."))
            ctx.reference_service.bind(
                run=ctx.run,
                demo_key="DEMO-POSTCARE-ENC-001",
                record=postcare,
                generator_key=self.key,
                scenario_key="SCN-ENCOUNTER-01",
                ownership_kind="created",
                reset_policy=RESET_FRESH_DB_ONLY,
                reset_sequence=940,
                record_user=manager,
            )
            counters["created"] += 1
        else:
            counters["reused"] += 1

        return counters

    def validate(self, ctx, scenario):
        issues = []
        expected_states = {
            "DEMO-ENC-001": "done",
            "DEMO-ENC-LIVE-001": "in_progress",
            "DEMO-ENC-RET-001": "done",
            "DEMO-ENC-CHRON-001": "done",
            "DEMO-ENC-PKG-001": "done",
        }
        for key, expected_state in expected_states.items():
            encounter = self._resolve(ctx, key, "clinic.encounter", missing_ok=True)
            if not encounter:
                issues.append(f"{key} is missing.")
                continue
            if encounter.state != expected_state:
                issues.append(
                    f"{key} expected state {expected_state}, found {encounter.state}."
                )
            if not encounter.patient_id or not encounter.doctor_id:
                issues.append(f"{key} is missing patient/provider.")
            if not encounter.procedure_line_ids:
                issues.append(f"{key} has no procedure plan.")
            if encounter.state == "done" and (
                not encounter.date_start or not encounter.date_end
                or encounter.date_end < encounter.date_start
            ):
                issues.append(f"{key} has invalid completed chronology.")

        live = self._resolve(ctx, "DEMO-ENC-LIVE-001", "clinic.encounter", missing_ok=True)
        triage = self._resolve(
            ctx, "DEMO-TRIAGE-NORMAL-001", "clinic.triage.session", missing_ok=True
        )
        booking = self._resolve(
            ctx, "DEMO-BOOK-TODAY-002", "booking.booking", missing_ok=True
        )
        if live and triage and live.patient_id != triage.patient_id:
            issues.append("Live Encounter patient does not match Prompt-15 normal Triage.")
        if live and booking and live.appointment_id != booking:
            issues.append("Live Encounter is not linked to its Prompt-14 Booking.")

        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        postcare = self._resolve(
            ctx, "DEMO-POSTCARE-ENC-001", "clinic.postcare.plan",
            missing_ok=True, record_user=manager,
        )
        core = self._resolve(ctx, "DEMO-ENC-001", "clinic.encounter", missing_ok=True)
        if not postcare or not core or postcare.encounter_id != core:
            issues.append("Core Encounter Post-Care linkage is incomplete.")

        return issues

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}









