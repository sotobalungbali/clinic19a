




"""MASTER PROMPT 13 — deterministic longitudinal patient history.

Prompt 13 proves the historical engine with source-native patient history that
does not pre-empt the Booking/Encounter/Commercial workflows owned by later
Master Prompts. Those later generators consume HistoricalTimelineService.
"""

from odoo import _, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_DELETE_SAFE
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.historical_service import (
    BUSINESS_DATE_FIELDS,
    HISTORICAL_BUCKETS,
    HistoricalTimelineService,
    PROFILE_HISTORY_BUDGETS,
)


HISTORY_PATIENT_KEYS = (
    "DEMO-PAT-RET-001",
    "DEMO-PAT-ELDER-001",
    "DEMO-PAT-CHRON-001",
    "DEMO-PAT-FREQ-001",
    "DEMO-PAT-PKG-001",
    "DEMO-PAT-IMG-001",
    "DEMO-PAT-EMAR-001",
    "DEMO-PAT-TELE-001",
    "DEMO-PAT-MEM-001",
    "DEMO-PAT-INS-001",
    "DEMO-PAT-INC-001",
    "DEMO-PAT-VIP-001",
)

PROFILE_HISTORY_PATIENT_COUNTS = {
    "compact": 6,
    "standard": 8,
    "full_enterprise": 12,
}

PROFILE_CONDITION_EPISODES = {
    "compact": 3,
    "standard": 4,
    "full_enterprise": 6,
}

CONDITION_EPISODE_DAYS = (330, 240, 150, 75, 28, 6)


