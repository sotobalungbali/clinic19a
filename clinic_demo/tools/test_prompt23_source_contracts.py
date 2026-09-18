import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Prompt23SourceContracts(unittest.TestCase):
    def test_version_and_final_registry(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "19.0.1.0.61")
        source = (ROOT / "generators/validation/acceptance.py").read_text(encoding="utf-8")
        for key in (
            "validation.structural", "validation.temporal", "validation.workflow",
            "validation.journey_exception", "validation.analytics_evidence",
            "validation.integrity_reset_regeneration",
        ):
            self.assertIn(f'key = "{key}"', source)

    def test_acceptance_gates_are_read_only_business_checks(self):
        source = (ROOT / "generators/validation/acceptance.py").read_text(encoding="utf-8")
        for forbidden in (".create(", ".write(", ".unlink(", ".cr.commit(", ".execute(", "next_by_code", "uuid4", "date.today()", "datetime.now()"):
            self.assertNotIn(forbidden, source)
        self.assertIn(".sudo().browse(reference.res_id).exists()", source)
        self.assertIn("owned_models = ()", source)

    def test_temporal_gate_uses_owner_model_semantics(self):
        source = (ROOT / "generators/validation/acceptance.py").read_text(encoding="utf-8")
        self.assertIn('"clinic.triage.session": ("start_datetime", "end_datetime", "non_decreasing")', source)
        self.assertIn('"booking.booking": ("start_datetime", "end_datetime", "strict")', source)
        self.assertIn('"clinical.imaging.device.downtime": (', source)
        self.assertNotIn('if {"start_datetime", "end_datetime"} <= set(record._fields)', source)
        self.assertIn('rule == "strict" and end == start', source)

    def test_validation_button_reexecutes_all_readiness_gates(self):
        source = (ROOT / "generators/validation/acceptance.py").read_text(encoding="utf-8")
        self.assertIn("self.generate(ctx, scenario)", source)
        run = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        self.assertIn('else _("READY FOR DEMO")', run)

    def test_reset_is_preflighted_and_atomic(self):
        source = (ROOT / "services/reset_service.py").read_text(encoding="utf-8")
        self.assertIn("Reset whole-path preflight failed", source)
        self.assertIn("Atomic reset failed at", source)
        self.assertNotIn("with self.env.cr.savepoint():\n                    result = self.reset_reference", source)

    def test_reset_unknowns_remain_blocked(self):
        source = (ROOT / "services/reset_policy_registry.py").read_text(encoding="utf-8")
        self.assertIn("Unknown models are blocked from reset", source)
        self.assertIn('"clinic.analytics.forecast", "clinic.analytics.snapshot"', source)
        self.assertIn('"clinic.appointment",', source)
        self.assertNotIn('{{model_name}}', source)
        self.assertNotIn('{{state!r}}', source)

    def test_owner_created_appointment_references_have_reset_coverage(self):
        queue_source = (ROOT / "generators/operations/queue_triage.py").read_text(encoding="utf-8")
        reset_source = (ROOT / "services/reset_policy_registry.py").read_text(encoding="utf-8")
        self.assertIn('booking._create_or_link_appointment()', queue_source)
        self.assertIn('spec["appointment_key"]', queue_source)
        self.assertIn('"clinic.appointment",', reset_source)


if __name__ == "__main__":
    unittest.main()
















