import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "generators/operations/future_pipeline.py"

class Prompt20SourceContracts(unittest.TestCase):
    def test_version_and_registry_budget(self):
        self.assertEqual(ast.literal_eval((ROOT / "__manifest__.py").read_text())["version"], "19.0.1.0.46")
        self.assertIn('"operations.future_pipeline" not in registered_generator_keys', (ROOT / "tools/clinic_demo_guardrail.py").read_text())

    def test_explicit_temporal_matrix_and_dependencies(self):
        text = PIPELINE.read_text()
        self.assertIn("PIPELINE_OFFSETS = (1, 7, 14, 30, 60, 90)", text)
        self.assertIn('key = "operations.future_pipeline"', text)
        self.assertIn('phase = "20_pipeline"', text)
        self.assertIn('depends_on = ("digital.ecommerce_marketing_portal", "operations.booking", "clinical.telemedicine")', text)

    def test_whole_path_contract_precedes_mutation(self):
        text = PIPELINE.read_text()
        generate = text[text.index("    def generate("):text.index("    def validate(")]
        self.assertLess(generate.index("self._whole_path_preflight(ctx)"), generate.index("self._ensure_followup"))
        self.assertIn("PIPELINE_CONTRACTS", text)
        self.assertIn("PIPELINE_RELATIONS", text)
        self.assertIn("check_access", text)

    def test_deterministic_identity_and_no_external_delivery(self):
        text = PIPELINE.read_text()
        self.assertIn('"reference": key', text)
        self.assertIn('"auto_send": False', text)
        self.assertIn('"channel": "internal"', text)
        for forbidden in ("next_by_code", "uuid", ".sudo(", ".commit(", "cr.execute"):
            self.assertNotIn(forbidden, text)

    def test_future_records_cannot_masquerade_as_completed(self):
        text = PIPELINE.read_text()
        self.assertIn('task.state not in {"pending", "scheduled"}', text)
        self.assertIn("task.completed_at or task.sent_at", text)
        self.assertIn("line.expected_date > anchor", text)
        self.assertIn("item.start_datetime.date() > anchor", text)

    def test_progress_notification_mentions_prompt20(self):
        self.assertIn("Prompt-20 deterministic 90-day future pipeline", (ROOT / "services/execution_engine.py").read_text())

if __name__ == "__main__":
    unittest.main()