@GENERATOR_REGISTRY.register
class HistoricalPatientLongitudinalGenerator(BaseDemoGenerator):
    key = "history.patient_longitudinal"
    phase = "13_history"
    sequence = 550
    depends_on = ("resources.rooms_devices",)
    scenario_keys = ("SCN-PATIENT-RET-01",)
    owned_models = (
        "clinic.patient.vital",
        "clinic.patient.condition.episode",
        "clinic.patient.allergy.reaction",
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

    def _ensure(
        self, ctx, counters, key, model, values, reset_sequence,
        scenario_key="SCN-PATIENT-RET-01",
    ):
        Model = ctx.env[model].with_company(ctx.run.company_id)

        def create():
            return Model.create(dict(values))

        def update_record(record):
            record.write(dict(values))

        record, reference, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=scenario_key,
            create_callback=create,
            update_callback=update_record,
            reset_policy=RESET_DELETE_SAFE,
            reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record, reference

    def _timeline(self, ctx):
        return HistoricalTimelineService(ctx.run, ctx.seed_service)

    def _preflight(self, ctx):
        requirements = {
            "clinic.patient.vital": {
                "patient_id", "measured_datetime", "measured_by", "device_name",
                "device_serial", "device_type", "bp_systolic", "bp_diastolic",
                "heart_rate", "respiratory_rate", "temperature_c", "spo2",
                "blood_glucose_mgdl", "pain_scale", "notes",
            },
            "clinic.patient.condition.episode": {
                "condition_id", "episode_datetime", "description", "severity", "outcome",
            },
            "clinic.patient.allergy.reaction": {
                "allergy_id", "onset_datetime", "recorded_date", "reaction_text",
                "description", "severity", "exposure_route", "outcome", "recorded_by",
            },
        }
        missing = []
        for model_name, fields_required in requirements.items():
            if model_name not in ctx.env:
                missing.append(f"missing model {model_name}")
                continue
            absent = sorted(fields_required - set(ctx.env[model_name]._fields))
            if absent:
                missing.append(f"{model_name} missing fields {', '.join(absent)}")

        # Validate the downstream business-date contract now, before any later
        # generator is allowed to synthesize history by technical timestamps.
        for model_name, date_fields in BUSINESS_DATE_FIELDS.items():
            if model_name not in ctx.env:
                missing.append(f"missing historical contract model {model_name}")
                continue
            absent = sorted(set(date_fields) - set(ctx.env[model_name]._fields))
            if absent:
                missing.append(
                    f"{model_name} missing historical business fields {', '.join(absent)}"
                )

        patient_count = PROFILE_HISTORY_PATIENT_COUNTS[ctx.profile]
        for key in HISTORY_PATIENT_KEYS[:patient_count]:
            ctx.reference_service.resolve(ctx.run, key, "clinic.patient")

        ctx.reference_service.resolve(ctx.run, "DEMO-USER-NUR-001", "res.users")
        ctx.reference_service.resolve(ctx.run, "DEMO-DEVICE-MON-01", "clinic.device")
        ctx.reference_service.resolve(
            ctx.run, "DEMO-PATCOND-CHRON-001", "clinic.patient.condition"
        )
        ctx.reference_service.resolve(
            ctx.run, "DEMO-PATALLERGY-EMAR-001", "clinic.patient.allergy"
        )

        if missing:
            raise UserError(
                _("MASTER PROMPT 13 historical preflight failed: %s")
                % "; ".join(missing)
            )

    def _nurse_users(self, ctx):
        keys = ["DEMO-USER-NUR-001"]
        if ctx.profile in {"standard", "full_enterprise"}:
            keys.append("DEMO-USER-NUR-002")
        return [
            ctx.reference_service.resolve(ctx.run, key, "res.users")
            for key in keys
        ]

    @staticmethod
    def _vital_values(ctx, patient_key, event_index):
        seed = ctx.seed_service
        namespace = f"prompt13.vitals.{patient_key}.{event_index:03d}"
        systolic = 112 + seed.stable_int(namespace + ".sys", 13)
        diastolic = 70 + seed.stable_int(namespace + ".dia", 10)

        # Keep values presentation-realistic but deliberately non-diagnostic.
        if patient_key == "DEMO-PAT-CHRON-001":
            systolic += 10
            diastolic += 5
        elif patient_key == "DEMO-PAT-ELDER-001":
            systolic += 5

        return {
            "bp_systolic": float(systolic),
            "bp_diastolic": float(diastolic),
            "heart_rate": float(66 + seed.stable_int(namespace + ".hr", 18)),
            "respiratory_rate": float(14 + seed.stable_int(namespace + ".rr", 5)),
            "temperature_c": 36.3 + (seed.stable_int(namespace + ".temp", 6) / 10.0),
            "spo2": float(97 + seed.stable_int(namespace + ".spo2", 3)),
            "blood_glucose_mgdl": float(88 + seed.stable_int(namespace + ".glu", 24)),
            "pain_scale": int(seed.stable_int(namespace + ".pain", 4)),
        }

    def _generate_vitals(self, ctx, counters, timeline):
        patient_count = PROFILE_HISTORY_PATIENT_COUNTS[ctx.profile]
        patients = [
            (
                key,
                ctx.reference_service.resolve(ctx.run, key, "clinic.patient"),
            )
            for key in HISTORY_PATIENT_KEYS[:patient_count]
        ]
        nurses = self._nurse_users(ctx)
        monitor = ctx.reference_service.resolve(
            ctx.run, "DEMO-DEVICE-MON-01", "clinic.device"
        )
        dates = timeline.historical_dates(ctx.profile)

        for index, business_date in enumerate(dates, 1):
            patient_key, patient = patients[(index - 1) % len(patients)]
            nurse = nurses[(index - 1) % len(nurses)]
            measured_datetime = timeline.local_to_utc(
                business_date,
                f"prompt13.vital.datetime.{index:03d}",
                hour_from=8,
                hour_to=15,
            )
            values = {
                "patient_id": patient.id,
                "measured_datetime": measured_datetime,
                "measured_by": nurse.id,
                "device_name": monitor.name,
                "device_serial": monitor.serial_no,
                "device_type": "monitor",
                "notes": (
                    "Synthetic longitudinal vital observation generated by "
                    "ClinicOne MASTER PROMPT 13; presentation data only."
                ),
            }
            values.update(self._vital_values(ctx, patient_key, index))
            self._ensure(
                ctx, counters,
                f"DEMO-HIST-VITAL-{index:03d}",
                "clinic.patient.vital",
                values,
                reset_sequence=1030,
            )

    def _generate_condition_episodes(self, ctx, counters, timeline):
        condition = ctx.reference_service.resolve(
            ctx.run, "DEMO-PATCOND-CHRON-001", "clinic.patient.condition"
        )
        count = PROFILE_CONDITION_EPISODES[ctx.profile]
        for index, days_ago in enumerate(CONDITION_EPISODE_DAYS[:count], 1):
            event_dt = timeline.fixed_historical_datetime(
                days_ago,
                f"prompt13.condition.{index:03d}",
                hour_from=9,
                hour_to=14,
            )
            severity = "moderate" if index in {2, count} else "mild"
            outcome = "improved" if index % 2 else "unchanged"
            self._ensure(
                ctx, counters,
                f"DEMO-HIST-COND-EP-{index:03d}",
                "clinic.patient.condition.episode",
                {
                    "condition_id": condition.id,
                    "episode_datetime": event_dt,
                    "description": (
                        "Synthetic demo longitudinal episode used to demonstrate "
                        "patient-history continuity; not a clinical diagnosis."
                    ),
                    "severity": severity,
                    "outcome": outcome,
                },
                reset_sequence=1040,
            )

    def _generate_allergy_reaction(self, ctx, counters, timeline):
        allergy = ctx.reference_service.resolve(
            ctx.run, "DEMO-PATALLERGY-EMAR-001", "clinic.patient.allergy"
        )
        recorder = ctx.reference_service.resolve(
            ctx.run, "DEMO-USER-NUR-001", "res.users"
        )
        onset = timeline.fixed_historical_datetime(
            300, "prompt13.allergy.onset", hour_from=10, hour_to=13
        )
        recorded = timeline.fixed_historical_datetime(
            299, "prompt13.allergy.recorded", hour_from=8, hour_to=11
        )
        self._ensure(
            ctx, counters,
            "DEMO-HIST-ALLERGY-REACTION-001",
            "clinic.patient.allergy.reaction",
            {
                "allergy_id": allergy.id,
                "reaction_text": "Synthetic demo prior rash",
                "description": (
                    "Synthetic recovered allergy-reaction history for medication "
                    "safety presentation only."
                ),
                "severity": "mild",
                "onset_datetime": onset,
                "recorded_date": recorded,
                "recorded_by": recorder.id,
                "exposure_route": "ingestion",
                "outcome": "recovered",
            },
            reset_sequence=1050,
        )

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        counters = self._counters()
        timeline = self._timeline(ctx)
        self._generate_vitals(ctx, counters, timeline)
        self._generate_condition_episodes(ctx, counters, timeline)
        self._generate_allergy_reaction(ctx, counters, timeline)
        return counters

    def validate(self, ctx, scenario):
        failures = []
        timeline = self._timeline(ctx)
        expected_vitals = PROFILE_HISTORY_BUDGETS[ctx.profile]
        vital_refs = ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id),
            ("generator_key", "=", self.key),
            ("model_name", "=", "clinic.patient.vital"),
            ("record_status", "=", "bound"),
        ])
        vitals = ctx.env["clinic.patient.vital"].browse(
            vital_refs.mapped("res_id")
        ).exists()
        if len(vitals) != expected_vitals:
            failures.append(
                f"Expected {expected_vitals} Prompt-13 vital history rows, found {len(vitals)}."
            )

        if vitals.filtered(lambda row: fields.Datetime.to_datetime(row.measured_datetime).date() >= timeline.anchor_date):
            failures.append("Prompt-13 historical vitals contain T0/future business dates.")

        actual_buckets = {
            bucket.key
            for row in vitals
            for bucket in [timeline.bucket_for(row.measured_datetime.date())]
            if bucket
        }
        required_buckets = {bucket.key for bucket in HISTORICAL_BUCKETS}
        if not required_buckets <= actual_buckets:
            failures.append(
                "Historical vital coverage is missing buckets: "
                + ", ".join(sorted(required_buckets - actual_buckets))
            )

        patient_ids = set(vitals.mapped("patient_id").ids)
        expected_patient_count = PROFILE_HISTORY_PATIENT_COUNTS[ctx.profile]
        if len(patient_ids) != expected_patient_count:
            failures.append(
                f"Expected longitudinal vitals across {expected_patient_count} patients, "
                f"found {len(patient_ids)}."
            )

        episode_refs = ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id),
            ("generator_key", "=", self.key),
            ("model_name", "=", "clinic.patient.condition.episode"),
            ("record_status", "=", "bound"),
        ])
        expected_episodes = PROFILE_CONDITION_EPISODES[ctx.profile]
        if len(episode_refs) != expected_episodes:
            failures.append(
                f"Expected {expected_episodes} chronic-condition episodes, "
                f"found {len(episode_refs)}."
            )

        reaction = ctx.reference_service.resolve(
            ctx.run,
            "DEMO-HIST-ALLERGY-REACTION-001",
            "clinic.patient.allergy.reaction",
        )
        if not reaction.onset_datetime or reaction.onset_datetime.date() >= timeline.anchor_date:
            failures.append("Historical allergy reaction is not strictly before Demo Anchor Date.")

        if failures:
            raise UserError(
                _("MASTER PROMPT 13 validation failed:\n%s")
                % "\n".join(f"- {item}" for item in failures)
            )
        return []

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return True
























