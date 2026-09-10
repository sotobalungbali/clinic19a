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
        """Adopt the current build only across bounded progressive demo boundaries.
        Prompt 13 is additive: a run that completed Prompt 12 may adopt the
        historical-time/longitudinal build after ``clinic_demo`` is upgraded and
        Refresh Compatibility is executed. Prompt 12 remains additive: a run
        that completed Prompt 11 may adopt the room/device/resource scheduling
        build after ``clinic_demo`` is upgraded and Refresh Compatibility is executed. A Prompt-11 ``master.catalog``
        failure caused only by functional-owner ACL context may also adopt a
        bounded runtime-repair build when its savepoint left no Prompt-11
        references committed. A later ``master.commercial`` ACL failure may
        likewise adopt an owner-security repair when no commercial references
        were committed. A failed ``resources.rooms_devices`` savepoint may adopt
        Prompt-12 runtime repairs (owner sequence drift or deterministic slot-name
        uniqueness) only while it left no Prompt-12 references committed.
        A failed ``operations.booking`` savepoint may adopt a Prompt-14 owner/API
        runtime repair only when ``operations.referral`` is already complete and
        the failed booking generator left no Prompt-14 booking references committed.
        Prompt-11/10/09 bounded adoption routes remain supported for cumulative
        full-replacement upgrades.
        """
        self.ensure_one()
        from ..services.progressive_adoption import prompt_stage_adoption
        if self.state not in {"draft", "failed", "ready"}:
            return False
        foundation_generators = {"foundation.native", "foundation.organization"}
        workforce_generators = {"workforce.preflight", "workforce.staff"}
        patient_generators = {"patient.personas"}
        completed_prompt09_generators = foundation_generators | workforce_generators
        completed_prompt10_generators = completed_prompt09_generators | patient_generators
        prompt11_generators = {"master.catalog", "master.consent", "master.commercial"}
        completed_prompt11_generators = completed_prompt10_generators | prompt11_generators
        prompt12_generators = {"resources.rooms_devices"}
        completed_prompt12_generators = completed_prompt11_generators | prompt12_generators
        prompt13_generators = {"history.patient_longitudinal"}
        completed_prompt13_generators = completed_prompt12_generators | prompt13_generators
        prompt14_generators = {"operations.referral", "operations.booking"}
        completed_prompt14_generators = completed_prompt13_generators | prompt14_generators
        prompt15_generators = {"operations.queue_triage"}
        completed_prompt15_generators = completed_prompt14_generators | prompt15_generators
        prompt16_generators = {"operations.encounter", "operations.treatment_session"}
        completed_prompt16_generators = completed_prompt15_generators | prompt16_generators
        prompt17_sequence = (
            "clinical.imaging",
            "clinical.emar",
            "clinical.care_postcare",
            "clinical.telemedicine",
        )
        prompt17_generators = set(prompt17_sequence)
        completed_prompt17_generators = completed_prompt16_generators | prompt17_generators
        prompt18_sequence = (
            "commercial.billing",
            "commercial.ar",
            "commercial.ap",
        )
        prompt18_generators = set(prompt18_sequence)
        completed_prompt18_generators = completed_prompt17_generators | prompt18_generators
        prompt19_sequence = (
            "exception.feedback",
            "exception.incident_quality",
            "digital.ecommerce_marketing_portal",
        )
        prompt19_generators = set(prompt19_sequence)
        completed_prompt19_generators = completed_prompt18_generators | prompt19_generators
        completed_prompt20_generators = completed_prompt19_generators | {"operations.future_pipeline"}
        completed_prompt21_generators = completed_prompt20_generators | {"management.reports"}
        completed_prompt22_generators = completed_prompt21_generators | {
            "management.dashboard", "management.analytics",
        }
        prompt23_sequence = (
            "validation.structural",
            "validation.temporal",
            "validation.workflow",
            "validation.journey_exception",
            "validation.analytics_evidence",
            "validation.integrity_reset_regeneration",
        )
        generated_keys = set(self.reference_ids.mapped("generator_key"))
        checkpoint_generators = set(self.checkpoint_ids.mapped("generator_key"))
        progressive_prompt18_adoption, prompt18_runtime_repair_adoption, prompt18_failed_key = (
            prompt_stage_adoption(self, completed_prompt17_generators, prompt18_sequence)
        )
        progressive_prompt19_adoption, prompt19_runtime_repair_adoption, prompt19_failed_key = (
            prompt_stage_adoption(self, completed_prompt18_generators, prompt19_sequence)
        )
        progressive_prompt23_adoption, prompt23_runtime_repair_adoption, prompt23_failed_key = (
            prompt_stage_adoption(self, completed_prompt22_generators, prompt23_sequence)
        )
        prompt16_complete = all(
            bool(self.checkpoint_ids.filtered(
                lambda checkpoint, generator_key=generator_key: (
                    checkpoint.generator_key == generator_key
                    and checkpoint.state == "done"
                )
            ))
            for generator_key in prompt16_generators
        )
        progressive_prompt17_adoption = (
            self.state in {"draft", "ready"}
            and prompt16_complete
            and checkpoint_generators == completed_prompt16_generators
            and generated_keys <= completed_prompt16_generators
            and not (checkpoint_generators & prompt17_generators)
            and not (generated_keys & prompt17_generators)
        )
        prompt17_failed_keys = {
            generator_key
            for generator_key in prompt17_sequence
            if self.checkpoint_ids.filtered(
                lambda checkpoint, key=generator_key: (
                    checkpoint.generator_key == key
                    and checkpoint.state == "failed"
                )
            )
        }
        prompt17_failed_key = (
            next(iter(prompt17_failed_keys))
            if len(prompt17_failed_keys) == 1
            else False
        )
        prompt17_failed_index = (
            prompt17_sequence.index(prompt17_failed_key)
            if prompt17_failed_key
            else -1
        )
        prompt17_completed_prefix = (
            set(prompt17_sequence[:prompt17_failed_index])
            if prompt17_failed_key
            else set()
        )
        prompt17_uncommitted_suffix = (
            set(prompt17_sequence[prompt17_failed_index:])
            if prompt17_failed_key
            else prompt17_generators
        )
        prompt17_prefix_complete = bool(prompt17_failed_key) and all(
            self.checkpoint_ids.filtered(
                lambda checkpoint, key=generator_key: (
                    checkpoint.generator_key == key
                    and checkpoint.state == "done"
                )
            )
            for generator_key in prompt17_completed_prefix
        )
        prompt17_runtime_repair_checkpoint_shape = (
            bool(prompt17_failed_key)
            and checkpoint_generators
            == completed_prompt16_generators
            | prompt17_completed_prefix
            | {prompt17_failed_key}
        )
        prompt17_runtime_repair_adoption = (
            self.state == "failed"
            and prompt16_complete
            and prompt17_prefix_complete
            and not (generated_keys & prompt17_uncommitted_suffix)
            and prompt17_runtime_repair_checkpoint_shape
            and generated_keys
            <= completed_prompt16_generators | prompt17_completed_prefix
        )
        prompt15_complete = all(
            bool(self.checkpoint_ids.filtered(
                lambda checkpoint, generator_key=generator_key: (
                    checkpoint.generator_key == generator_key
                    and checkpoint.state == "done"
                )
            ))
            for generator_key in prompt15_generators
        )
        progressive_prompt16_adoption = (
            self.state in {"draft", "ready"}
            and prompt15_complete
            and checkpoint_generators == completed_prompt15_generators
            and generated_keys <= completed_prompt15_generators
            and not (checkpoint_generators & prompt16_generators)
            and not (generated_keys & prompt16_generators)
        )
        prompt16_encounter_complete = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: (
                checkpoint.generator_key == "operations.encounter"
                and checkpoint.state == "done"
            )
        ))
        prompt16_treatment_session_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: (
                checkpoint.generator_key == "operations.treatment_session"
                and checkpoint.state == "failed"
            )
        ))
        no_prompt16_treatment_session_references = not self.reference_ids.filtered(
            lambda reference: (
                reference.generator_key == "operations.treatment_session"
            )
        )
        prompt16_runtime_repair_checkpoint_shape = (
            checkpoint_generators
            <= (completed_prompt15_generators | prompt16_generators)
        )
        prompt16_runtime_repair_generated_shape = (
            generated_keys
            <= (completed_prompt15_generators | {"operations.encounter"})
        )
        prompt16_treatment_session_runtime_repair_adoption = (
            self.state == "failed"
            and prompt15_complete
            and prompt16_encounter_complete
            and prompt16_treatment_session_failed
            and no_prompt16_treatment_session_references
            and prompt16_runtime_repair_checkpoint_shape
            and prompt16_runtime_repair_generated_shape
        )
        prompt14_complete = all(
            bool(self.checkpoint_ids.filtered(
                lambda checkpoint, generator_key=generator_key: (
                    checkpoint.generator_key == generator_key
                    and checkpoint.state == "done"
                )
            ))
            for generator_key in prompt14_generators
        )
        progressive_prompt15_adoption = (
            self.state in {"draft", "ready"}
            and prompt14_complete
            and checkpoint_generators == completed_prompt14_generators
            and generated_keys <= completed_prompt14_generators
            and not (checkpoint_generators & prompt15_generators)
            and not (generated_keys & prompt15_generators)
        )
        prompt15_queue_triage_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: (
                checkpoint.generator_key == "operations.queue_triage"
                and checkpoint.state == "failed"
            )
        ))
        no_prompt15_references = not self.reference_ids.filtered(
            lambda reference: reference.generator_key == "operations.queue_triage"
        )
        prompt15_runtime_repair_checkpoint_shape = (
            checkpoint_generators
            <= (completed_prompt14_generators | prompt15_generators)
        )
        prompt15_runtime_repair_adoption = (
            self.state == "failed"
            and prompt14_complete
            and prompt15_queue_triage_failed
            and no_prompt15_references
            and prompt15_runtime_repair_checkpoint_shape
        )
        # A Ready run is allowed to change build contract only through this exact
        # Prompt-15 boundary; older failed/draft adoption routes must not apply.
        if self.state == "ready" and not (
            progressive_prompt23_adoption
            or prompt23_runtime_repair_adoption
            or progressive_prompt19_adoption
            or progressive_prompt18_adoption
            or progressive_prompt17_adoption
            or progressive_prompt16_adoption
            or progressive_prompt15_adoption
        ):
            return False
        prompt12_complete = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "resources.rooms_devices"
            and checkpoint.state == "done"
        ))
        progressive_prompt13_adoption = (
            prompt12_complete
            and generated_keys <= completed_prompt12_generators
            and checkpoint_generators <= completed_prompt12_generators
            and not (generated_keys & prompt13_generators)
            and not (checkpoint_generators & prompt13_generators)
            and "resources.rooms_devices" in checkpoint_generators
        )
        prompt13_complete = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "history.patient_longitudinal"
            and checkpoint.state == "done"
        ))
        progressive_prompt14_adoption = (
            prompt13_complete
            and generated_keys <= completed_prompt13_generators
            and checkpoint_generators <= completed_prompt13_generators
            and not (generated_keys & prompt14_generators)
            and not (checkpoint_generators & prompt14_generators)
            and "history.patient_longitudinal" in checkpoint_generators
        )
        progressive_prompt12_adoption = (
            generated_keys <= completed_prompt11_generators
            and checkpoint_generators <= completed_prompt11_generators
            and not (generated_keys & prompt12_generators)
            and not (checkpoint_generators & prompt12_generators)
            and "master.commercial" in checkpoint_generators
        )
        progressive_prompt11_adoption = (
            generated_keys <= completed_prompt10_generators
            and checkpoint_generators <= completed_prompt10_generators
            and not (generated_keys & prompt11_generators)
            and not (checkpoint_generators & prompt11_generators)
            and "patient.personas" in checkpoint_generators
        )
        progressive_prompt10_adoption = (
            generated_keys <= completed_prompt09_generators
            and checkpoint_generators <= completed_prompt09_generators
            and "patient.personas" not in generated_keys
            and "patient.personas" not in checkpoint_generators
        )
        prompt09_staff_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "workforce.staff"
            and checkpoint.state == "failed"
        ))
        no_workforce_references = not (generated_keys - foundation_generators)
        repair_safe_checkpoint_shape = not (
            checkpoint_generators - completed_prompt09_generators
        )
        runtime_repair_adoption = (
            prompt09_staff_failed
            and no_workforce_references
            and repair_safe_checkpoint_shape
        )
        prompt11_catalog_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "master.catalog"
            and checkpoint.state == "failed"
        ))
        no_prompt11_references = not (generated_keys & prompt11_generators)
        prompt11_acl_repair_checkpoint_shape = checkpoint_generators <= (
            completed_prompt10_generators | {"master.catalog"}
        )
        prompt11_acl_runtime_repair_adoption = (
            prompt11_catalog_failed
            and no_prompt11_references
            and prompt11_acl_repair_checkpoint_shape
            and "patient.personas" in checkpoint_generators
        )
        prompt11_commercial_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "master.commercial"
            and checkpoint.state == "failed"
        ))
        no_prompt11_commercial_references = not self.reference_ids.filtered(
            lambda reference: reference.generator_key == "master.commercial"
        )
        prompt11_commercial_acl_repair_checkpoint_shape = checkpoint_generators <= (
            completed_prompt10_generators | prompt11_generators
        )
        prompt11_commercial_acl_runtime_repair_adoption = (
            prompt11_commercial_failed
            and no_prompt11_commercial_references
            and prompt11_commercial_acl_repair_checkpoint_shape
            and "master.catalog" in checkpoint_generators
            and "master.consent" in checkpoint_generators
        )
        prompt12_resources_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "resources.rooms_devices"
            and checkpoint.state == "failed"
        ))
        no_prompt12_references = not self.reference_ids.filtered(
            lambda reference: reference.generator_key == "resources.rooms_devices"
        )
        prompt12_sequence_repair_checkpoint_shape = checkpoint_generators <= (
            completed_prompt11_generators | prompt12_generators
        )
        prompt12_runtime_repair_adoption = (
            prompt12_resources_failed
            and no_prompt12_references
            and prompt12_sequence_repair_checkpoint_shape
            and "master.commercial" in checkpoint_generators
        )
        prompt14_booking_failed = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "operations.booking"
            and checkpoint.state == "failed"
        ))
        prompt14_referral_complete = bool(self.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.generator_key == "operations.referral"
            and checkpoint.state == "done"
        ))
        no_prompt14_booking_references = not self.reference_ids.filtered(
            lambda reference: reference.generator_key == "operations.booking"
        )
        prompt14_booking_repair_checkpoint_shape = checkpoint_generators <= (
            completed_prompt13_generators | prompt14_generators
        )
        prompt14_booking_runtime_repair_adoption = (
            prompt14_booking_failed
            and prompt14_referral_complete
            and no_prompt14_booking_references
            and prompt14_booking_repair_checkpoint_shape
            and "history.patient_longitudinal" in checkpoint_generators
        )
        if not (
            prompt23_runtime_repair_adoption
            or progressive_prompt23_adoption
            or prompt19_runtime_repair_adoption
            or progressive_prompt19_adoption
            or prompt18_runtime_repair_adoption
            or progressive_prompt18_adoption
            or prompt17_runtime_repair_adoption
            or progressive_prompt17_adoption
            or prompt16_treatment_session_runtime_repair_adoption
            or progressive_prompt16_adoption
            or prompt15_runtime_repair_adoption
            or progressive_prompt15_adoption
            or prompt14_booking_runtime_repair_adoption
            or progressive_prompt14_adoption
            or progressive_prompt13_adoption
            or prompt12_runtime_repair_adoption
            or progressive_prompt12_adoption
            or progressive_prompt11_adoption
            or progressive_prompt10_adoption
            or prompt11_acl_runtime_repair_adoption
            or prompt11_commercial_acl_runtime_repair_adoption
            or runtime_repair_adoption
        ):
            return False
        changed = (
            self.generator_version != GENERATOR_VERSION
            or self.source_fingerprint != AUTHORITATIVE_SOURCE_FINGERPRINT
            or self.expected_suite_fingerprint != EXPECTED_SUITE_FINGERPRINT
        )
        if not changed:
            return False
        if prompt23_runtime_repair_adoption:
            adoption_label = _(
                "Prompt 23 stage-aware acceptance repair adopted after rolled-back %(generator)s failure"
            ) % {"generator": prompt23_failed_key}
        elif progressive_prompt23_adoption:
            adoption_label = "Prompt 23 acceptance contract adopted after completed 29-generator Prompt-22 scope"
        elif prompt19_runtime_repair_adoption:
            adoption_label = _(
                "Prompt 19 stage-aware whole-path runtime repair adopted after "
                "rolled-back %(generator)s failure"
            ) % {"generator": prompt19_failed_key}
        elif progressive_prompt19_adoption:
            adoption_label = "Prompt 19 progressive contract adopted after completed Prompt-18 scope"
        elif prompt18_runtime_repair_adoption:
            adoption_label = _(
                "Prompt 18 stage-aware whole-path runtime repair adopted after "
                "rolled-back %(generator)s failure"
            ) % {"generator": prompt18_failed_key}
        elif progressive_prompt18_adoption:
            adoption_label = "Prompt 18 progressive contract adopted after completed Prompt-17 scope"
        elif prompt17_runtime_repair_adoption:
            adoption_label = _(
                "Prompt 17 stage-aware whole-path runtime repair adopted after "
                "rolled-back %(generator)s failure"
            ) % {"generator": prompt17_failed_key}
        elif progressive_prompt17_adoption:
            adoption_label = "Prompt 17 progressive contract adopted after completed Prompt-16 scope"
        elif prompt16_treatment_session_runtime_repair_adoption:
            adoption_label = "Prompt 16 Treatment Session business-API ACL repair adopted after rolled-back treatment-session failure"
        elif progressive_prompt16_adoption:
            adoption_label = "Prompt 16 progressive contract adopted after completed Prompt-15 scope"
        elif prompt15_runtime_repair_adoption:
            adoption_label = "Prompt 15 queue-stage Odoo-19 domain repair adopted after rolled-back queue/triage failure"
        elif progressive_prompt15_adoption:
            adoption_label = "Prompt 15 progressive contract adopted after completed Prompt-14 scope"
        elif prompt14_booking_runtime_repair_adoption:
            adoption_label = "Prompt 14 bounded runtime-repair contract adopted after operations.booking rollback"
        elif progressive_prompt14_adoption:
            adoption_label = "Prompt 14 progressive contract adopted after completed Prompt-13 scope"
        elif progressive_prompt13_adoption:
            adoption_label = "Prompt 13 progressive contract adopted after completed Prompt-12 scope"
        elif prompt12_runtime_repair_adoption:
            adoption_label = "Prompt 12 bounded runtime-repair contract adopted after resources.rooms_devices rollback"
        elif progressive_prompt12_adoption:
            adoption_label = "Prompt 12 progressive contract adopted after completed Prompt-11 scope"
        elif progressive_prompt11_adoption:
            adoption_label = "Prompt 11 progressive contract adopted after completed Prompt-10 scope"
        elif progressive_prompt10_adoption:
            adoption_label = "Prompt 10 progressive contract adopted after completed Prompt-09 scope"
        elif prompt11_acl_runtime_repair_adoption:
            adoption_label = "Prompt 11 functional-ACL runtime-repair contract adopted after master.catalog rollback"
        elif prompt11_commercial_acl_runtime_repair_adoption:
            adoption_label = "Prompt 11 membership ACL runtime-repair contract adopted after master.commercial rollback"
        else:
            adoption_label = "Prompt 09 bounded runtime-repair contract adopted"
        self.write({
            "generator_version": GENERATOR_VERSION,
            "source_fingerprint": AUTHORITATIVE_SOURCE_FINGERPRINT,
            "expected_suite_fingerprint": EXPECTED_SUITE_FINGERPRINT,
            "compatibility_state": "unchecked",
            "compatibility_message": False,
            "patch_compatibility_status": adoption_label,
        })
        self._log_control_event(
            "info",
            "adopt_build_contract",
            adoption_label,
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
        self.write({"state": "validating"})
        try:
            results = DemoValidationService(self.env).validate_full_readiness(self)
        except Exception as exc:
            self.write({"state": "failed"})
            self._log_control_event(
                "error",
                "validate",
                f"Validation failed with {exc.__class__.__name__}: {exc}",
            )
            raise
        failed = any(result.state == "fail" for result in results)
        next_state = "failed" if failed else "ready"
        self.write({
            "state": next_state,
            "validation_status": "fail" if failed else self.validation_status,
        })
        self._log_control_event(
            "error" if failed else "info",
            "validate",
            "Enterprise readiness validation failed."
            if failed
            else "READY FOR DEMO",
        )
        return self._display_notification(
            _("Validation Failed") if failed else _("READY FOR DEMO"),
            _("Enterprise readiness validation failed. Open Validation Results for the complete evidence.")
            if failed
            else _("All critical structural, temporal, workflow, journey, exception, analytics, integrity, reset, regeneration, and fresh-database readiness checks passed."),
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



