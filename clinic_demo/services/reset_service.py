




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

    def _record(self, reference, technical=False):
        try:
            model = self.env[reference.model_name]
        except KeyError:
            return False
        if technical:
            model = model.sudo()
        return model.browse(reference.res_id).exists()

    def inspect(self, reference, technical=False):
        reference.ensure_one()
        record = self._record(reference, technical=technical)
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
            active_field = "active" if "active" in record._fields else ("is_active" if "is_active" in record._fields else False)
            if not active_field:
                raise ValidationError(
                    f"Model {record._name} has no active/is_active field; deactivation is not possible."
                )

            if record._name == "clinic.branch":
                company = record.company_id
                if (
                    "default_branch_id" in company._fields
                    and company.default_branch_id == record
                ):
                    company.write({"default_branch_id": False})

            record.write({active_field: False})
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


    def preview_run(self, run):
        """Return a policy-aware reset preview without modifying business records."""
        run.ensure_one()
        references = self.env["clinic.demo.reference"].search(
            [("run_id", "=", run.id)],
            order="reset_sequence desc, id desc",
        )
        summary = {
            "total": len(references),
            "delete_or_cancel": 0,
            "deactivate": 0,
            "retain": 0,
            "missing": 0,
            "blocked": 0,
        }
        for reference in references:
            try:
                inspection = self.inspect(reference)
            except Exception:
                summary["blocked"] += 1
                continue
            action = inspection.get("action")
            if action == "missing":
                summary["missing"] += 1
            elif action in {"delete_safe", "cancel_then_delete"}:
                summary["delete_or_cancel"] += 1
            elif action == "deactivate":
                summary["deactivate"] += 1
            elif action in {
                "retain",
                "retain_immutable",
                "fresh_db_reset_only",
                "reverse_then_retain",
            }:
                summary["retain"] += 1
            else:
                summary["blocked"] += 1
        return summary

    def reset_run(self, run):
        """Reset demo-owned references in explicit child-first sequence.

        Prompt 23 makes reset atomic: the complete ordered plan is preflighted
        before the first mutation, and any runtime failure rolls the request
        back instead of leaving a partially reset dataset.
        """
        run.ensure_one()
        references = self.env["clinic.demo.reference"].search(
            [("run_id", "=", run.id)],
            order="reset_sequence desc, id desc",
        )
        blocked = []
        for reference in references:
            try:
                inspection = self.inspect(reference)
                record = self._record(reference)
                for action_name in inspection.get("pre_actions", ()):
                    if record and not hasattr(record, action_name):
                        blocked.append(
                            f"{reference.demo_key}: missing {record._name}.{action_name}()"
                        )
            except Exception as exc:
                blocked.append(f"{reference.demo_key}: {exc}")
        if blocked:
            raise ValidationError(
                "Reset whole-path preflight failed: " + "; ".join(blocked)
            )

        summary = {
            "removed": 0,
            "deactivated": 0,
            "retained": 0,
            "missing": 0,
            "errors": 0,
        }

        for reference in references:
            try:
                result = self.reset_reference(reference)
            except Exception as exc:
                raise ValidationError(
                    f"Atomic reset failed at {reference.demo_key}; no reset changes "
                    f"were committed. Root cause: {exc}"
                ) from exc

            status = result.get("status")
            if status in {"removed"}:
                summary["removed"] += 1
            elif status in {"deactivated"}:
                summary["deactivated"] += 1
            elif status in {"retained", "retained_reused"}:
                summary["retained"] += 1
            elif status == "already_missing":
                summary["missing"] += 1

        if run.checkpoint_ids:
            run.checkpoint_ids.write({
                "state": "pending",
                "completed_at": False,
                "error_summary": False,
            })

        run.validation_result_ids.unlink()

        run.write({
            "state": "failed" if summary["errors"] else "draft",
            "validation_status": "not_run",
            "current_phase": False,
            "current_scenario": False,
            "last_successful_checkpoint_key": False,
            "completed_at": False,
            "created_count": 0,
            "reused_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "warning_count": 0,
            "error_count": summary["errors"],
        })
        return summary







