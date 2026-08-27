"""Stable demo identity and idempotent create/reuse helpers."""

import re

from odoo import fields
from odoo.exceptions import ValidationError

from .reset_policy_registry import ResetPolicyRegistry

_DEMO_KEY_RE = re.compile(r"^DEMO-[A-Z0-9][A-Z0-9._-]*$")


class DemoReferenceService:
    def __init__(self, env):
        self.env = env
        self.policy_registry = ResetPolicyRegistry()

    def _validate_key(self, demo_key):
        if not _DEMO_KEY_RE.match(demo_key or ""):
            raise ValidationError(
                "Demo keys must start with DEMO- and use uppercase letters, "
                "numbers, dots, underscores, or hyphens."
            )

    def _reference(self, run, demo_key):
        run.ensure_one()
        return self.env["clinic.demo.reference"].search(
            [("run_id", "=", run.id), ("demo_key", "=", demo_key)],
            limit=1,
        )

    def _existing_record(self, reference):
        if not reference:
            return False
        try:
            model = self.env[reference.model_name]
        except KeyError:
            return False
        return model.browse(reference.res_id).exists()

    def resolve(self, run, demo_key, expected_model=None, missing_ok=False):
        self._validate_key(demo_key)
        reference = self._reference(run, demo_key)
        if not reference:
            if missing_ok:
                return False
            raise ValidationError(f"Demo reference {demo_key} does not exist.")

        if expected_model and reference.model_name != expected_model:
            raise ValidationError(
                f"Demo key {demo_key} points to {reference.model_name}, "
                f"not expected model {expected_model}."
            )

        record = self._existing_record(reference)
        if not record:
            values = {"last_checked_at": fields.Datetime.now()}
            if reference.record_status not in {"reset_removed", "reset_retained"}:
                values["record_status"] = "missing"
            reference.write(values)
            if missing_ok:
                return False
            raise ValidationError(
                f"Demo reference {demo_key} points to a missing record."
            )

        if reference.record_status != "bound":
            reference.write({"record_status": "bound"})
        reference.last_checked_at = fields.Datetime.now()
        return record

    def bind(
        self,
        run,
        demo_key,
        record,
        generator_key,
        scenario_key=None,
        ownership_kind="created",
        reset_policy=None,
        business_reference=None,
        reset_sequence=100,
    ):
        self._validate_key(demo_key)
        run.ensure_one()
        record.ensure_one()

        if reset_policy is None:
            reset_policy = self.policy_registry.policy_for_record(record).policy

        reference = self._reference(run, demo_key)
        existing_record = self._existing_record(reference)

        if reference and existing_record and (
            reference.model_name != record._name or reference.res_id != record.id
        ):
            raise ValidationError(
                f"Demo key {demo_key} is already bound to a different live record."
            )

        values = {
            "run_id": run.id,
            "demo_key": demo_key,
            "generator_key": generator_key,
            "scenario_key": scenario_key or False,
            "model_name": record._name,
            "res_id": record.id,
            "display_name": record.display_name,
            "business_reference": business_reference or record.display_name,
            "ownership_kind": ownership_kind,
            "reset_sequence": int(reset_sequence),
            "reset_policy_snapshot": reset_policy,
            "record_status": "bound",
            "last_checked_at": fields.Datetime.now(),
        }
        if reference:
            reference.write(values)
            return reference
        return self.env["clinic.demo.reference"].create(values)

    def ensure_record(
        self,
        run,
        demo_key,
        model_name,
        generator_key,
        create_callback,
        scenario_key=None,
        reset_policy=None,
        update_callback=None,
        reset_sequence=100,
    ):
        """Create once, then resolve/reuse deterministically on every rerun.

        The callback owns source-specific creation so this generic service never
        bypasses business methods or invents core values.
        """
        self._validate_key(demo_key)
        reference = self._reference(run, demo_key)
        if reference:
            if reference.model_name != model_name:
                raise ValidationError(
                    f"Demo key {demo_key} is registered for {reference.model_name}, "
                    f"not {model_name}."
                )
            record = self._existing_record(reference)
            if record:
                status = "reused"
                if update_callback:
                    if reference.ownership_kind == "reused":
                        raise ValidationError(
                            f"Demo key {demo_key} points to a reused non-demo record. "
                            "The generic idempotency service will not mutate it."
                        )
                    update_callback(record)
                    reference.ownership_kind = "updated_demo_owned"
                    status = "updated"
                reference.write({
                    "record_status": "bound",
                    "last_checked_at": fields.Datetime.now(),
                })
                return record, reference, status

        record = create_callback()
        if not record or len(record) != 1 or record._name != model_name:
            raise ValidationError(
                f"Create callback for {demo_key} must return exactly one {model_name} record."
            )

        reference = self.bind(
            run=run,
            demo_key=demo_key,
            record=record,
            generator_key=generator_key,
            scenario_key=scenario_key,
            ownership_kind="created",
            reset_policy=reset_policy,
            reset_sequence=reset_sequence,
        )
        return record, reference, "created"

    def bind_reused(
        self,
        run,
        demo_key,
        record,
        generator_key,
        scenario_key=None,
        reset_policy=None,
        reset_sequence=100,
    ):
        return self.bind(
            run=run,
            demo_key=demo_key,
            record=record,
            generator_key=generator_key,
            scenario_key=scenario_key,
            ownership_kind="reused",
            reset_policy=reset_policy,
            reset_sequence=reset_sequence,
        )
