"""Prompt-06 validation foundation: identity and compatibility checks only."""

from .fingerprint_service import SourceFingerprintService


class DemoValidationService:
    def __init__(self, env):
        self.env = env

    def _result(self, run, key, category, severity, state, message, **extra):
        values = {
            "run_id": run.id,
            "check_key": key,
            "category": category,
            "severity": severity,
            "state": state,
            "message": message,
        }
        values.update(extra)
        return self.env["clinic.demo.validation.result"].create(values)

    def validate_identity_foundation(self, run):
        run.ensure_one()
        self.env["clinic.demo.validation.result"].search(
            [("run_id", "=", run.id), ("category", "in", ["source", "identity"])]
        ).unlink()

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
                "Duplicate demo keys found." if duplicates else "Demo keys are unique within the run.",
            )
        )
        run.validation_status = (
            "fail" if any(result.state == "fail" for result in results) else "pass"
        )
        return results
