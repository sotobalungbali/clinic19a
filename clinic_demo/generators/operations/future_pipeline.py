"""MASTER PROMPT 20 — deterministic 90-day future pipeline."""

from datetime import datetime, time, timedelta

import pytz
from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_CANCEL_THEN_DELETE
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.journey_read_context import actor_key, read_model


PIPELINE_OFFSETS = (1, 7, 14, 30, 60, 90)
PIPELINE_CONTRACTS = {
    "booking.booking": {"start_datetime", "end_datetime", "state", "room_id", "doctor_id"},
    "clinic.care.plan.line": {"expected_date", "scheduled_datetime", "state", "plan_id"},
    "clinic.postcare.plan": {"expected_end_date", "state", "task_ids"},
    "clinic.postcare.task": {"plan_id", "reference", "due_datetime", "state", "auto_send",
        "company_id", "assignee_id", "channel", "completed_at", "sent_at",
        "contacted_at", "send_count", "escalate_if_overdue"},
    "clinic.telemedicine.session": {"scheduled_start", "scheduled_end", "state"},
}
PIPELINE_RELATIONS = {
    ("clinic.postcare.task", "plan_id"): "clinic.postcare.plan",
    ("clinic.care.plan.line", "plan_id"): "clinic.care.plan",
}


@GENERATOR_REGISTRY.register
class FuturePipelineGenerator(BaseDemoGenerator):
    """Consolidate source-owned future work without duplicating its ownership."""

    key = "operations.future_pipeline"
    phase = "20_pipeline"
    sequence = 900
    depends_on = ("digital.ecommerce_marketing_portal", "operations.booking", "clinical.telemedicine")
    scenario_keys = ("SCN-PIPELINE-01",)
    owned_models = ("clinic.postcare.task",)
    required_groups = ("clinic_post_care_followup.group_postcare_manager",)

    @staticmethod
    def _counts():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _actor(record, user, ctx):
        return record.with_user(user).with_company(ctx.run.company_id).with_context(
            allowed_company_ids=[ctx.run.company_id.id], prefetch_fields=False,
        )

    @staticmethod
    def _utc(ctx, offset, hour=9):
        zone = pytz.timezone(ctx.run.timezone or "UTC")
        local = zone.localize(datetime.combine(ctx.run.anchor_date + timedelta(days=offset), time(hour=hour)))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _resolve(self, ctx, key, model, missing_ok=False, user=None):
        if user is None:
            reference = ctx.reference_service._reference(ctx.run, key)
            if reference and actor_key(reference):
                user = read_model(ctx.run, reference).env.user
        record = ctx.reference_service.resolve(ctx.run, key, model, missing_ok=missing_ok, record_user=user)
        if not record:
            return record
        if user:
            return self._actor(record, user, ctx)
        return record.with_company(ctx.run.company_id).with_context(
            allowed_company_ids=[ctx.run.company_id.id], prefetch_fields=False,
        )

    def _whole_path_preflight(self, ctx):
        issues = []
        for model_name, required_fields in PIPELINE_CONTRACTS.items():
            missing = sorted(required_fields - set(ctx.env[model_name]._fields))
            if missing:
                issues.append(f"{model_name} missing fields: {', '.join(missing)}")
        for (model_name, field_name), expected in PIPELINE_RELATIONS.items():
            field = ctx.env[model_name]._fields.get(field_name)
            actual = getattr(field, "comodel_name", None) if field else None
            if actual != expected:
                issues.append(f"{model_name}.{field_name} comodel is {actual or 'missing'}, expected {expected}")

        prerequisites = (
            ("DEMO-USER-MGR", "res.users"),
            ("DEMO-STAFF-MGR", "clinic.staff"),
            ("DEMO-POSTCARE-PLAN-001", "clinic.postcare.plan"),
            ("DEMO-CARE-PLAN-001", "clinic.care.plan"),
            ("DEMO-TELE-SESSION-001", "clinic.telemedicine.session"),
            ("DEMO-FUT-BOOK-001", "booking.booking"),
        )
        found = {}
        for key, model in prerequisites:
            found[key] = self._resolve(ctx, key, model, missing_ok=True)
            if not found[key]:
                issues.append(f"required provenance reference {key} ({model}) is missing")

        manager = found.get("DEMO-USER-MGR")
        if manager:
            Task = self._actor(ctx.env["clinic.postcare.task"].browse(), manager, ctx)
            for mode in ("read", "create", "write"):
                try:
                    Task.check_access(mode)
                except Exception as error:
                    issues.append(f"DEMO-USER-MGR cannot {mode} clinic.postcare.task: {error}")
        if found.get("DEMO-POSTCARE-PLAN-001") and found["DEMO-POSTCARE-PLAN-001"].company_id != ctx.run.company_id:
            issues.append("DEMO-POSTCARE-PLAN-001 belongs to another company")
        if found.get("DEMO-POSTCARE-PLAN-001") and found.get("DEMO-STAFF-MGR"):
            for offset in PIPELINE_OFFSETS:
                task = self._resolve(ctx, f"DEMO-FUT-FOLLOWUP-{offset:03d}", "clinic.postcare.task", True, manager)
                if task:
                    issues.extend(self._followup_issues(ctx, task, offset,
                        found["DEMO-POSTCARE-PLAN-001"], found["DEMO-STAFF-MGR"]))
        if issues:
            raise UserError(_("MASTER PROMPT 20 whole-path runtime preflight failed: %s") % "; ".join(issues))
        return found

    def _followup_issues(self, ctx, task, offset, plan, staff):
        """Anchor-relative open work; owner cron may age pending work into due.

        Due is an undelivered work state, not proof of contact or completion.
        Never move the anchor, rewrite workflow state, or erase delivery evidence.
        """
        key = f"DEMO-FUT-FOLLOWUP-{offset:03d}"
        if not task:
            return [f"{key}: missing follow-up"]
        issues = []
        if task.state not in {"pending", "scheduled", "due"}:
            issues.append(f"{key}: expected open undelivered work, found {task.state}")
        if task.completed_at or task.sent_at or task.contacted_at or task.send_count:
            issues.append(f"{key}: contact/delivery/completion evidence is present")
        if task.due_datetime != self._utc(ctx, offset):
            issues.append(f"{key}: expected UTC deadline {self._utc(ctx, offset)}, found {task.due_datetime}")
        if (task.reference != key or task.plan_id != plan or task.assignee_id != staff
                or task.company_id != ctx.run.company_id):
            issues.append(f"{key}: identity/plan/assignee/company contract mismatch")
        if task.channel != "internal" or task.auto_send or task.escalate_if_overdue:
            issues.append(f"{key}: internal-only non-escalating follow-up contract mismatch")
        return issues

    def _ensure_followup(self, ctx, counts, plan, staff, manager, offset):
        key = f"DEMO-FUT-FOLLOWUP-{offset:03d}"
        values = {
            "reference": key,
            "name": f"Synthetic T+{offset} follow-up",
            "plan_id": plan.id,
            "assignee_id": staff.id,
            "task_type": "review" if offset in (30, 90) else "checkin",
            "channel": "internal",
            "priority": "0",
            "due_datetime": self._utc(ctx, offset),
            "response_required": False,
            "auto_send": False,
            "instruction_html": f"<p>Synthetic deterministic T+{offset} follow-up; no outbound delivery.</p>",
            "escalate_if_overdue": False,
        }
        Model = self._actor(ctx.env["clinic.postcare.task"], manager, ctx)
        record, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name="clinic.postcare.task",
            generator_key=self.key, scenario_key="SCN-PIPELINE-01",
            create_callback=lambda: Model.create(values), update_callback=None,
            reset_policy=RESET_CANCEL_THEN_DELETE, reset_sequence=1200 + offset,
            record_user=manager,
        )
        counts[status if status in counts else "created"] += 1
        return record

    def generate(self, ctx, scenario):
        counts = self._counts()
        found = self._whole_path_preflight(ctx)
        manager = found["DEMO-USER-MGR"]
        staff = self._resolve(ctx, "DEMO-STAFF-MGR", "clinic.staff", user=manager)
        plan = self._resolve(ctx, "DEMO-POSTCARE-PLAN-001", "clinic.postcare.plan", user=manager)
        for offset in PIPELINE_OFFSETS:
            self._ensure_followup(ctx, counts, plan, staff, manager, offset)
        return counts

    def validate(self, ctx, scenario):
        issues = []
        anchor = ctx.run.anchor_date
        plan = self._resolve(ctx, "DEMO-POSTCARE-PLAN-001", "clinic.postcare.plan", True)
        staff = self._resolve(ctx, "DEMO-STAFF-MGR", "clinic.staff", True)
        for offset in PIPELINE_OFFSETS:
            task = self._resolve(ctx, f"DEMO-FUT-FOLLOWUP-{offset:03d}", "clinic.postcare.task", True)
            issues.extend(self._followup_issues(ctx, task, offset, plan, staff))
        bookings = [self._resolve(ctx, f"DEMO-FUT-BOOK-{index:03d}", "booking.booking", True) for index in range(1, 13)]
        if not any(item and item.start_datetime.date() > anchor and item.state not in {"done", "cancelled"} for item in bookings):
            issues.append("The source-owned future Booking workload is missing")
        tele = self._resolve(ctx, "DEMO-TELE-SESSION-001", "clinic.telemedicine.session", True)
        if not tele or tele.scheduled_start.date() <= anchor or tele.state not in {"scheduled", "ready"}:
            issues.append("The future Telemedicine workload anchor is missing")
        care = self._resolve(ctx, "DEMO-CARE-PLAN-001", "clinic.care.plan", True)
        if not care or not care.line_ids.filtered(lambda line: line.expected_date and line.expected_date > anchor and line.state not in {"done", "cancelled", "skipped"}):
            issues.append("The recurring Care Plan has no future pending activity")
        return issues

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}



















