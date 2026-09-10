#!/usr/bin/env python3
"""Standalone MASTER PROMPT 19 whole-path source contracts."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "generators/exception.py"


class TestPrompt19SourceContracts(unittest.TestCase):
    def test_version_registry_and_order(self):
        manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.46")
        source = SOURCE.read_text()
        for token in (
            'key = "exception.feedback"', 'depends_on = ("commercial.ap",)',
            'key = "exception.incident_quality"', 'depends_on = ("exception.feedback",)',
            'key = "digital.ecommerce_marketing_portal"',
            'depends_on = ("exception.incident_quality",)',
        ):
            self.assertIn(token, source)

    def test_whole_path_contracts_and_safe_mode(self):
        source = SOURCE.read_text()
        for token in (
            "CONTRACTS =", "relations =", "check_access(operation)",
            "ctx.run.safe_mode", "DEMO-FB-001", "DEMO-QUAL-001",
            "DEMO-INC-001", "DEMO-API-001", "attempt_count == 0",
            "not event.delivery_ids",
        ):
            self.assertIn(token, source)

    def test_deterministic_business_keys_bypass_owner_sequences(self):
        source = SOURCE.read_text()
        for key in ("DEMO-FB-001", "DEMO-QUAL-001", "DEMO-INC-001", "DEMO-API-001"):
            self.assertIn(f'"name": "{key}"', source)
        for forbidden in ("next_by_code", "uuid4", ".sudo(", ".cr.commit(", ".execute("):
            self.assertNotIn(forbidden, source)

    def test_official_workflows_are_used_without_external_dispatch(self):
        source = SOURCE.read_text()
        for method in (
            "action_activate()", "action_submit()", "action_escalate()",
            "action_start()", "action_submit_review()", "action_report()",
            "action_start_triage()", "action_review_reportability()",
            "action_start_investigation()",
        ):
            self.assertIn(method, source)
        for forbidden in ("action_queue()", "_attempt_delivery(", "_cron_dispatch("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()





