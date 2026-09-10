



"""Static regression contract for ClinicOne MASTER PROMPT 15."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestPrompt15SourceContract(unittest.TestCase):
    def test_generator_contract(self):
        path = ROOT / "generators" / "operations" / "queue_triage.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        target = None
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            values = {}
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        try:
                            values[t.id] = ast.literal_eval(stmt.value)
                        except Exception:
                            pass
            if values.get("key") == "operations.queue_triage":
                target = values
                break
        self.assertIsNotNone(target)
        self.assertEqual(target["phase"], "15_arrival")
        self.assertEqual(target["sequence"], 620)
        self.assertEqual(target["depends_on"], ("operations.booking",))

    def test_no_forbidden_demo_bypasses(self):
        source = (ROOT / "generators" / "operations" / "queue_triage.py").read_text(encoding="utf-8")
        for forbidden in (".sudo(", "create_date", "write_date", "_cr.execute", "env.cr"):
            self.assertNotIn(forbidden, source)
        for owner_method in (
            "_create_or_link_appointment",
            "action_issue",
            "action_call",
            "action_create_queue",
            "action_assign_room",
            "action_start",
            "action_done",
            "action_serve",
            "action_complete",
        ):
            self.assertIn(owner_method, source)
        self.assertNotIn('"is_abnormal":', source)
        self.assertIn("queue.action_assign_room(clinic_room.id)", source)

    def test_prompt15_registry_and_progressive_adoption_contract(self):
        scenario = (ROOT / "services" / "scenario_registry.py").read_text(encoding="utf-8")
        resources = (ROOT / "generators" / "resources" / "rooms_devices.py").read_text(encoding="utf-8")
        demo_run = (ROOT / "models" / "demo_run.py").read_text(encoding="utf-8")
        execution = (ROOT / "services" / "execution_engine.py").read_text(encoding="utf-8")

        self.assertIn('"key": "SCN-QUEUE-01"', scenario) if '"key": "SCN-QUEUE-01"' in scenario else self.assertIn("SCN-QUEUE-01", scenario)
        self.assertIn("operations.queue_triage", scenario)
        self.assertIn("15_arrival", scenario)
        self.assertIn('scenario_keys = ("SCN-BOOKING-TODAY-01",)', resources)
        self.assertNotIn('scenario_keys = ("SCN-QUEUE-01",)', resources)
        self.assertIn('self.state in {"draft", "ready"}', demo_run)
        self.assertIn("progressive_prompt15_adoption", demo_run)
        self.assertIn("Prompt-15 ", execution)
        self.assertIn("queue/triage arrival operations", execution)









