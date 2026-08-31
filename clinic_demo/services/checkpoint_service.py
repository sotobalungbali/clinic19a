
"""Idempotent checkpoint helpers for future bounded execution."""

from odoo import fields


class DemoCheckpointService:
    def __init__(self, env):
        self.env = env

    def ensure(
        self,
        run,
        checkpoint_key,
        phase_key,
        generator_key,
        sequence,
        scenario_key=None,
    ):
        run.ensure_one()
        model = self.env["clinic.demo.checkpoint"]
        checkpoint = model.search(
            [("run_id", "=", run.id), ("checkpoint_key", "=", checkpoint_key)],
            limit=1,
        )
        values = {
            "phase_key": phase_key,
            "generator_key": generator_key,
            "scenario_key": scenario_key or False,
            "sequence": sequence,
            "source_fingerprint": run.source_fingerprint,
        }
        if checkpoint:
            if checkpoint.state in {"pending", "failed", "skipped"}:
                checkpoint.write(values)
            return checkpoint
        values.update({
            "run_id": run.id,
            "checkpoint_key": checkpoint_key,
        })
        return model.create(values)

    def start(self, checkpoint):
        checkpoint.ensure_one()
        checkpoint.write({
            "state": "running",
            "attempt_count": checkpoint.attempt_count + 1,
            "started_at": fields.Datetime.now(),
            "completed_at": False,
            "error_summary": False,
        })
        return checkpoint

    def complete(self, checkpoint, counters=None):
        checkpoint.ensure_one()
        values = {
            "state": "done",
            "completed_at": fields.Datetime.now(),
            "error_summary": False,
        }
        for key, value in (counters or {}).items():
            field_name = f"{key}_count"
            if field_name in checkpoint._fields:
                values[field_name] = int(value)
        checkpoint.write(values)
        checkpoint.run_id.write({
            "last_successful_checkpoint_key": checkpoint.checkpoint_key,
        })
        return checkpoint

    def fail(self, checkpoint, message):
        checkpoint.ensure_one()
        checkpoint.write({
            "state": "failed",
            "completed_at": fields.Datetime.now(),
            "error_count": checkpoint.error_count + 1,
            "error_summary": str(message)[:4000],
        })
        checkpoint.run_id.write({
            "state": "failed",
            "error_count": checkpoint.run_id.error_count + 1,
        })
        return checkpoint



