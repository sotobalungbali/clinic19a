"""Source, identity and registered-generator validation for ClinicOne demo runs."""

from .checkpoint_service import DemoCheckpointService
from .context import GenerationContext
from .fingerprint_service import SourceFingerprintService
from .generator_registry import GENERATOR_REGISTRY
from .logging_service import DemoLoggingService
from .reference_service import DemoReferenceService
from .safe_mode_service import DemoSafeModeService
from .scenario_registry import ScenarioRegistry
from .seed_service import DeterministicSeedService


class DemoValidationService:
    def __init__(self, env):
        self.env = env

    def _result(self, run, key, category, severity, state, message, **extra):
        model = self.env["clinic.demo.validation.result"]
        result = model.search(
            [("run_id", "=", run.id), ("check_key", "=", key)],
            limit=1,
        )
        values = {
            "run_id": run.id,
            "check_key": key,
            "category": category,
            "severity": severity,
            "state": state,
            "message": message,
        }
        values.update(extra)
        if result:
            result.write(values)
            return result
        return model.create(values)

    def _context(self, run, scenario):
        return GenerationContext(
            env=self.env,
            run=run,
            profile=run.profile,
            scenario=scenario,
            seed_service=DeterministicSeedService(run.deterministic_seed),
            reference_service=DemoReferenceService(self.env),
            safe_mode_service=DemoSafeModeService(run),
            checkpoint_service=DemoCheckpointService(self.env),
            logging_service=DemoLoggingService(self.env),
        )

    def _validate_registered_generators(self, run):
        GENERATOR_REGISTRY.validate()
        results = []

        generators = sorted(
            GENERATOR_REGISTRY.all(),
            key=lambda generator: (
                generator.phase or "",
                generator.sequence,
                generator.key,
            ),
        )
        for generator in generators:
            checkpoint = run.checkpoint_ids.filtered(
                lambda item: item.generator_key == generator.key and item.state == "done"
            )[:1]
            if not checkpoint:
                continue

            scenario = ScenarioRegistry.get(generator.scenario_keys[0])
            try:
                warnings = generator().validate(
                    self._context(run, scenario),
                    scenario,
                ) or []
            except Exception as exc:
                results.append(
                    self._result(
                        run,
                        f"generator.{generator.key}",
                        "foundation",
                        "critical",
                        "fail",
                        f"{generator.key} validation failed: {exc}",
                        generator_key=generator.key,
                        scenario_key=scenario.key,
                    )
                )
                continue

            results.append(
                self._result(
                    run,
                    f"generator.{generator.key}",
                    "foundation",
                    "warning" if warnings else "info",
                    "warning" if warnings else "pass",
                    "; ".join(warnings)
                    if warnings
                    else f"{generator.key} validation passed.",
                    generator_key=generator.key,
                    scenario_key=scenario.key,
                )
            )
        return results

    def validate_identity_foundation(self, run):
        run.ensure_one()

        compatibility = SourceFingerprintService(self.env).check_compatibility(run=run)
        results = [
            self._result(
                run,
                "source.compatibility",
                "source",
                "critical",
                "pass" if compatibility["compatible"] else "fail",
                compatibility["message"],
            )
        ]

        references = self.env["clinic.demo.reference"].search(
            [("run_id", "=", run.id)]
        )
        keys = references.mapped("demo_key")
        duplicates = len(keys) != len(set(keys))
        results.append(
            self._result(
                run,
                "identity.unique_demo_keys",
                "identity",
                "critical",
                "fail" if duplicates else "pass",
                "Duplicate demo keys found."
                if duplicates
                else "Demo keys are unique within the run.",
            )
        )

        missing = references.filtered(lambda ref: ref.record_status == "missing")
        results.append(
            self._result(
                run,
                "identity.missing_references",
                "identity",
                "warning" if missing else "info",
                "warning" if missing else "pass",
                f"{len(missing)} missing demo reference(s) require repair."
                if missing
                else "No missing demo references are currently registered.",
            )
        )

        results.extend(self._validate_registered_generators(run))

        critical_failure = any(
            result.state == "fail" and result.severity in {"error", "critical"}
            for result in results
        )
        warnings = any(result.state == "warning" for result in results)
        run.validation_status = (
            "fail" if critical_failure else "warning" if warnings else "pass"
        )
        return results
