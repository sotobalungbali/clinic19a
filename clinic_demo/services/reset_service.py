"""Ownership-aware reset foundation.

Full cross-domain reset ordering is intentionally completed in Prompt 23. This
foundation already refuses unsafe destructive fallbacks.
"""

from odoo import fields
from odoo.exceptions import ValidationError

from .constants import (
    RESET_CANCEL_THEN_DELETE,
    RESET_DEACTIVATE,
    RESET_DELETE_SAFE,
    RESET_FRESH_DB_ONLY,
    RESET_RETAIN_IMMUTABLE,
    RESET_REVERSE_THEN_RETAIN,
)
from .reset_policy_registry import ResetPolicyRegistry


class DemoResetService:
    def __init__(self, env):
        self.env = env
        self.registry = ResetPolicyRegistry()

    def _record(self, reference):
        try:
            model = self.env[reference.model_name]
        except KeyError:
            return False
        return model.browse(reference.res_id).exists()

    def inspect(self, reference):
        reference.ensure_one()
        record = self._record(reference)
        if not record:
            return {
                "action": "missing",
                "policy": reference.reset_policy_snapshot,
                "reason": "Referenced record no longer exists.",
            }

        if reference.ownership_kind == "reused":
            return {
                "action": "retain",
                "policy": reference.reset_policy_snapshot,
                "reason": "Reused non-demo record is never deleted by demo reset.",
            }

        decision = self.registry.policy_for_record(record)
        return {
            "action": decision.policy,
            "policy": decision.policy,
            "pre_actions": decision.pre_actions,
            "reason": decision.reason,
        }

    def reset_reference(self, reference, dry_run=False):
        reference.ensure_one()
        record = self._record(reference)
        now = fields.Datetime.now()

        if not record:
            if not dry_run:
                reference.write({
                    "record_status": "reset_removed",
                    "last_reset_at": now,
                })
            return {"status": "already_missing"}

        if reference.ownership_kind == "reused":
            if not dry_run:
                reference.write({
                    "record_status": "reset_retained",
                    "last_reset_at": now,
                })
            return {"status": "retained_reused"}

        decision = self.registry.policy_for_record(record)

        if decision.policy in {
            RESET_RETAIN_IMMUTABLE,
            RESET_FRESH_DB_ONLY,
            RESET_REVERSE_THEN_RETAIN,
        }:
            if not dry_run:
                reference.write({
                    "record_status": "reset_retained",
                    "last_reset_at": now,
                    "note": decision.reason or reference.note,
                })
            return {"status": "retained", "policy": decision.policy}

        if dry_run:
            return {
                "status": "would_reset",
                "policy": decision.policy,
                "pre_actions": decision.pre_actions,
            }

        if decision.policy == RESET_CANCEL_THEN_DELETE:
            for action_name in decision.pre_actions:
                if not hasattr(record, action_name):
                    raise ValidationError(
                        f"Reset policy requires {record._name}.{action_name}(), "
                        "but that method is not available."
                    )
                getattr(record, action_name)()
                record = record.exists()
                if not record:
                    break

        if record and decision.policy == RESET_DEACTIVATE:
            if "active" not in record._fields:
                raise ValidationError(
                    f"Model {record._name} has no active field; deactivation is not possible."
                )
            record.write({"active": False})
            reference.write({
                "record_status": "reset_retained",
                "last_reset_at": now,
            })
            return {"status": "deactivated"}

        if record and decision.policy in {RESET_DELETE_SAFE, RESET_CANCEL_THEN_DELETE}:
            record.unlink()
            reference.write({
                "record_status": "reset_removed",
                "last_reset_at": now,
            })
            return {"status": "removed"}

        raise ValidationError(
            f"Unsupported reset policy {decision.policy!r} for {reference.demo_key}."
        )
