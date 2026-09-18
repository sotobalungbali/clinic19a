"""MASTER PROMPT 19 — deterministic exception, quality and safe integration evidence."""

import json
from datetime import datetime, time

from odoo import Command, _
from odoo.exceptions import UserError

from .base import BaseDemoGenerator
from ..services.constants import RESET_FRESH_DB_ONLY
from ..services.generator_registry import GENERATOR_REGISTRY


GROUPS = (
    "clinic_feedback.group_feedback_manager",
    "clinic_quality.group_quality_manager",
    "clinic_incident_event.group_incident_manager",
    "clinic_integration_api.group_api_manager",
)

CONTRACTS = {
    "clinic.feedback.survey": ({"name", "code", "company_id", "state", "title"}, {"action_activate"}),
    "clinic.feedback": ({"name", "company_id", "branch_id", "survey_id", "patient_id",
                          "feedback_type", "overall_rating", "nps_score", "comment", "state"},
                         {"action_submit", "action_escalate"}),
    "clinic.feedback.escalation": ({"feedback_id", "severity", "reason", "state"}, set()),
    "clinic.quality.check.template": ({"name", "code", "company_id", "branch_ids", "state",
                                        "scope_type", "target_score", "line_ids"}, {"action_activate"}),
    "clinic.quality.check.template.line": ({"template_id", "control_code", "requirement",
                                             "critical", "weight"}, set()),
    "clinic.quality.check": ({"name", "title", "template_id", "company_id", "branch_id",
                               "state", "line_ids", "overall_result"},
                              {"action_start", "action_submit_review"}),
    "clinic.quality.check.line": ({"check_id", "control_code", "result", "evidence_note"}, set()),
    "clinic.incident.category": ({"name", "code", "company_id", "incident_type",
                                   "requires_investigation", "requires_capa"}, set()),
    "clinic.incident": ({"name", "title", "company_id", "branch_id", "category_id", "state",
                          "quality_check_id", "quality_check_line_id", "description"},
                         {"action_report", "action_start_triage", "action_review_reportability",
                          "action_start_investigation"}),
    "clinic.api.event.type": ({"name", "code", "active"}, set()),
    "clinic.api.event": ({"name", "company_id", "branch_id", "event_type_id", "model_name",
                           "res_id", "state", "payload_json", "error_message"}, set()),
}


