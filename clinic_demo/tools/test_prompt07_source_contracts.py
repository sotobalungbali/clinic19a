
#!/usr/bin/env python3
"""Standalone Prompt-07 source-contract regression tests.

These tests do not need an Odoo server. Odoo TransactionCase tests remain packaged
for the user's target Odoo 19 runtime.
"""

from pathlib import Path
import ast
import hashlib
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPrompt07SourceContracts(unittest.TestCase):

    def test_manifest_version_and_clinicone_dependencies(self):
        manifest = ast.literal_eval(
            ast.parse((ROOT / "__manifest__.py").read_text(encoding="utf-8")).body[0].value
        )
        self.assertEqual(manifest["version"], "19.0.1.0.19")
        clinic_dependencies = [
            name for name in manifest["depends"] if name.startswith("clinic_")
        ]
        self.assertEqual(len(clinic_dependencies), 41)
        self.assertEqual(len(set(clinic_dependencies)), 41)

    def test_expected_suite_fingerprint(self):
        constants = load_module(
            "prompt07_constants",
            ROOT / "services/constants.py",
        )
        vector = constants.EXPECTED_SUITE_VERSIONS
        canonical = "\n".join(f"{name}={vector[name]}" for name in sorted(vector))
        actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(actual, constants.EXPECTED_SUITE_FINGERPRINT)

    def test_seed_is_namespace_order_independent(self):
        seed_module = load_module(
            "prompt07_seed",
            ROOT / "services/seed_service.py",
        )
        service = seed_module.DeterministicSeedService("247001")
        before = service.token("patient:DEMO-PAT-001")
        service.token("unrelated:scenario")
        after = service.token("patient:DEMO-PAT-001")
        self.assertEqual(before, after)

    def test_prompt04_scenario_registry_contains_34_unique_scenarios(self):
        text = (ROOT / "services/scenario_registry.py").read_text(encoding="utf-8")
        tree = ast.parse(text)
        data_node = next(
            statement.value
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_SCENARIO_DATA"
                for target in statement.targets
            )
        )
        data = ast.literal_eval(data_node)
        keys = [item["key"] for item in data]
        self.assertEqual(len(keys), 34)
        self.assertEqual(len(set(keys)), 34)
        self.assertIn("SCN-REFERRAL-01", keys)
        self.assertIn("SCN-SESSION-01", keys)

    def test_control_center_menu_uses_runtime_safe_parent_bridge(self):
        menu_xml = (ROOT / "views/demo_menus.xml").read_text(encoding="utf-8")
        bridge_xml = (ROOT / "data/demo_menu_bridge.xml").read_text(encoding="utf-8")
        bridge_service = (
            ROOT / "services/menu_bridge_service.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            'parent="clinic_patient.menu_patient_configuration"',
            menu_xml,
        )
        self.assertIn("_ensure_demo_dataset_menu_parent", bridge_xml)
        self.assertIn(
            "clinic_patient.menu_patient_configuration",
            bridge_service,
        )
        self.assertNotIn("res.config.settings", menu_xml)


if __name__ == "__main__":
    unittest.main(verbosity=2)



