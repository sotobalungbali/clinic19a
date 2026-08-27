"""Enterprise Control Center for one ClinicOne demo dataset run."""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

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
    missing_reference_count = fields.Integer(compute="_compute_child_counts")
    checkpoint_count = fields.Integer(compute="_compute_child_counts")
    failed_checkpoint_count = fields.Integer(compute="_compute_child_counts")
    log_count = fields.Integer(compute="_compute_child_counts")
    validation_result_count = fields.Integer(compute="_compute_child_counts")
    validation_failure_count = fields.Integer(compute="_compute_child_counts")

    executable_generator_count = fields.Integer(
        string="Executable Generators",
        compute="_compute_framework_readiness",
    )
    scenario_count = fields.Integer(
        string="Registered Scenarios",
        compute="_compute_framework_readiness",
    )
    generation_readiness = fields.Selection(
        [
            ("framework_only", "Framework Ready / Domain Generators Pending"),
            ("partial", "Partial Generator Coverage"),
            ("ready", "Generator Registry Ready"),
        ],
        string="Generation Readiness",
        compute="_compute_framework_readiness",
    )

    @api.depends(
        "reference_ids.record_status",
        "checkpoint_ids.state",
        "log_ids",
        "validation_result_ids.state",
    )
    def _compute_child_counts(self):
        for run in self:
            run.reference_count = len(run.reference_ids)
            run.missing_reference_count = len(
                run.reference_ids.filtered(lambda ref: ref.record_status == "missing")
            )
            run.checkpoint_count = len(run.checkpoint_ids)
            run.failed_checkpoint_count = len(
                run.checkpoint_ids.filtered(lambda checkpoint: checkpoint.state == "failed")
            )
            run.log_count = len(run.log_ids)
            run.validation_result_count = len(run.validation_result_ids)
            run.validation_failure_count = len(
                run.validation_result_ids.filtered(lambda result: result.state == "fail")
            )

    def _compute_framework_readiness(self):
        from ..services.generator_registry import GENERATOR_REGISTRY
        from ..services.scenario_registry import ScenarioRegistry

        generator_count = len(GENERATOR_REGISTRY.all())
        scenario_count = len(ScenarioRegistry.all())
        if generator_count == 0:
            readiness = "framework_only"
        elif generator_count < 35:
            readiness = "partial"
        else:
            readiness = "ready"

        for run in self:
            run.executable_generator_count = generator_count
            run.scenario_count = scenario_count
            run.generation_readiness = readiness

    @api.model_create_multi
    def create(self, vals_list):
        """Assign readable run references without assuming single-record create calls."""
        sequence = self.env["ir.sequence"]
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            if not values.get("name") or values.get("name") == "New":
                values["name"] = sequence.next_by_code("clinic.demo.run") or "Demo Run"
            prepared.append(values)
        return super().create(prepared)


    @api.model
    def _ensure_demo_dataset_menu_parent(self):
        """Runtime-safe post-load routing for the Demo Dataset menu."""
        from ..services.menu_bridge_service import DemoMenuBridgeService

        return DemoMenuBridgeService(self.env).ensure_parent()

    # ------------------------------------------------------------------
    # Backend authorization: button visibility is never treated as security.
    # ------------------------------------------------------------------
    def _check_operator(self):
        authorized = (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("clinic_demo.group_demo_operator")
        )
        if not authorized:
            raise AccessError(
                _("System Administrator or Demo Dataset Operator access is required.")
            )

    def _check_manager(self):
        authorized = (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("clinic_demo.group_demo_manager")
        )
        if not authorized:
            raise AccessError(
                _("System Administrator or Demo Dataset Manager access is required.")
            )

    def _display_notification(self, title, message, notification_type="info", sticky=False):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": sticky,
            },
        }

    def _log_control_event(self, level, operation, message):
        from ..services.logging_service import DemoLoggingService

        return DemoLoggingService(self.env).log(
            run=self,
            level=level,
            operation=operation,
            message=message,
            phase_key=self.current_phase,
            scenario_key=self.current_scenario,
        )

    def _adopt_current_build_if_pristine(self):
        """Upgrade a pre-generation Control Center run to the current build contract.

        A run with generated references/checkpoints remains fingerprint-locked so
        source drift cannot be hidden. Prompt-07-only draft runs have no business
        dataset yet and may safely adopt the current clinic_demo framework build.
        """
        self.ensure_one()
        if self.reference_ids or self.checkpoint_ids:
            return False
        if self.state not in {"draft", "failed"}:
            return False

        changed = (
            self.generator_version != GENERATOR_VERSION
            or self.source_fingerprint != AUTHORITATIVE_SOURCE_FINGERPRINT
            or self.expected_suite_fingerprint != EXPECTED_SUITE_FINGERPRINT
        )
        if not changed:
            return False

        self.write({
            "generator_version": GENERATOR_VERSION,
            "source_fingerprint": AUTHORITATIVE_SOURCE_FINGERPRINT,
            "expected_suite_fingerprint": EXPECTED_SUITE_FINGERPRINT,
            "compatibility_state": "unchecked",
            "compatibility_message": False,
        })
        self._log_control_event(
            "info",
            "adopt_build_contract",
            "Pristine Demo Run adopted the current clinic_demo build fingerprint before generation.",
        )
        return True

    def _check_generation_preflight(self):
        self.ensure_one()
        self._check_operator()
        compatibility = self.action_refresh_compatibility()
        if self.compatibility_state != "compatible":
            raise UserError(
                _("Generation is blocked by source/runtime compatibility.\n\n%s")
                % (self.compatibility_message or _("Run Refresh Compatibility first."))
            )
        return compatibility

    # ------------------------------------------------------------------
    # Prompt-07 Control Center actions.
    # Domain execution stays safely gated until Prompt 08+ registers generators.
    # ------------------------------------------------------------------
    def action_generate_full_dataset(self):
        self.ensure_one()
        self._check_generation_preflight()
        from ..services.execution_engine import DemoExecutionEngine

        return DemoExecutionEngine(self.env).request_full_generation(self)

    def action_generate_current_phase(self):
        self.ensure_one()
        self._check_generation_preflight()
        from ..services.execution_engine import DemoExecutionEngine

        return DemoExecutionEngine(self.env).request_current_phase(self)

    def action_continue_generation(self):
        self.ensure_one()
        self._check_generation_preflight()
        from ..services.execution_engine import DemoExecutionEngine

        return DemoExecutionEngine(self.env).continue_generation(self)

    def action_validate(self):
        self.ensure_one()
        self._check_operator()
        from ..services.validation_service import DemoValidationService

        previous_state = self.state
        self.write({"state": "validating"})
        try:
            results = DemoValidationService(self.env).validate_identity_foundation(self)
        except Exception as exc:
            self.write({"state": "failed"})
            self._log_control_event(
                "error",
                "validate",
                f"Validation failed with {exc.__class__.__name__}: {exc}",
            )
            raise

        failed = any(result.state == "fail" for result in results)
        next_state = "failed" if failed else "ready" if previous_state == "ready" else "draft"
        self.write({
            "state": next_state,
            "validation_status": "fail" if failed else self.validation_status,
        })
        self._log_control_event(
            "error" if failed else "info",
            "validate",
            "Identity/source foundation validation failed."
            if failed
            else "Identity/source foundation validation completed.",
        )
        return self._display_notification(
            _("Validation Complete"),
            _("Identity/source foundation validation failed.")
            if failed
            else _("Identity/source foundation validation passed. Full readiness validation is completed in Prompt 23."),
            "danger" if failed else "success",
            sticky=failed,
        )

    def action_regenerate_missing(self):
        self.ensure_one()
        self._check_operator()
        from ..services.generator_registry import GENERATOR_REGISTRY
        from ..services.reference_service import DemoReferenceService

        reference_service = DemoReferenceService(self.env)
        missing = self.env["clinic.demo.reference"]
        for reference in self.reference_ids:
            if not reference_service._existing_record(reference):
                if reference.record_status not in {"reset_removed", "reset_retained"}:
                    reference.record_status = "missing"
                missing |= reference

        if not missing:
            self._log_control_event(
                "info",
                "regenerate_missing",
                "No missing demo references were detected.",
            )
            return self._display_notification(
                _("Regenerate Missing"),
                _("No missing demo-owned references were detected."),
                "success",
            )

        generators = {generator.key: generator for generator in GENERATOR_REGISTRY.all()}
        repairable = missing.filtered(lambda ref: ref.generator_key in generators)
        if not repairable:
            self._log_control_event(
                "warning",
                "regenerate_missing",
                f"{len(missing)} missing reference(s) found; no owning repair generator is registered yet.",
            )
            return self._display_notification(
                _("Missing Records Detected"),
                _("%s missing reference(s) were found. Their domain repair generators are not registered yet.")
                % len(missing),
                "warning",
                sticky=True,
            )

        from ..services.execution_engine import DemoExecutionEngine

        return DemoExecutionEngine(self.env).repair_missing(self, repairable)

    def action_open_reset_wizard(self):
        self.ensure_one()
        self._check_manager()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reset Demo Dataset"),
            "res_model": "clinic.demo.reset.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_run_id": self.id},
        }

    def action_refresh_compatibility(self):
        """Re-evaluate source-on-disk and database-installed ClinicOne versions."""
        self.ensure_one()
        self._check_operator()
        from ..services.fingerprint_service import SourceFingerprintService

        self._adopt_current_build_if_pristine()
        result = SourceFingerprintService(self.env).check_compatibility(run=self)
        if self.env.context.get("return_compatibility_notification"):
            return self._display_notification(
                _("Compatibility Check"),
                result["message"],
                "success" if result["compatible"] else "danger",
                sticky=not result["compatible"],
            )
        return result

    # ------------------------------------------------------------------
    # Smart-button/navigation actions.
    # ------------------------------------------------------------------
    def _open_related_action(self, name, res_model, domain):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_run_id": self.id},
        }

    def action_open_references(self):
        return self._open_related_action(
            _("Golden Journeys"),
            "clinic.demo.reference",
            [("run_id", "=", self.id)],
        )

    def action_open_golden_journeys(self):
        return self.action_open_references()

    def action_open_checkpoints(self):
        return self._open_related_action(
            _("Generation Checkpoints"),
            "clinic.demo.checkpoint",
            [("run_id", "=", self.id)],
        )

    def action_open_logs(self):
        return self._open_related_action(
            _("Demo Logs"),
            "clinic.demo.log",
            [("run_id", "=", self.id)],
        )

    def action_open_validation_results(self):
        return self._open_related_action(
            _("Validation Results"),
            "clinic.demo.validation.result",
            [("run_id", "=", self.id)],
        )