class ExceptionBase(BaseDemoGenerator):
    required_groups = ("base.group_user",)

    @staticmethod
    def _counts():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    def _resolve(self, ctx, key, model, missing_ok=False, user=None):
        return ctx.reference_service.resolve(
            ctx.run, key, model, missing_ok=missing_ok, record_user=user,
        )

    @staticmethod
    def _actor(record, user, ctx, branch=False):
        values = {
            "allowed_company_ids": [ctx.run.company_id.id],
            "allowed_branch_ids": user.allowed_branch_ids.ids,
        }
        if branch:
            values["branch_id"] = branch.id
        return record.with_user(user).with_company(ctx.run.company_id).with_context(**values)

    def _prepare(self, ctx):
        user = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        branch = self._resolve(ctx, "DEMO-BRANCH-001", "clinic.branch")
        patient = self._resolve(ctx, "DEMO-PAT-RET-001", "clinic.patient", missing_ok=True, user=user)
        if not patient:
            patient = self._resolve(ctx, "DEMO-PAT-NEW-001", "clinic.patient", user=user)
        missing_branch = branch - user.allowed_branch_ids
        if missing_branch:
            user.write({"allowed_branch_ids": [Command.link(branch.id)]})
        groups = ctx.env["res.groups"]
        for xmlid in GROUPS:
            groups |= ctx.env.ref(xmlid)
        missing = groups - user.group_ids
        if missing:
            user.write({"group_ids": [Command.link(group.id) for group in missing]})

        issues = []
        for model_name, (fields, methods) in CONTRACTS.items():
            Model = ctx.env[model_name]
            absent = sorted(fields - set(Model._fields))
            absent_methods = sorted(name for name in methods if not hasattr(Model, name))
            if absent:
                issues.append(f"{model_name} missing fields: {', '.join(absent)}")
            if absent_methods:
                issues.append(f"{model_name} missing methods: {', '.join(absent_methods)}")
        relations = {
            ("clinic.feedback", "survey_id"): "clinic.feedback.survey",
            ("clinic.feedback.escalation", "feedback_id"): "clinic.feedback",
            ("clinic.quality.check", "template_id"): "clinic.quality.check.template",
            ("clinic.quality.check.line", "check_id"): "clinic.quality.check",
            ("clinic.incident", "quality_check_id"): "clinic.quality.check",
            ("clinic.incident", "quality_check_line_id"): "clinic.quality.check.line",
            ("clinic.api.event", "event_type_id"): "clinic.api.event.type",
        }
        for (model, field), expected in relations.items():
            actual = getattr(ctx.env[model]._fields.get(field), "comodel_name", None)
            if actual != expected:
                issues.append(f"{model}.{field} comodel is {actual or 'missing'}, expected {expected}")
        for model in CONTRACTS:
            for operation in (("read", "create", "write") if model != "clinic.api.event.type" else ("read", "create")):
                try:
                    self._actor(ctx.env[model], user, ctx, branch).browse().check_access(operation)
                except Exception as error:
                    issues.append(f"DEMO-USER-MGR cannot {operation} {model}: {error}")
        if not ctx.run.safe_mode:
            issues.append("MASTER PROMPT 19 requires Demo Safe Mode for synthetic integration evidence")
        if issues:
            raise UserError(_("MASTER PROMPT 19 whole-path runtime preflight failed: %s") % "; ".join(issues))
        return user, branch, patient

    def _bind(self, ctx, counts, key, record, scenario, sequence, user):
        existing = self._resolve(ctx, key, record._name, missing_ok=True, user=user)
        if existing:
            counts["reused"] += 1
            return existing
        ctx.reference_service.bind(
            ctx.run, key, record, self.key, scenario_key=scenario,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=sequence, record_user=user,
        )
        counts["created"] += 1
        return record

    def reset(self, ctx, scenario):
        return {"skipped": 1}


@GENERATOR_REGISTRY.register
class FeedbackExceptionGenerator(ExceptionBase):
    key = "exception.feedback"
    phase = "19_exception"
    sequence = 800
    depends_on = ("commercial.ap",)
    scenario_keys = ("SCN-FEEDBACK-01",)
    owned_models = ("clinic.feedback.survey", "clinic.feedback", "clinic.feedback.escalation")

    def generate(self, ctx, scenario):
        counts = self._counts()
        user, branch, patient = self._prepare(ctx)
        survey = self._resolve(ctx, "DEMO-FB-SURVEY-001", "clinic.feedback.survey", True, user)
        if not survey:
            survey = self._actor(ctx.env["clinic.feedback.survey"], user, ctx, branch).create({
                "name": "Demo Service Recovery Survey", "code": "DEMO-FB-SURVEY-001",
                "company_id": ctx.run.company_id.id, "branch_id": branch.id,
                "title": "ClinicOne Demo Patient Experience", "survey_type": "satisfaction",
            })
            survey.action_activate()
            self._bind(ctx, counts, "DEMO-FB-SURVEY-001", survey, scenario.key, 1100, user)
        else:
            counts["reused"] += 1
        feedback = self._resolve(ctx, "DEMO-FB-001", "clinic.feedback", True, user)
        if not feedback:
            feedback = self._actor(ctx.env["clinic.feedback"], user, ctx, branch).create({
                "name": "DEMO-FB-001", "company_id": ctx.run.company_id.id, "branch_id": branch.id,
                "survey_id": survey.id, "patient_id": patient.partner_id.id,
                "patient_card_id": patient.id, "feedback_type": "complaint",
                "overall_rating": 2, "nps_score": 4, "would_recommend": "no",
                "comment": "Controlled demo complaint: excessive waiting time; service recovery required.",
            })
            feedback.action_submit()
            feedback.action_escalate()
            self._bind(ctx, counts, "DEMO-FB-001", feedback, scenario.key, 1110, user)
        else:
            counts["reused"] += 1
        escalation = feedback.escalation_ids.filtered(lambda item: item.state not in ("resolved", "cancelled"))[:1]
        if escalation:
            self._bind(ctx, counts, "DEMO-FB-ESC-001", escalation, scenario.key, 1120, user)
        return counts

    def validate(self, ctx, scenario):
        user = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        rec = self._resolve(ctx, "DEMO-FB-001", "clinic.feedback", True, user)
        return [] if rec and rec.state == "escalated" and rec.open_escalation_count else ["DEMO-FB-001 is not an open service-recovery exception"]


