




#!/usr/bin/env python3
"""Standalone MASTER PROMPT 08 source-contract regression tests."""

from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


def class_metadata(path, class_name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    values = {}
    for statement in cls.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name):
                try:
                    values[target.id] = ast.literal_eval(statement.value)
                except Exception:
                    pass
    return cls, values


class TestPrompt08SourceContracts(unittest.TestCase):

    def test_foundation_generators_are_registered(self):
        native_path = ROOT / "generators/foundation/native_odoo.py"
        org_path = ROOT / "generators/foundation/organization.py"

        native_cls, native = class_metadata(native_path, "NativeOdooFoundationGenerator")
        org_cls, org = class_metadata(org_path, "ClinicOrganizationFoundationGenerator")

        self.assertEqual(native["key"], "foundation.native")
        self.assertEqual(org["key"], "foundation.organization")
        self.assertEqual(native["phase"], "08_foundation")
        self.assertEqual(org["phase"], "08_foundation")
        self.assertEqual(org["depends_on"], ("foundation.native",))

        self.assertTrue(
            any(
                ast.unparse(dec) == "GENERATOR_REGISTRY.register"
                for dec in native_cls.decorator_list
            )
        )
        self.assertTrue(
            any(
                ast.unparse(dec) == "GENERATOR_REGISTRY.register"
                for dec in org_cls.decorator_list
            )
        )

    def test_organization_generator_declares_owner_models_and_role(self):
        _, org = class_metadata(
            ROOT / "generators/foundation/organization.py",
            "ClinicOrganizationFoundationGenerator",
        )
        self.assertEqual(
            org["owned_models"],
            ("clinic.branch", "clinic.branch.location"),
        )
        self.assertEqual(
            org["required_groups"],
            ("clinic_branch.group_branch_manager",),
        )

    def test_profile_branch_and_location_budgets(self):
        text = (ROOT / "generators/foundation/organization.py").read_text(encoding="utf-8")
        tree = ast.parse(text)

        branch_specs = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "BRANCH_SPECS" for t in node.targets)
        )
        location_specs = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "LOCATION_SPECS" for t in node.targets)
        )

        self.assertEqual(len(branch_specs), 3)
        self.assertEqual(len(location_specs["compact"]), 3)
        self.assertEqual(len(location_specs["standard"]), 6)
        self.assertEqual(len(location_specs["full_enterprise"]), 12)

    def test_stable_foundation_demo_keys_exist(self):
        text = (
            ROOT / "generators/foundation/organization.py"
        ).read_text(encoding="utf-8")
        for key in (
            "DEMO-BRANCH-001",
            "DEMO-BRANCH-002",
            "DEMO-BRANCH-003",
            "DEMO-LOC-B",
            "DEMO-WAREHOUSE-PRIMARY",
        ):
            self.assertIn(key, text)

    def test_native_generator_reuses_selected_company(self):
        text = (
            ROOT / "generators/foundation/native_odoo.py"
        ).read_text(encoding="utf-8")
        self.assertIn("DEMO-COMPANY-001", text)
        self.assertIn("DEMO-CURRENCY-BASE", text)
        self.assertIn("DEMO-COUNTRY-ID", text)
        self.assertNotIn('env["res.company"].create', text)
        self.assertNotIn('env["account.journal"].create', text)
        self.assertNotIn('env["account.tax"].create', text)

    def test_demo_manager_implies_branch_manager(self):
        xml = (
            ROOT / "security/clinic_demo_security.xml"
        ).read_text(encoding="utf-8")
        self.assertIn("clinic_branch.group_branch_manager", xml)

    def test_reset_policy_knows_foundation_models(self):
        text = (
            ROOT / "services/reset_policy_registry.py"
        ).read_text(encoding="utf-8")
        self.assertIn('{"clinic.branch", "clinic.branch.location"}', text)
        self.assertIn('model_name == "resource.resource"', text)
        self.assertIn('model_name == "ir.sequence"', text)

    def test_execution_engine_is_real_bounded_runner(self):
        text = (
            ROOT / "services/execution_engine.py"
        ).read_text(encoding="utf-8")
        self.assertIn("with self.env.cr.savepoint()", text)
        self.assertIn("generator().generate", text.replace("instance.generate", "generator().generate"))
        self.assertNotIn(".cr.commit(", text)
        self.assertNotIn("sudo()", text)

    def test_no_hardcoded_business_calendar_date(self):
        runtime = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ROOT.rglob("*.py")
            if "tests" not in path.parts and "tools" not in path.parts
        )
        import re
        self.assertIsNone(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", runtime))


if __name__ == "__main__":
    unittest.main(verbosity=2)
























