import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generators/management/reports.py"

class Prompt21SourceContracts(unittest.TestCase):
    def test_version_and_registry_budget(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        self.assertEqual(manifest["version"], "19.0.1.0.46")
        self.assertIn('"management.reports" not in registered_generator_keys', (ROOT / "tools/clinic_demo_guardrail.py").read_text())

    def test_all_native_reports_have_explicit_contracts(self):
        text = GENERATOR.read_text()
        tree = ast.parse(text)
        specs = next(node.value for node in tree.body if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "REPORT_SPECS" for target in node.targets))
        self.assertEqual(len(ast.literal_eval(specs)), 19)
        self.assertIn("REPORT_ENGINE_METHODS", text)
        self.assertIn("REPORT_MODEL_CONTRACTS", text)

    def test_whole_path_preflight_before_report_mutation(self):
        text = GENERATOR.read_text()
        generate = text[text.index("    def generate("):text.index("    def validate(")]
        self.assertLess(generate.index("self._whole_path_preflight"), generate.index("self._ensure_run"))
        self.assertIn("check_access", text)
        self.assertIn("missing report definition", text)
        self.assertIn("has no declared report engine", text)

    def test_owner_api_and_deterministic_identity(self):
        text = GENERATOR.read_text()
        self.assertIn('"name": key', text)
        self.assertIn("run.action_generate()", text)
        self.assertNotIn("next_by_code", text)
        for forbidden in ("uuid", ".sudo(", ".commit(", "cr.execute"):
            self.assertNotIn(forbidden, text)

    def test_source_backed_validation(self):
        text = GENERATOR.read_text()
        self.assertIn("unexpectedly zero", text)
        self.assertIn("contains details without source provenance", text)
        self.assertIn("run.metric_ids", text)
        self.assertIn("run.csv_file", text)

    def test_required_coverage_matrix(self):
        matrix = (ROOT / "docs/CLINIC_DEMO_REPORT_COVERAGE_MATRIX.md").read_text()
        self.assertIn("| Report | Addon | Source model | Domain/filter | Required demo source | Expected result | Status |", matrix)
        self.assertIn("Coverage-only", matrix)
        self.assertIn("No fake tax, cash-flow, or adverse-event record", matrix)

if __name__ == "__main__":
    unittest.main()



