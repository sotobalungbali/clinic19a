
"""Static regression contract for MASTER PROMPT 16."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestPrompt16Contract(unittest.TestCase):
    def test_prompt16_generators_registered(self):
        init = (ROOT / "generators" / "operations" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("from . import encounter", init)
        self.assertIn("from . import treatment_session", init)

    def test_no_forbidden_prompt16_bypass(self):
        for name in ("encounter.py", "treatment_session.py"):
            source = (ROOT / "generators" / "operations" / name).read_text(encoding="utf-8")
            tree = ast.parse(source)

            forbidden_attrs = {"create_date", "write_date"}
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(
                        node.attr,
                        forbidden_attrs,
                        f"{name} manipulates technical audit field {node.attr}",
                    )
                    self.assertNotEqual(
                        node.attr,
                        "sudo",
                        f"{name} uses sudo()",
                    )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "execute":
                        owner = node.func.value
                        if isinstance(owner, ast.Attribute) and owner.attr in {"cr", "_cr"}:
                            self.fail(f"{name} uses direct SQL")
                        if isinstance(owner, ast.Name) and owner.id in {"cr", "_cr"}:
                            self.fail(f"{name} uses direct SQL")

    def test_scenario_rebinding(self):
        source = (ROOT / "services" / "scenario_registry.py").read_text(encoding="utf-8")
        self.assertIn("'SCN-ENCOUNTER-01'", source)
        self.assertIn("'generator_key': 'operations.encounter'", source)
        self.assertIn("'SCN-SESSION-01'", source)
        self.assertIn("'generator_key': 'operations.treatment_session'", source)

    def test_progressive_adoption(self):
        source = (ROOT / "models" / "demo_run.py").read_text(encoding="utf-8")
        for token in (
            "completed_prompt15_generators",
            "prompt16_generators",
            "prompt15_complete",
            "progressive_prompt16_adoption",
            "Prompt 16 progressive contract adopted after completed Prompt-15 scope",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)









