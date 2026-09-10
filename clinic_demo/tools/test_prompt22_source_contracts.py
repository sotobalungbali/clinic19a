import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generators/management/dashboard_analytics.py"
DASHBOARD_ROOT = ROOT.parent / "clinic_dashboard"

class Prompt22SourceContracts(unittest.TestCase):
    def test_versions_and_registry_budget(self):
        self.assertEqual(ast.literal_eval((ROOT / "__manifest__.py").read_text())["version"], "19.0.1.0.46")
        self.assertEqual(ast.literal_eval((DASHBOARD_ROOT / "__manifest__.py").read_text())["version"], "19.0.1.0.1")
        self.assertIn("Prompt-23 expected 35 registered generators", (ROOT / "tools/clinic_demo_guardrail.py").read_text())

    def test_two_explicit_generator_owners(self):
        text = GENERATOR.read_text()
        self.assertIn('key = "management.dashboard"', text)
        self.assertIn('depends_on = ("management.reports",)', text)
        self.assertIn('key = "management.analytics"', text)
        self.assertIn('depends_on = ("management.dashboard",)', text)

    def test_full_path_contracts_precede_mutation(self):
        text = GENERATOR.read_text()
        self.assertIn("DASHBOARD_CONTRACTS", text)
        self.assertIn("ANALYTICS_CONTRACTS", text)
        self.assertIn("expected 17 active Analytics KPIs", text)
        self.assertIn("has no fixed-source adapter", text)
        self.assertIn("check_access", text)
        self.assertIn("publish_integration_events must be disabled", text)

    def test_deterministic_identity_extension(self):
        board = (DASHBOARD_ROOT / "models/dashboard_board.py").read_text()
        self.assertIn("snapshot_name=None", board)
        self.assertIn('"name": snapshot_name or "/"', board)
        text = GENERATOR.read_text()
        self.assertIn("snapshot_name=key", text)
        self.assertIn('"name": key', text)
        for forbidden in ("next_by_code", "uuid", ".sudo(", "cr.execute", ".commit("):
            self.assertNotIn(forbidden, text)

    def test_multi_period_and_forecast_contract(self):
        text = GENERATOR.read_text()
        self.assertIn('(\"HISTORICAL\", -365, -181)', text)
        self.assertIn('(\"PRIOR\", -180, -1)', text)
        self.assertIn('(\"CURRENT_FUTURE\", 0, 90)', text)
        self.assertIn('"history_periods": 12', text)
        self.assertIn('"horizon_periods": 3', text)
        self.assertIn('"method": "linear_trend"', text)

    def test_no_fake_kpi_validation(self):
        text = GENERATOR.read_text()
        self.assertIn("without Report provenance", text)
        self.assertIn("without fixed-source provenance", text)
        self.assertIn("Current Analytics snapshot has no populated source", text)

if __name__ == "__main__":
    unittest.main()