@GENERATOR_REGISTRY.register
class IncidentQualityGenerator(ExceptionBase):
    key = "exception.incident_quality"
    phase = "19_exception"
    sequence = 810
    depends_on = ("exception.feedback",)
    scenario_keys = ("SCN-INCIDENT-01", "SCN-QUALITY-01")
    owned_models = ("clinic.quality.check.template", "clinic.quality.check", "clinic.incident")

    def generate(self, ctx, scenario):
        counts = self._counts()
        user, branch, _patient = self._prepare(ctx)
        template = self._resolve(ctx, "DEMO-QUAL-TPL-001", "clinic.quality.check.template", True, user)
        if not template:
            template = self._actor(ctx.env["clinic.quality.check.template"], user, ctx, branch).create({
                "name": "Demo Patient Handover Control", "code": "DEMO-QUAL-TPL-001",
                "company_id": ctx.run.company_id.id, "branch_ids": [Command.set([branch.id])],
                "scope_type": "branch", "target_score": 100.0,
                "failure_incident_type": "operational", "require_evidence_on_failure": True,
                "line_ids": [Command.create({"control_code": "DEMO-HANDOVER-01",
                    "requirement": "Documented clinical handover must be completed before transfer.",
                    "critical": True, "weight": 1.0, "evidence_required": True})],
            })
            template.action_activate()
            self._bind(ctx, counts, "DEMO-QUAL-TPL-001", template, scenario.key, 1130, user)
        else:
            counts["reused"] += 1
        check = self._resolve(ctx, "DEMO-QUAL-001", "clinic.quality.check", True, user)
        if not check:
            check = self._actor(ctx.env["clinic.quality.check"], user, ctx, branch).create({
                "name": "DEMO-QUAL-001", "title": "Controlled Handover Nonconformity",
                "template_id": template.id, "branch_id": branch.id, "scope_type": "branch",
                "planned_date": ctx.run.anchor_date, "performed_by_user_id": user.id,
                "reviewed_by_user_id": user.id,
            })
            check.action_start()
            check.line_ids.write({"result": "fail", "evidence_note": "Required handover evidence was absent in the controlled demo case."})
            check.write({"review_summary": "Nonconformity retained for management visibility and corrective action."})
            check.action_submit_review()
            self._bind(ctx, counts, "DEMO-QUAL-001", check, scenario.key, 1140, user)
        else:
            counts["reused"] += 1
        line = check.line_ids.filtered(lambda item: item.result == "fail")[:1]
        incident = self._resolve(ctx, "DEMO-INC-001", "clinic.incident", True, user)
        if not incident:
            category = self._actor(ctx.env["clinic.incident.category"], user, ctx, branch).search([
                ("code", "=", "DEMO-QUAL-INC"), ("company_id", "=", ctx.run.company_id.id),
            ], limit=1)
            if not category:
                category = self._actor(ctx.env["clinic.incident.category"], user, ctx, branch).create({
                    "name": "Demo Quality Nonconformity", "code": "DEMO-QUAL-INC",
                    "company_id": ctx.run.company_id.id, "incident_type": "operational",
                    "default_severity": "high", "requires_investigation": True,
                    "requires_capa": True, "requires_regulatory_review": False,
                })
            incident = self._actor(ctx.env["clinic.incident"], user, ctx, branch).create({
                "name": "DEMO-INC-001", "title": "Quality Check Handover Failure",
                "company_id": ctx.run.company_id.id,
                "branch_id": branch.id if ctx.run.company_id.policy_branch_scope_incident_event else False,
                "category_id": category.id, "classification": "operational", "severity": "high",
                "harm_level": "none", "recurrence_risk": "medium",
                "occurred_at": datetime.combine(ctx.run.anchor_date, time(hour=10)),
                "case_owner_id": user.id,
                "quality_check_id": check.id, "quality_check_line_id": line.id,
                "description": "<p>Controlled quality exception; no patient harm and no external side effect.</p>",
                "immediate_action": "Handover paused and supervisor notified.",
            })
            incident.action_report(); incident.action_start_triage()
            incident.action_review_reportability(); incident.action_start_investigation()
            self._bind(ctx, counts, "DEMO-INC-001", incident, scenario.key, 1150, user)
        else:
            counts["reused"] += 1
        return counts

    def validate(self, ctx, scenario):
        user = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        check = self._resolve(ctx, "DEMO-QUAL-001", "clinic.quality.check", True, user)
        incident = self._resolve(ctx, "DEMO-INC-001", "clinic.incident", True, user)
        return [] if check and check.state == "review" and check.fail_count and incident and incident.state == "investigation" else ["Prompt-19 quality/incident journey is incomplete"]


