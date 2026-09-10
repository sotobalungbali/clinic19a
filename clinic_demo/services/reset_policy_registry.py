




"""Source-driven reset-policy decisions.

Unknown model/state combinations are deliberately blocked instead of falling back
to destructive deletion.
"""

from dataclasses import dataclass

from odoo.exceptions import ValidationError

from .constants import (
    RESET_CANCEL_THEN_DELETE,
    RESET_DELETE_SAFE,
    RESET_DEACTIVATE,
    RESET_FRESH_DB_ONLY,
    RESET_RETAIN_IMMUTABLE,
    RESET_REVERSE_THEN_RETAIN,
)


@dataclass(frozen=True)
class ResetPolicyDecision:
    policy: str
    pre_actions: tuple = ()
    reason: str = ""


class ResetPolicyRegistry:
    """Small explicit foundation that later prompts extend with generated models."""

    def decision_for_values(self, model_name, values):
        state = (values or {}).get("state")

        if model_name in {
            "clinic.analytics.forecast", "clinic.analytics.snapshot",
            "clinic.report.run", "clinic.postcare.task",
        }:
            return ResetPolicyDecision(
                RESET_FRESH_DB_ONLY,
                reason=(
                    "Generated report, analytics, forecast, and post-care evidence is retained "
                    "for auditability; a fresh database is the destructive acceptance boundary."
                ),
            )

        if model_name in {"res.company", "resource.calendar", "stock.warehouse"}:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason="Demo-owned organization infrastructure is archived, never generically deleted.",
            )


        if model_name in {
            "res.users", "res.partner", "hr.employee", "hr.department",
            "clinic.staff", "clinic.practitioner", "clinic.skill",
            "clinic.license.type", "clinic.staff.license", "clinic.staff.availability",
            "clinic.specialty", "clinic.doctor", "clinic.schedule.rule",
        }:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason="Prompt-09 workforce/provider masters are retained but deactivated on demo reset.",
            )

        if model_name == "clinic.staff.skill":
            return ResetPolicyDecision(
                RESET_DELETE_SAFE,
                reason="Prompt-09 competency rows are demo-owned dependent records and may be deleted safely.",
            )

        if model_name == "clinic.patient":
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Prompt-10 patient masters are presentation anchors and may be "
                    "referenced by later clinical/financial history; reset archives them."
                ),
            )

        if model_name == "clinic.patient.identifier.type":
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Prompt-10 identifier-type masters are retained/deactivated; reused "
                    "non-demo types remain untouched by ownership-aware reset."
                ),
            )

        if model_name == "clinic.patient.identifier":
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Prompt-10 patient identifiers are identity evidence and are archived "
                    "with the patient instead of destructively deleted."
                ),
            )

        if model_name == "clinic.patient.condition":
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Prompt-10 longitudinal condition context is retained but deactivated "
                    "so later clinical history never loses its source patient context."
                ),
            )

        if model_name in {"clinic.patient.tag", "clinic.patient.allergy"}:
            return ResetPolicyDecision(
                RESET_DELETE_SAFE,
                reason=(
                    "Prompt-10 demo-owned patient tag/allergy dependent rows contain no "
                    "posted/legal workflow evidence and may be removed child-first."
                ),
            )

        if model_name in {
            "clinic.patient.vital",
            "clinic.patient.condition.episode",
            "clinic.patient.allergy.reaction",
        }:
            return ResetPolicyDecision(
                RESET_DELETE_SAFE,
                reason=(
                    "Prompt-13 longitudinal observations are demo-owned historical "
                    "children with explicit business dates and may be removed child-first."
                ),
            )

        if model_name in {
            "clinic.treatment.category", "clinic.treatment",
            "clinic.treatment.pricelist", "clinic.treatment.pricelist.item",
            "product.template", "product.product", "product.pricelist",
            "clinic.care.protocol", "clinic.care.protocol.step",
            "clinical.imaging.type", "clinic.emar.medication.profile",
            "clinic.consent.template", "clinic.package.policy",
            "clinic.package.pricing", "clinic.package", "membership.plan",
            "clinic.wallet.rule",
        }:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Prompt-11 reusable clinical/commercial masters are presentation anchors; "
                    "reset archives them rather than deleting structures later journeys may reference."
                ),
            )

        if model_name in {
            "clinical.imaging.protocol", "clinical.imaging.type.prep",
            "clinical.imaging.type.contra", "clinic.consent.template.version",
            "clinic.package.line", "membership.plan.benefit",
            "clinic.insurance.plan", "clinic.insurance.plan.rule",
        }:
            return ResetPolicyDecision(
                RESET_FRESH_DB_ONLY,
                reason=(
                    "Prompt-11 frozen/versioned child policy rows are retained until fresh-DB reset "
                    "because active parent workflows protect their structure."
                ),
            )

        if model_name in {
            "clinic.consent.template.item", "clinic.package.integration.event",
            "membership.integration.event",
        }:
            return ResetPolicyDecision(
                RESET_DELETE_SAFE,
                reason=(
                    "Prompt-11 demo-owned acknowledgement/outbox rows are local-safe dependent "
                    "records and may be removed child-first when not immutable/processed evidence."
                ),
            )

        if model_name in {
            "clinic.room.type", "clinic.room", "clinic.device.category", "clinic.device",
            "clinic.room.device.assignment", "booking.room.tag", "booking.room",
            "booking.resource.tag", "booking.resource", "booking.slot",
        }:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Prompt-12 resource/scheduling masters are presentation anchors and are "
                    "archived on reset so later bookings and operational history retain valid references."
                ),
            )

        if model_name in {
            "clinic.room.availability", "booking.room.schedule", "booking.room.blackout",
            "booking.resource.schedule", "booking.resource.blackout",
            "booking.doctor.schedule", "booking.doctor.blackout", "booking.slot.exception",
        }:
            return ResetPolicyDecision(
                RESET_DELETE_SAFE,
                reason=(
                    "Prompt-12 demo-owned schedule/blackout rows are reversible configuration children "
                    "and may be deleted safely before their parent resources are archived."
                ),
            )

        if model_name == "resource.resource":
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason="Resources auto-created for demo branch locations are archived on reset.",
            )

        if model_name == "ir.sequence":
            return ResetPolicyDecision(
                RESET_FRESH_DB_ONLY,
                reason=(
                    "Branch-owned sequences are retained as technical numbering evidence; "
                    "fresh-database reset removes them with the database."
                ),
            )

        if model_name in {"clinic.branch", "clinic.branch.location"}:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Demo organization masters are archived/deactivated so related "
                    "historical references are never destroyed by generic reset."
                ),
            )

        if model_name in {"clinic.referral.program", "clinic.referral.source", "booking.channel"}:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason="Prompt-14 reusable acquisition/front-office masters are archived on reset.",
            )

        if model_name == "booking.booking":
            if state == "done":
                return ResetPolicyDecision(
                    RESET_FRESH_DB_ONLY,
                    reason="Completed historical bookings are retained as longitudinal service evidence.",
                )
            if state in {"confirmed", "in_progress"}:
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_cancel",),
                    reason="Active demo bookings must be cancelled through the owner workflow before delete.",
                )
            if state in {"draft", "cancelled"}:
                return ResetPolicyDecision(RESET_DELETE_SAFE)
            raise ValidationError(f"No reset policy is registered for booking.booking state {state!r}.")

        if model_name == "clinic.audit.event":
            return ResetPolicyDecision(
                RESET_RETAIN_IMMUTABLE,
                reason="Audit events are immutable source evidence.",
            )

        if model_name == "clinic.referral":
            if state == "converted":
                return ResetPolicyDecision(
                    RESET_FRESH_DB_ONLY,
                    reason="Converted referrals have no normal public transition back to a deletable state.",
                )
            if state == "expired":
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_set_draft",),
                    reason="Expired referrals must return to Draft through the manager workflow before delete.",
                )
            if state == "confirmed":
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_cancel",),
                    reason="Confirmed referrals must be cancelled before delete.",
                )
            if state in {"draft", "cancelled"}:
                return ResetPolicyDecision(RESET_DELETE_SAFE)
            raise ValidationError(
                f"No reset policy is registered for clinic.referral state {state!r}."
            )

        if model_name == "clinic.treatment.session":
            if state == "done":
                return ResetPolicyDecision(
                    RESET_FRESH_DB_ONLY,
                    reason="Done Treatment Sessions are protected service evidence.",
                )
            if state == "no_show":
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_reset_draft",),
                    reason="No-show sessions must use the manager reset workflow before delete.",
                )
            if state in {"confirmed", "in_progress"}:
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_cancel",),
                    reason="Active Treatment Sessions must be cancelled before delete.",
                )
            if state in {"draft", "cancelled"}:
                return ResetPolicyDecision(RESET_DELETE_SAFE)
            raise ValidationError(
                f"No reset policy is registered for clinic.treatment.session state {state!r}."
            )

        if model_name == "clinic.consent.form":
            if state in {"signed", "archived"}:
                return ResetPolicyDecision(
                    RESET_RETAIN_IMMUTABLE,
                    reason="Signed/archived consent is legal evidence.",
                )
            if state == "to_sign":
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_cancel",),
                )
            if state in {"draft", "cancelled"}:
                return ResetPolicyDecision(RESET_DELETE_SAFE)
            raise ValidationError(
                f"No reset policy is registered for clinic.consent.form state {state!r}."
            )

        if model_name == "clinic.billing.invoice":
            if state in {"posted", "paid"}:
                return ResetPolicyDecision(
                    RESET_REVERSE_THEN_RETAIN,
                    reason="Posted financial evidence is reversed/corrected, not deleted.",
                )
            if state == "confirmed":
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_cancel",),
                )
            if state in {"draft", "cancelled"}:
                return ResetPolicyDecision(RESET_DELETE_SAFE)
            raise ValidationError(
                f"No reset policy is registered for clinic.billing.invoice state {state!r}."
            )

        if model_name == "clinic.billing.payment":
            if state in {"posted", "reconciled"}:
                return ResetPolicyDecision(
                    RESET_REVERSE_THEN_RETAIN,
                    reason="Posted/reconciled payment evidence cannot be destructively reset.",
                )
            if state in {"confirmed", "failed"}:
                return ResetPolicyDecision(
                    RESET_CANCEL_THEN_DELETE,
                    pre_actions=("action_cancel",),
                )
            if state in {"draft", "cancelled"}:
                return ResetPolicyDecision(RESET_DELETE_SAFE)
            raise ValidationError(
                f"No reset policy is registered for clinic.billing.payment state {state!r}."
            )

        if model_name in {"account.move", "clinic.ap", "clinic.ar.invoice"}:
            return ResetPolicyDecision(
                RESET_REVERSE_THEN_RETAIN,
                reason=(
                    "Accounting, receivable, and payable evidence is never deleted by "
                    "generic demo reset; owner correction/reversal or a fresh database is required."
                ),
            )

        if model_name in {
            "clinic.analytics.forecast.point", "clinic.analytics.insight",
            "clinic.analytics.snapshot.line", "clinic.api.event",
            "clinic.appointment",
            "clinic.care.plan", "clinic.dashboard.snapshot",
            "clinic.dashboard.snapshot.line", "clinic.diagnosis",
            "clinic.emar.administration", "clinic.emar.medication.line",
            "clinic.emar.order", "clinic.emar.prescription", "clinic.encounter",
            "clinic.encounter.procedure", "clinic.feedback",
            "clinic.feedback.escalation", "clinic.incident", "clinic.postcare.plan",
            "clinic.quality.check", "clinic.queue", "clinic.queue.token",
            "clinic.report.detail", "clinic.report.metric", "clinic.room.assignment",
            "clinic.soap.note", "clinic.telemedicine.message",
            "clinic.telemedicine.session", "clinic.telemedicine.thread",
            "clinic.treatment.session.line", "clinic.triage.session",
            "clinic.vitals.intake", "clinical.imaging",
        }:
            return ResetPolicyDecision(
                RESET_FRESH_DB_ONLY,
                reason=(
                    "This record is clinical, operational, communication, exception, or "
                    "management evidence. It is retained to preserve provenance and is "
                    "removed only with the disposable fresh-database acceptance dataset."
                ),
            )

        if model_name in {
            "clinic.api.event.type", "clinic.encounter.stage", "clinic.feedback.survey",
            "clinic.postcare.protocol", "clinic.procedure.catalog",
            "clinic.procedure.category", "clinic.quality.check.template",
            "clinic.triage.level", "clinical.imaging.device",
        }:
            return ResetPolicyDecision(
                RESET_DEACTIVATE,
                reason=(
                    "Demo-owned reusable master/configuration records are archived rather "
                    "than deleted so retained evidence keeps valid relations."
                ),
            )

        raise ValidationError(
            f"No reset policy is registered for model {model_name}. "
            "Unknown models are blocked from reset."
        )

    def policy_for_record(self, record):
        record.ensure_one()
        values = {}
        if "state" in record._fields:
            values["state"] = record.state
        return self.decision_for_values(record._name, values)





