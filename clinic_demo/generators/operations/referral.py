




"""MASTER PROMPT 14 — Referral acquisition and conversion-ready front-office dataset."""

from datetime import timedelta

from odoo import _, Command, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_CANCEL_THEN_DELETE, RESET_DEACTIVATE, RESET_DELETE_SAFE, RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.historical_service import HistoricalTimelineService

PROFILE_REFERRAL_COUNTS = {"compact": 5, "standard": 7, "full_enterprise": 10}
GOLDEN_REFERRAL_KEY = "DEMO-REF-001"

REFERRAL_SPECS = (
    ("001", "DEMO-PAT-REF-001", "confirmed", 0, "SCN-REFERRAL-01"),
    ("HIST-001", "DEMO-PAT-RET-001", "converted", 330, "SCN-REFERRAL-01"),
    ("HIST-002", "DEMO-PAT-FREQ-001", "converted", 180, "SCN-REFERRAL-01"),
    ("EXC-CANCEL-001", "DEMO-PAT-NOSHOW-001", "cancelled", 28, "SCN-REFERRAL-02"),
    ("EXC-EXPIRED-001", "DEMO-PAT-VIP-001", "expired", 45, "SCN-REFERRAL-02"),
    ("HIST-003", "DEMO-PAT-PKG-001", "converted", 90, "SCN-REFERRAL-01"),
    ("CUR-001", "DEMO-PAT-NEW-001", "draft", 0, "SCN-REFERRAL-02"),
    ("HIST-004", "DEMO-PAT-INS-001", "converted", 60, "SCN-REFERRAL-01"),
    ("CUR-002", "DEMO-PAT-MEM-001", "confirmed", 0, "SCN-REFERRAL-02"),
    ("HIST-005", "DEMO-PAT-TELE-001", "converted", 14, "SCN-REFERRAL-01"),
)