@GENERATOR_REGISTRY.register
class SafeDigitalFailureGenerator(ExceptionBase):
    key = "digital.ecommerce_marketing_portal"
    phase = "19_exception"
    sequence = 820
    depends_on = ("exception.incident_quality",)
    scenario_keys = ("SCN-API-01",)
    owned_models = ("clinic.api.event.type", "clinic.api.event")

    def generate(self, ctx, scenario):
        counts = self._counts()
        user, branch, patient = self._prepare(ctx)
        event_type = self._actor(ctx.env["clinic.api.event.type"], user, ctx).search([("code", "=", "DEMO.SAFE.FAILURE")], limit=1)
        if not event_type:
            event_type = self._actor(ctx.env["clinic.api.event.type"], user, ctx).create({
                "name": "Demo Safe Simulated Failure", "code": "DEMO.SAFE.FAILURE",
                "description": "Synthetic evidence only; no webhook or external API is invoked.",
            })
        event = self._resolve(ctx, "DEMO-API-001", "clinic.api.event", True, user)
        if not event:
            event = self._actor(ctx.env["clinic.api.event"], user, ctx, branch).create({
                "name": "DEMO-API-001", "company_id": ctx.run.company_id.id, "branch_id": branch.id,
                "event_type_id": event_type.id, "model_name": "clinic.patient", "res_id": patient.id,
                "state": "failed", "payload_json": json.dumps({"demo_key": "DEMO-API-001", "synthetic": True}, sort_keys=True),
                "available_at": datetime.combine(ctx.run.anchor_date, time(hour=11)),
                "error_message": "Synthetic timeout evidence generated under Demo Safe Mode; no outbound request attempted.",
            })
            self._bind(ctx, counts, "DEMO-API-001", event, scenario.key, 1160, user)
        else:
            counts["reused"] += 1
        return counts

    def validate(self, ctx, scenario):
        user = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        event = self._resolve(ctx, "DEMO-API-001", "clinic.api.event", True, user)
        return [] if ctx.run.safe_mode and event and event.state == "failed" and event.attempt_count == 0 and not event.delivery_ids else ["DEMO-API-001 is not isolated synthetic failure evidence"]




















