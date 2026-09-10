




"""Persistent checkpoint used for bounded, resumable demo generation."""

from odoo import fields, models


class ClinicDemoCheckpoint(models.Model):
    _name = "clinic.demo.checkpoint"
    _description = "ClinicOne Demo Generation Checkpoint"
    _order = "run_id desc, sequence, id"

    run_id = fields.Many2one(
        "clinic.demo.run",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="run_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    checkpoint_key = fields.Char(required=True, index=True)
    phase_key = fields.Char(required=True, index=True)
    generator_key = fields.Char(required=True, index=True)
    scenario_key = fields.Char(index=True)
    sequence = fields.Integer(required=True, default=10, index=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("skipped", "Skipped"),
        ],
        required=True,
        default="pending",
        index=True,
    )
    attempt_count = fields.Integer(default=0, readonly=True)
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)

    created_count = fields.Integer(default=0, readonly=True)
    reused_count = fields.Integer(default=0, readonly=True)
    updated_count = fields.Integer(default=0, readonly=True)
    skipped_count = fields.Integer(default=0, readonly=True)
    warning_count = fields.Integer(default=0, readonly=True)
    error_count = fields.Integer(default=0, readonly=True)

    source_fingerprint = fields.Char(required=True, index=True)
    error_summary = fields.Text(readonly=True)

    _run_checkpoint_unique = models.Constraint(
        "UNIQUE(run_id, checkpoint_key)",
        "A checkpoint key must be unique within one Demo Run.",
    )
    _attempt_nonnegative = models.Constraint(
        "CHECK(attempt_count >= 0)",
        "Checkpoint attempt count cannot be negative.",
    )


    def action_open_run(self):
        """Navigate back to the owning Demo Control Center run."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.run_id.display_name,
            "res_model": "clinic.demo.run",
            "view_mode": "form",
            "res_id": self.run_id.id,
            "target": "current",
        }


    def action_open_checkpoint(self):
        """Open this exact service-managed record from an embedded One2many row."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Generation Checkpoint",
            "res_model": "clinic.demo.checkpoint",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }









