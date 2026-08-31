
"""Bounded Control Center execution for registered ClinicOne demo generators.

The engine executes only the bounded generators registered by completed Master
Prompts, persists one checkpoint per generator/scenario, and stops on the first
unknown runtime root cause.
"""

import traceback

from odoo import _, fields
from odoo.exceptions import AccessError

from .checkpoint_service import DemoCheckpointService
from .context import GenerationContext
from .logging_service import DemoLoggingService
from .reference_service import DemoReferenceService
from .safe_mode_service import DemoSafeModeService
from .scenario_registry import ScenarioRegistry
from .seed_service import DeterministicSeedService


EXPECTED_FINAL_GENERATOR_COUNT = 35


class DemoExecutionEngine:
    def __init__(self, env):
        self.env = env
        self.checkpoints = DemoCheckpointService(env)
        self.logging = DemoLoggingService(env)

    @staticmethod
    def _notification(title, message, notification_type="info", sticky=False):
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

    def _registered_generators(self):
        from .generator_registry import GENERATOR_REGISTRY

        GENERATOR_REGISTRY.validate()
        return tuple(
            sorted(
                GENERATOR_REGISTRY.all(),
                key=lambda generator: (
                    generator.phase or "",
                    generator.sequence,
                    generator.key,
                ),
            )
        )

    def _generator_map(self):
        return {generator.key: generator for generator in self._registered_generators()}

    def _scenario_for(self, generator):
        if not generator.scenario_keys:
            raise ValueError(f"Generator {generator.key} has no registered scenario.")
        return ScenarioRegistry.get(generator.scenario_keys[0])

    def _checkpoint_key(self, generator, scenario):
        return f"{generator.phase}:{generator.key}:{scenario.key}"

    def _context(self, run, scenario):
        return GenerationContext(
            env=self.env,
            run=run,
            profile=run.profile,
            scenario=scenario,
            seed_service=DeterministicSeedService(run.deterministic_seed),
            reference_service=DemoReferenceService(self.env),
            safe_mode_service=DemoSafeModeService(run),
            checkpoint_service=self.checkpoints,
            logging_service=self.logging,
        )

    def _require_generator_groups(self, generator):
        # The Control Center explicitly authorizes Odoo System Administrators.
        # Do not force them to duplicate every functional role merely to execute
        # a bounded demo generator; ORM ACL/record rules still apply normally.
        if self.env.user.has_group("base.group_system"):
            return True

        missing = []
        for xmlid in generator.required_groups:
            if not self.env.user.has_group(xmlid):
                group = self.env.ref(xmlid, raise_if_not_found=False)
                missing.append(group.display_name if group else xmlid)
        if missing:
            raise AccessError(
                _(
                    "Generator %(generator)s requires: %(groups)s. "
                    "Assign the owning ClinicOne role instead of bypassing core security."
                )
                % {
                    "generator": generator.key,
                    "groups": ", ".join(missing),
                }
            )

    def _upsert_validation(self, run, generator, state, message, severity="info"):
        model = self.env["clinic.demo.validation.result"]
        check_key = f"generator.{generator.key}"
        result = model.search(
            [("run_id", "=", run.id), ("check_key", "=", check_key)],
            limit=1,
        )
        values = {
            "run_id": run.id,
            "check_key": check_key,
            "category": generator.phase or "generation",
            "severity": severity,
            "state": state,
            "generator_key": generator.key,
            "scenario_key": self._scenario_for(generator).key,
            "message": message,
        }
        if result:
            result.write(values)
            return result
        return model.create(values)

    def _refresh_run_counters(self, run):
        done = run.checkpoint_ids.filtered(lambda checkpoint: checkpoint.state == "done")
        values = {}
        for key in ("created", "reused", "updated", "skipped", "warning"):
            values[f"{key}_count"] = sum(done.mapped(f"{key}_count"))
        values["error_count"] = sum(run.checkpoint_ids.mapped("error_count"))
        run.write(values)

    def _dependencies_done(self, run, generator):
        for dependency in generator.depends_on:
            checkpoint = run.checkpoint_ids.filtered(
                lambda item: item.generator_key == dependency and item.state == "done"
            )
            if not checkpoint:
                return False, dependency
        return True, False

    def _execute_generator(self, run, generator, force=False, repair=False):
        scenario = self._scenario_for(generator)
        checkpoint = self.checkpoints.ensure(
            run=run,
            checkpoint_key=self._checkpoint_key(generator, scenario),
            phase_key=generator.phase,
            generator_key=generator.key,
            sequence=generator.sequence,
            scenario_key=scenario.key,
        )

        if checkpoint.state == "done" and not force and not repair:
            return True, "already_done"

        dependencies_ok, missing_dependency = self._dependencies_done(run, generator)
        if not dependencies_ok:
            message = (
                f"Generator {generator.key} is waiting for dependency "
                f"{missing_dependency}."
            )
            checkpoint.write({"state": "pending", "error_summary": message})
            return False, message

        try:
            self._require_generator_groups(generator)
            self.checkpoints.start(checkpoint)
            run.write({
                "state": "generating",
                "current_phase": generator.phase,
                "current_scenario": scenario.key,
                "started_at": run.started_at or fields.Datetime.now(),
            })

            ctx = self._context(run, scenario)
            with self.env.cr.savepoint():
                instance = generator()
                counters = (
                    instance.repair_missing(ctx, scenario)
                    if repair
                    else instance.generate(ctx, scenario)
                )
                warnings = instance.validate(ctx, scenario)
        except Exception as exc:
            self.checkpoints.fail(checkpoint, exc)
            self.logging.log(
                run=run,
                level="error",
                checkpoint=checkpoint,
                phase_key=generator.phase,
                generator_key=generator.key,
                scenario_key=scenario.key,
                operation="repair_missing" if repair else "generate",
                message=(
                    f"{generator.key} failed with {exc.__class__.__name__}: {exc}"
                ),
                exception_class=exc.__class__.__name__,
                traceback_excerpt=traceback.format_exc(),
            )
            self._upsert_validation(
                run,
                generator,
                "fail",
                f"{generator.key} failed: {exc}",
                severity="critical",
            )
            self._refresh_run_counters(run)
            return False, str(exc)

        counters = counters or {}
        for warning in warnings or []:
            counters["warning"] = int(counters.get("warning", 0)) + 1
            self.logging.log(
                run=run,
                level="warning",
                checkpoint=checkpoint,
                phase_key=generator.phase,
                generator_key=generator.key,
                scenario_key=scenario.key,
                operation="validate",
                message=warning,
            )

        self.checkpoints.complete(checkpoint, counters)
        self._upsert_validation(
            run,
            generator,
            "warning" if warnings else "pass",
            "; ".join(warnings)
            if warnings
            else f"{generator.key} generated and validated successfully.",
            severity="warning" if warnings else "info",
        )
        self.logging.log(
            run=run,
            level="info",
            checkpoint=checkpoint,
            phase_key=generator.phase,
            generator_key=generator.key,
            scenario_key=scenario.key,
            operation="repair_missing" if repair else "generate",
            message=(
                f"{generator.key} completed: "
                f"created={counters.get('created', 0)}, "
                f"reused={counters.get('reused', 0)}, "
                f"updated={counters.get('updated', 0)}, "
                f"warnings={counters.get('warning', 0)}."
            ),
        )
        self._refresh_run_counters(run)
        return True, "done"

    def _finish_registered_scope(self, run, generators):
        failed = run.checkpoint_ids.filtered(lambda checkpoint: checkpoint.state == "failed")
        if failed:
            run.write({"state": "failed"})
            first_failed = failed.sorted(key=lambda checkpoint: (checkpoint.sequence, checkpoint.id))[:1]
            first = first_failed[0]
            summary = (first.error_summary or _("Unknown runtime error")).strip()
            if len(summary) > 600:
                summary = summary[:597] + "..."
            return self._notification(
                _("Generation Paused"),
                _(
                    "%(count)s checkpoint(s) failed. First failure: %(generator)s. "
                    "%(summary)s Open Logs for the sanitized traceback."
                )
                % {
                    "count": len(failed),
                    "generator": first.generator_key,
                    "summary": summary,
                },
                "danger",
                sticky=True,
            )

        run.write({
            "state": "draft",
            "current_scenario": False,
        })

        count = len(generators)
        if count < EXPECTED_FINAL_GENERATOR_COUNT:
            return self._notification(
                _("Registered Dataset Scope Complete"),
                _(
                    "%(count)s bounded generator(s) completed. Foundation, organization, "
                    "workforce/provider, patient-persona, Prompt-11 clinical/commercial master, "
                    "Prompt-12 room/device/resource scheduling, Prompt-13 longitudinal historical "
                    "backbone, and Prompt-14 referral/booking front-office operations registered so far "
                    "are now real demo data. The full "
                    "35-generator enterprise registry is completed progressively by later Master Prompts."
                )
                % {"count": count},
                "success",
                sticky=True,
            )

        return self._notification(
            _("Generation Complete"),
            _("All registered enterprise generators completed. Run validation next."),
            "success",
            sticky=True,
        )

    def _execute_scope(self, run, generators, force=False):
        for generator in generators:
            ok, _message = self._execute_generator(
                run,
                generator,
                force=force,
                repair=False,
            )
            if not ok:
                break
        return self._finish_registered_scope(run, generators)

    def request_full_generation(self, run):
        run.ensure_one()
        generators = self._registered_generators()
        if not generators:
            return self._notification(
                _("No Generators Registered"),
                _("No executable domain generator is registered."),
                "warning",
                sticky=True,
            )
        return self._execute_scope(run, generators)

    def request_current_phase(self, run):
        run.ensure_one()
        generators = self._registered_generators()
        if not generators:
            return self._notification(
                _("No Generators Registered"),
                _("No executable domain generator is registered."),
                "warning",
            )

        phases = sorted({generator.phase for generator in generators})
        phase = run.current_phase if run.current_phase in phases else phases[0]
        phase_generators = tuple(
            generator for generator in generators if generator.phase == phase
        )
        return self._execute_scope(run, phase_generators)

    def continue_generation(self, run):
        run.ensure_one()
        generators = self._registered_generators()
        pending_or_failed = []
        for generator in generators:
            checkpoints = run.checkpoint_ids.filtered(
                lambda checkpoint: checkpoint.generator_key == generator.key
            )
            if not checkpoints or checkpoints.filtered(
                lambda checkpoint: checkpoint.state in {"pending", "failed"}
            ):
                pending_or_failed.append(generator)

        if not pending_or_failed:
            return self._notification(
                _("Nothing Pending"),
                _("All currently registered generator checkpoints are complete."),
                "info",
            )
        return self._execute_scope(run, tuple(pending_or_failed), force=True)

    def repair_missing(self, run, references):
        run.ensure_one()
        generator_map = self._generator_map()
        keys = sorted(
            {
                reference.generator_key
                for reference in references
                if reference.generator_key in generator_map
            }
        )
        if not keys:
            return self._notification(
                _("No Repair Generator"),
                _("No registered generator owns the missing references."),
                "warning",
                sticky=True,
            )

        repaired = 0
        for key in keys:
            generator = generator_map[key]
            ok, _message = self._execute_generator(
                run,
                generator,
                force=True,
                repair=True,
            )
            if not ok:
                return self._finish_registered_scope(run, tuple(generator_map[k] for k in keys))
            repaired += 1

        return self._notification(
            _("Missing Records Repaired"),
            _("%s owning generator(s) completed missing-record repair.") % repaired,
            "success",
            sticky=True,
        )



