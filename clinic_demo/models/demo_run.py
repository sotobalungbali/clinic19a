"""Persistent identity for one ClinicOne enterprise demo dataset run."""

from odoo import api, fields, models

from ..services.constants import (
    AUTHORITATIVE_SOURCE_FINGERPRINT,
    EXPECTED_SUITE_FINGERPRINT,
    GENERATOR_VERSION,
    PROFILE_SELECTION,
)


class ClinicDemoRun(models.Model):
    _name = "clinic.demo.run"
    _description = "ClinicOne Demo Dataset Run"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete="restrict",
        tracking=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Currency",
        readonly=True,
    )

    profile = fields.Selection(
        PROFILE_SELECTION,
        required=True,
        default="full_enterprise",
        tracking=True,
    )
    anchor_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    timezone = fields.Char(
        required=True,
        default=lambda self: self.env.user.tz or "UTC",
    )
    locale = fields.Char(
        required=True,
        default=lambda self: self.env.context.get("lang") or self.env.user.lang or "en_US",
    )
    deterministic_seed = fields.Char(
        required=True,
        default="247001",
        help="Stable master seed. Namespace-derived randomness keeps scenario identities deterministic.",
    )
    safe_mode = fields.Boolean(
        default=True,
        required=True,
        tracking=True,
        help="When enabled, demo orchestration must not invoke real external side effects.",
    )

    generator_version = fields.Char(
        required=True,
        readonly=True,
        default=GENERATOR_VERSION,
    )
    source_fingerprint = fields.Char(
        required=True,
        readonly=True,
        default=AUTHORITATIVE_SOURCE_FINGERPRINT,
    )
    expected_suite_fingerprint = fields.Char(
        required=True,
        readonly=True,
        default=EXPECTED_SUITE_FINGERPRINT,
    )
    source_suite_fingerprint = fields.Char(
        string="Source Suite Fingerprint",
        readonly=True,
        copy=False,
        help="Fingerprint of addon manifest versions currently present on disk.",
    )
    database_suite_fingerprint = fields.Char(
        string="Database Suite Fingerprint",
        readonly=True,
        copy=False,
        help="Fingerprint of addon versions recorded as installed in the database.",
    )

    compatibility_state = fields.Selection(
        [
            ("unchecked", "Unchecked"),
            ("compatible", "Compatible"),
            ("blocked", "Blocked"),
        ],
        required=True,
        default="unchecked",
        readonly=True,
        copy=False,
        tracking=True,
    )
    compatibility_message = fields.Text(readonly=True, copy=False)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("generating", "Generating"),
            ("validating", "Validating"),
            ("ready", "Ready"),
            ("failed", "Failed"),
        ],
        required=True,
        default="draft",
        tracking=True,
        copy=False,
    )
    current_phase = fields.Char(copy=False, readonly=True)
    current_scenario = fields.Char(copy=False, readonly=True)
    last_successful_checkpoint_key = fields.Char(copy=False, readonly=True)

    started_at = fields.Datetime(copy=False, readonly=True)
    completed_at = fields.Datetime(copy=False, readonly=True)

    created_count = fields.Integer(default=0, readonly=True, copy=False)
    reused_count = fields.Integer(default=0, readonly=True, copy=False)
    updated_count = fields.Integer(default=0, readonly=True, copy=False)
    skipped_count = fields.Integer(default=0, readonly=True, copy=False)
    warning_count = fields.Integer(default=0, readonly=True, copy=False)
    error_count = fields.Integer(default=0, readonly=True, copy=False)

    validation_status = fields.Selection(
        [
            ("not_run", "Not Run"),
            ("pass", "Pass"),
            ("warning", "Warning"),
            ("fail", "Fail"),
        ],
        required=True,
        default="not_run",
        readonly=True,
        copy=False,
    )
    patch_compatibility_status = fields.Char(
        default="Not evaluated",
        readonly=True,
        copy=False,
    )

    reference_ids = fields.One2many("clinic.demo.reference", "run_id", string="Demo References")
    checkpoint_ids = fields.One2many("clinic.demo.checkpoint", "run_id", string="Checkpoints")
    log_ids = fields.One2many("clinic.demo.log", "run_id", string="Logs")
    validation_result_ids = fields.One2many(
        "clinic.demo.validation.result",
        "run_id",
        string="Validation Results",
    )

    reference_count = fields.Integer(compute="_compute_child_counts")
    checkpoint_count = fields.Integer(compute="_compute_child_counts")
    log_count = fields.Integer(compute="_compute_child_counts")
    validation_result_count = fields.Integer(compute="_compute_child_counts")

    @api.depends("reference_ids", "checkpoint_ids", "log_ids", "validation_result_ids")
    def _compute_child_counts(self):
        for run in self:
            run.reference_count = len(run.reference_ids)
            run.checkpoint_count = len(run.checkpoint_ids)
            run.log_count = len(run.log_ids)
            run.validation_result_count = len(run.validation_result_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Assign a readable run reference without assuming one-record create calls."""
        sequence = self.env["ir.sequence"]
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            if not values.get("name") or values.get("name") == "New":
                values["name"] = sequence.next_by_code("clinic.demo.run") or "Demo Run"
            prepared.append(values)
        return super().create(prepared)

    def action_refresh_compatibility(self):
        """Re-evaluate the installed ClinicOne suite against this build contract."""
        from ..services.fingerprint_service import SourceFingerprintService

        for run in self:
            SourceFingerprintService(self.env).check_compatibility(run=run)
        return True
