from pathlib import Path
import ast
import csv
import re
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class TestClinicAuditSourceContracts(unittest.TestCase):
    def test_manifest_identity_and_dependency_boundary(self):
        data = ast.literal_eval((ROOT / "__manifest__.py").read_text().split("\n", 1)[1])
        self.assertEqual(data["version"], "19.0.2.0.3")
        self.assertIn("clinic_base", data["depends"])
        self.assertIn("clinic_branch", data["depends"])
        self.assertNotIn("clinic_encounter", data["depends"])
        self.assertNotIn("clinic_integration_api", data["depends"])
        self.assertNotIn("clinic_analytics", data["depends"])
        for rel in data["data"]:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_authoritative_event_is_separate_from_legacy_log(self):
        event = (ROOT / "models/audit_event.py").read_text()
        legacy = (ROOT / "models/audit_legacy_log.py").read_text()
        self.assertIn('_name = "clinic.audit.event"', event)
        self.assertIn('_name = "clinic.audit.log"', legacy)
        self.assertIn("event_hash", event)
        self.assertNotIn("event_hash", legacy)

    def test_authoritative_evidence_is_immutable(self):
        event = (ROOT / "models/audit_event.py").read_text()
        line = (ROOT / "models/audit_event_line.py").read_text()
        self.assertIn("Audit events are immutable", event)
        self.assertIn("def unlink(self):", event)
        self.assertIn("Audit event lines are immutable", line)

    def test_registry_coverage_uses_origin_chaining(self):
        text = (ROOT / "models/audit_registry_hook.py").read_text()
        self.assertIn("method.origin", text)
        self.assertIn("clinic_audit_skip=True", text)
        self.assertIn('_clinic_audit_logger_model = "clinic.audit.event"', text)
        self.assertIn("_harden_legacy_log_surface", text)

    def test_fixed_tracked_catalog_is_large_and_excludes_audit_models(self):
        ns = {}
        exec((ROOT / "models/tracked_model_catalog.py").read_text(), ns)
        names = ns["TRACKED_MODEL_NAMES"]
        self.assertGreaterEqual(len(names), 350)
        self.assertEqual(len(names), len(set(names)))
        self.assertFalse(any(n.startswith("clinic.audit.") for n in names))

    def test_odoo19_constraint_api_only(self):
        for folder in (ROOT / "models", ROOT / "wizard"):
            for path in folder.glob("*.py"):
                tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        self.assertFalse(isinstance(target, ast.Name) and target.id == "_sql_constraints", path.name)
        joined = "\n".join(p.read_text() for p in (ROOT / "models").glob("*.py"))
        self.assertIn("models.Constraint", joined)

    def test_privacy_redaction_contract(self):
        text = (ROOT / "models/audit_service.py").read_text()
        for term in ["password", "token", "diagnos", "allerg", "attachment", "binary"]:
            self.assertIn(term, text)
        self.assertIn('"redacted": True', text)

    def test_fail_closed_default(self):
        text = (ROOT / "models/res_config_settings.py").read_text()
        self.assertIn("clinic.audit.fail_closed", text)
        self.assertIn("default=True", text)

    def test_all_xml_is_well_formed(self):
        for path in ROOT.rglob("*.xml"):
            ET.parse(path)

    def test_no_legacy_tree_view_tag(self):
        for path in ROOT.rglob("*.xml"):
            self.assertNotIn("<tree", path.read_text(), path.name)

    def test_search_list_form_for_all_persistent_ui_models(self):
        xml = "\n".join(p.read_text() for p in ROOT.rglob("*.xml"))
        models = [
            "clinic.audit.event", "clinic.audit.event.line", "clinic.audit.policy",
            "clinic.audit.review", "clinic.audit.review.tag", "clinic.audit.review.line",
            "clinic.audit.verification", "clinic.audit.log", "clinic.audit.log.line",
        ]
        for model in models:
            self.assertGreaterEqual(xml.count(f"<field name=\"model\">{model}</field>"), 3, model)

    def test_object_buttons_have_local_python_methods(self):
        method_names = set()
        for folder in (ROOT / "models", ROOT / "wizard"):
            for path in folder.glob("*.py"):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_names.add(node.name)
        button_names = set()
        for path in ROOT.rglob("*.xml"):
            tree = ET.parse(path)
            for node in tree.iter("button"):
                if node.attrib.get("type") == "object":
                    button_names.add(node.attrib.get("name"))
        missing = sorted(button_names - method_names)
        self.assertFalse(missing, missing)

    def test_authoritative_acl_is_readonly_for_evidence(self):
        with (ROOT / "security/ir.model.access.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        for model_id in {"model_clinic_audit_event", "model_clinic_audit_event_line"}:
            relevant = [r for r in rows if r["model_id:id"] == model_id]
            self.assertTrue(relevant)
            self.assertTrue(all(r["perm_write"] == "0" and r["perm_create"] == "0" and r["perm_unlink"] == "0" for r in relevant))

    def test_global_evidence_rules_exist(self):
        text = (ROOT / "security/clinic_audit_security.xml").read_text()
        self.assertIn("rule_audit_event_global_scope", text)
        self.assertIn("allowed_branch_ids", text)
        self.assertIn('<field name="global" eval="True"/>', text)

    def test_relation_and_constraint_identifiers_are_postgres_safe(self):
        for path in (ROOT / "models").glob("*.py"):
            for literal in re.findall(r'[\"\']([a-z][a-z0-9_]+)[\"\']', path.read_text()):
                if any(key in literal for key in ("_rel", "_unique")):
                    self.assertLessEqual(len(literal), 63, literal)

    def test_no_digit_prefixed_packaged_basename(self):
        bad = [p for p in ROOT.rglob("*") if p.is_file() and p.name and p.name[0].isdigit()]
        self.assertFalse(bad, bad)

    def test_guardrail_docs_exist(self):
        for name in [
            "PROJECT_IDENTITY_PREFLIGHT.md", "FULL_STRUCTURAL_INVENTORY.md",
            "CROSS_ADDON_CONTRACT_AUDIT.md", "SECURITY_MODEL.md", "UI_UX_MATRIX.md",
            "ENTERPRISE_COMPLETENESS_MATRIX.md", "ARCHITECTURE_DECISION_RECORD.md",
        ]:
            self.assertTrue((ROOT / "docs" / name).is_file(), name)

    def test_no_downstream_analytics_reference_in_runtime_code(self):
        runtime = "\n".join(p.read_text() for folder in [ROOT / "models", ROOT / "wizard"] for p in folder.glob("*.py"))
        self.assertNotIn("clinic.analytics", runtime)




    def test_legacy_import_wizard_pagination_contract(self):
        model = (ROOT / "wizard/audit_legacy_import.py").read_text()
        view = (ROOT / "wizard/audit_legacy_import_views.xml").read_text()
        self.assertIn("last_legacy_id = fields.Integer(", model)
        self.assertIn('("id", ">", self.last_legacy_id)', model)
        self.assertIn("last_processed_id = self.last_legacy_id", model)
        self.assertIn('"last_legacy_id":', model)
        self.assertIn('name="last_legacy_id"', view)
        self.assertIn('name="action_import"', view)

    def test_legacy_log_object_button_has_load_time_and_runtime_contract(self):
        legacy = (ROOT / "models/audit_legacy_log.py").read_text()
        hook = (ROOT / "models/audit_registry_hook.py").read_text()
        view = (ROOT / "views/audit_legacy_views.xml").read_text()

        self.assertIn('name="action_open_log"', view)
        self.assertIn("def action_open_log(self):", legacy)
        self.assertIn('ModelClass = self.env.registry["clinic.audit.log"]', hook)
        self.assertIn("ModelClass.action_open_log = action_open_log", hook)

    def test_dynamic_overdue_search_contract(self):
        review = (ROOT / "models/audit_review.py").read_text()
        self.assertIn('search="_search_is_overdue"', review)
        self.assertIn("def _search_is_overdue", review)
        self.assertIn('"in", "not in"', review)
        self.assertIn('("due_date", "<", now)', review)
        self.assertIn('("due_at", "<", now)', review)

    def test_upgrade_migration_preserves_legacy_policy_state(self):
        path = ROOT / "migrations/19.0.2.0.0/post-preserve-legacy-policy-state.py"
        self.assertTrue(path.is_file())
        text = path.read_text()
        self.assertIn("trigger IS NOT NULL", text)
        self.assertIn("state = 'active'", text)


if __name__ == "__main__":
    unittest.main()
