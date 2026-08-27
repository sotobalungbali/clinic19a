"""Source-driven reset-policy decisions.

Unknown model/state combinations are deliberately blocked instead of falling back
to destructive deletion.
"""

from dataclasses import dataclass

from odoo.exceptions import ValidationError

from .constants import (
    RESET_CANCEL_THEN_DELETE,
    RESET_DELETE_SAFE,
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
                f"No reset policy is registered for clinic.referral state {{state!r}}."
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
                f"No reset policy is registered for clinic.treatment.session state {{state!r}}."
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
                f"No reset policy is registered for clinic.consent.form state {{state!r}}."
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
                f"No reset policy is registered for clinic.billing.invoice state {{state!r}}."
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
                f"No reset policy is registered for clinic.billing.payment state {{state!r}}."
            )

        raise ValidationError(
            f"No reset policy is registered for model {{model_name}}. "
            "Unknown models are blocked from reset."
        )

    def policy_for_record(self, record):
        record.ensure_one()
        values = {{}}
        if "state" in record._fields:
            values["state"] = record.state
        return self.decision_for_values(record._name, values)