@GENERATOR_REGISTRY.register
class ReferralOperationsGenerator(BaseDemoGenerator):
    key = "operations.referral"
    phase = "14_frontoffice"
    sequence = 600
    depends_on = ("history.patient_longitudinal",)
    scenario_keys = ("SCN-REFERRAL-01", "SCN-REFERRAL-02")
    owned_models = ("clinic.referral.program", "clinic.referral.source", "clinic.referral")
    required_groups = ("clinic_referral.group_referral_manager",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _manager(self, ctx):
        manager = ctx.reference_service.resolve(ctx.run, "DEMO-USER-MGR", "res.users")
        group = ctx.env.ref("clinic_referral.group_referral_manager", raise_if_not_found=False)
        if not group:
            raise UserError(_("Referral Manager security group is missing."))
        if group not in manager.group_ids:
            manager.write({"group_ids": [Command.link(group.id)]})
        return manager

    def _ensure(self, ctx, counters, actor, key, model, values, policy, reset_sequence, scenario, update=True):
        Model = ctx.env[model].with_user(actor).with_company(ctx.run.company_id)
        def create():
            return Model.create(dict(values))
        def update_record(record):
            record.write(dict(values))
        record, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name=model, generator_key=self.key,
            scenario_key=scenario, create_callback=create,
            update_callback=update_record if update else None,
            reset_policy=policy, reset_sequence=reset_sequence, record_user=actor,
        )
        self._bump(counters, status)
        return record

    def _preflight(self, ctx, actor):
        requirements = {
            "clinic.referral.program": {"name", "code", "state", "start_date", "allowed_branch_ids"},
            "clinic.referral.source": {"name", "code", "category", "referrer_type", "default_program_id"},
            "clinic.referral": {"patient_id", "target_doctor_id", "program_id", "source_id", "date_referral", "date_received", "date_converted", "date_cancelled", "valid_until", "state"},
        }
        missing = []
        for model, fields_required in requirements.items():
            if model not in ctx.env:
                missing.append(f"missing model {model}")
                continue
            absent = sorted(fields_required - set(ctx.env[model]._fields))
            if absent:
                missing.append(f"{model} missing fields {', '.join(absent)}")
            try:
                ctx.env[model].with_user(actor).browse().check_access("create")
            except Exception as exc:
                missing.append(f"{model} create access failed: {exc}")
        for code in ("clinic.referral", "clinic.referral.program", "clinic.referral.source"):
            if not ctx.env["ir.sequence"].search_count([("code", "=", code), ("company_id", "in", [False, ctx.run.company_id.id])]):
                missing.append(f"missing sequence {code}")
        for key in ("DEMO-PAT-REF-001", "DEMO-PAT-RET-001", "DEMO-DOC-001", "DEMO-BRANCH-001"):
            expected = "clinic.doctor" if key.startswith("DEMO-DOC") else "clinic.branch" if key.startswith("DEMO-BRANCH") else "clinic.patient"
            ctx.reference_service.resolve(ctx.run, key, expected)
        if missing:
            raise UserError(_("MASTER PROMPT 14 referral preflight failed: %s") % "; ".join(missing))

    def _masters(self, ctx, counters, actor):
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        branches = [ctx.reference_service.resolve(ctx.run, f"DEMO-BRANCH-{i:03d}", "clinic.branch") for i in range(1, {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile] + 1)]
        program = self._ensure(ctx, counters, actor, "DEMO-REF-PROGRAM-001", "clinic.referral.program", {
            "name": "ClinicOne Demo Patient Referral Program", "code": "DEMO-REF-PROGRAM-001",
            "active": True, "company_id": ctx.run.company_id.id, "user_id": actor.id,
            "allowed_branch_ids": [Command.set([b.id for b in branches])],
            "start_date": anchor - timedelta(days=365), "end_date": False,
            "patient_scope": "any", "reward_policy": "none", "apply_on_booking": True,
            "integration_notes": "Synthetic Prompt-14 acquisition program; no financial reward is executed.",
        }, RESET_DEACTIVATE, 720, "SCN-REFERRAL-01")
        if program.state != "running":
            if program.state == "paused":
                program.action_set_draft()
            if program.state == "draft":
                program.action_start()
        doctor = ctx.reference_service.resolve(ctx.run, "DEMO-DOC-001", "clinic.doctor")
        source_internal = self._ensure(ctx, counters, actor, "DEMO-REF-SOURCE-DOCTOR", "clinic.referral.source", {
            "name": "Demo Internal Doctor Network", "code": "DEMO-REF-SRC-DOC", "active": True,
            "sequence": 10, "company_id": ctx.run.company_id.id, "category": "internal_doctor",
            "referrer_type": "internal_doctor", "internal_doctor_id": doctor.id,
            "apply_on_booking": True, "default_program_id": program.id, "default_reward_policy": "inherit",
            "integration_notes": "Synthetic internal clinical referral source.",
        }, RESET_DEACTIVATE, 710, "SCN-REFERRAL-01")
        source_patient = self._ensure(ctx, counters, actor, "DEMO-REF-SOURCE-PATIENT", "clinic.referral.source", {
            "name": "Demo Patient Referral", "code": "DEMO-REF-SRC-PAT", "active": True,
            "sequence": 20, "company_id": ctx.run.company_id.id, "category": "patient",
            "referrer_type": "patient", "apply_on_booking": True, "default_program_id": program.id,
            "default_reward_policy": "inherit", "integration_notes": "Synthetic patient-to-patient acquisition source.",
        }, RESET_DEACTIVATE, 710, "SCN-REFERRAL-02")
        source_digital = self._ensure(ctx, counters, actor, "DEMO-REF-SOURCE-DIGITAL", "clinic.referral.source", {
            "name": "Demo Digital Campaign", "code": "DEMO-REF-SRC-DIG", "active": True,
            "sequence": 30, "company_id": ctx.run.company_id.id, "category": "online_ads",
            "referrer_type": "other",
            "apply_on_booking": True, "apply_on_marketing": True, "default_program_id": program.id,
            "default_reward_policy": "inherit", "campaign_name": "ClinicOne Synthetic Acquisition 360",
            "tracking_code": "DEMO-ACQ-360", "integration_notes": "Synthetic digital attribution; no external delivery.",
        }, RESET_DEACTIVATE, 710, "SCN-REFERRAL-02")
        return program, (source_internal, source_patient, source_digital)

    def _doctor_for_patient(self, ctx, patient):
        max_doctors = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        candidates = [ctx.reference_service.resolve(ctx.run, f"DEMO-DOC-{i:03d}", "clinic.doctor") for i in range(1, max_doctors + 1)]
        branch = patient.partner_id.branch_id
        return next((doctor for doctor in candidates if doctor.branch_id == branch), candidates[0])

    @staticmethod
    def _frontoffice_day(anchor):
        # Booking operations are Monday-Saturday. If T0 is Sunday, the live
        # front-office snapshot is the immediately preceding Saturday.
        return anchor - timedelta(days=1) if anchor.weekday() == 6 else anchor

    def generate(self, ctx, scenario):
        counters = self._counters()
        actor = self._manager(ctx)
        self._preflight(ctx, actor)
        program, sources = self._masters(ctx, counters, actor)
        timeline = HistoricalTimelineService(ctx.run, ctx.seed_service)
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        count = PROFILE_REFERRAL_COUNTS[ctx.profile]
        patient_referrer = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-RET-001", "clinic.patient")

        for index, (token, patient_key, target_state, days_ago, scenario_key) in enumerate(REFERRAL_SPECS[:count], 1):
            patient = ctx.reference_service.resolve(ctx.run, patient_key, "clinic.patient")
            doctor = self._doctor_for_patient(ctx, patient)
            source = sources[(index - 1) % len(sources)]
            if days_ago:
                referral_dt = timeline.fixed_historical_datetime(days_ago, f"prompt14.referral.{token}", 9, 14)
            else:
                current_day = self._frontoffice_day(anchor)
                hour_from, hour_to = (8, 9) if token == "001" else (9, 14)
                referral_dt = timeline.local_to_utc(
                    current_day, f"prompt14.referral.{token}", hour_from, hour_to
                )
            valid_until = anchor + timedelta(days=3650) if target_state != "expired" else anchor - timedelta(days=1)
            values = {
                "company_id": ctx.run.company_id.id, "branch_id": patient.partner_id.branch_id.id,
                "user_id": actor.id, "patient_id": patient.id, "target_doctor_id": doctor.id,
                "program_id": program.id, "source_id": source.id, "date_referral": referral_dt,
                "valid_until": valid_until, "clinical_reason": "Synthetic front-office referral acquisition",
                "clinical_notes": "MASTER PROMPT 14 synthetic referral; no real patient data.",
                "referrer_type": source.referrer_type, "reward_policy": "none",
            }
            if source.referrer_type == "patient":
                values["referrer_patient_id"] = patient_referrer.id
            if source.referrer_type == "other":
                values["referrer_free_text"] = "Synthetic digital acquisition campaign"
            demo_key = GOLDEN_REFERRAL_KEY if token == "001" else f"DEMO-REF-{token}"
            reset_policy = (
                RESET_FRESH_DB_ONLY if target_state == "converted"
                else RESET_CANCEL_THEN_DELETE if target_state in {"confirmed", "expired"}
                else RESET_DELETE_SAFE
            )
            referral = self._ensure(ctx, counters, actor, demo_key, "clinic.referral", values,
                reset_policy, 760, scenario_key, update=(target_state in {"draft", "confirmed"}))
            # On a fresh or repaired rerun, use public workflow to reach the target.
            if target_state == "confirmed" and referral.state == "draft":
                referral.action_confirm(effective_datetime=referral_dt + timedelta(hours=1))
            elif target_state == "converted" and referral.state in {"draft", "confirmed"}:
                if referral.state == "draft":
                    referral.action_confirm(effective_datetime=referral_dt + timedelta(hours=1))
                referral.action_convert(effective_datetime=referral_dt + timedelta(hours=2))
            elif target_state == "cancelled" and referral.state in {"draft", "confirmed"}:
                if referral.state == "draft":
                    referral.action_confirm(effective_datetime=referral_dt + timedelta(hours=1))
                referral.action_cancel(effective_datetime=referral_dt + timedelta(hours=2))
            elif target_state == "expired" and referral.state in {"draft", "confirmed"}:
                referral.action_mark_expired(as_of_date=anchor)

        return counters

    def validate(self, ctx, scenario):
        issues = []
        count = PROFILE_REFERRAL_COUNTS[ctx.profile]
        records = []
        for token, _patient, _state, _days, _scenario in REFERRAL_SPECS[:count]:
            record = ctx.reference_service.resolve(ctx.run, f"DEMO-REF-{token}", "clinic.referral", missing_ok=True)
            if record:
                records.append(record)
        if len(records) != count:
            issues.append(f"Prompt-14 referral budget expected {count}, found {len(records)}.")
        states = {record.state for record in records}
        required = {"draft", "confirmed", "converted", "cancelled", "expired"} if count >= 5 else {"draft", "confirmed", "converted"}
        if not required <= states:
            issues.append("Referral lifecycle coverage is incomplete: " + ", ".join(sorted(required - states)))
        return issues
























