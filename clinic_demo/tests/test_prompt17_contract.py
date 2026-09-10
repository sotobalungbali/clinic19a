"""Static regression contract for MASTER PROMPT 17."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestPrompt17Contract(unittest.TestCase):
    def test_four_bounded_generators(self):
        tree = ast.parse((ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8"))
        found = {}
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            if not any(ast.unparse(item) == "GENERATOR_REGISTRY.register" for item in cls.decorator_list):
                continue
            values = {}
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    try:
                        values[stmt.targets[0].id] = ast.literal_eval(stmt.value)
                    except (ValueError, TypeError):
                        pass
            found[values.get("key")] = values
        self.assertEqual(set(found), {"clinical.imaging", "clinical.emar", "clinical.care_postcare", "clinical.telemedicine"})
        self.assertTrue(all(item["phase"] == "17_advanced" for item in found.values()))

    def test_no_generator_security_or_state_bypass(self):
        tree = ast.parse((ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, {"sudo", "create_date", "write_date"})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotEqual(node.func.attr, "execute")

    def test_registry_scenarios_are_bound(self):
        registry = (ROOT / "services/scenario_registry.py").read_text(encoding="utf-8")
        for key in ("clinical.imaging", "clinical.emar", "clinical.care_postcare", "clinical.telemedicine"):
            self.assertIn("'generator_key': '%s'" % key, registry)

    def test_progressive_prompt17_adoption(self):
        source = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        for token in (
            "completed_prompt16_generators", "prompt17_generators",
            "prompt16_complete", "progressive_prompt17_adoption",
            "Prompt 17 progressive contract adopted after completed Prompt-16 scope",
        ):
            self.assertIn(token, source)

    def test_failed_prompt17_adoption_is_bounded_and_reset_free(self):
        source = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        for token in (
            "prompt17_sequence", "prompt17_failed_keys", "prompt17_failed_key",
            "prompt17_completed_prefix", "prompt17_uncommitted_suffix",
            "prompt17_prefix_complete",
            "prompt17_runtime_repair_checkpoint_shape",
            "prompt17_runtime_repair_adoption",
            'self.state == "failed"',
            "completed_prompt16_generators | prompt17_completed_prefix",
            "not (generated_keys & prompt17_uncommitted_suffix)",
            "Prompt 17 stage-aware whole-path runtime repair",
        ):
            self.assertIn(token, source)

    def test_whole_path_preflight_and_deterministic_identifiers(self):
        source = (ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8")
        for token in (
            "ADVANCED_RUNTIME_CONTRACTS", "ADVANCED_RELATION_CONTRACTS",
            "ADVANCED_ACCESS_CONTRACTS", "ADVANCED_ACTOR_GROUPS",
            "_reconcile_advanced_actor_entitlements",
            "_preflight_all_advanced_paths", "_prepare_advanced_runtime",
            '.check_access(mode)',
            '"name": "DEMO-IMG-001"', '"name": "DEMO-EMAR-RX-001"',
            '"name": "DEMO-EMAR-ORDER-001"',
            '"name": "DEMO-EMAR-ADMIN-001"',
            '"name": "DEMO-CARE-PLAN-001"',
            '"name": "DEMO-POSTCARE-PLAN-001"',
            '"name": "DEMO-CONSENT-TELE-001"',
            '"name": "DEMO-TELE-SESSION-001"',
            '"name": "DEMO-TELE-THREAD-001"',
            "CLINICONE-DEMO-MED-PARA-500",
            '"patient_scan_code": patient.emar_barcode',
            '"product_scan_code": product.barcode',
        ):
            self.assertIn(token, source)

    def test_runtime_failure_contract_is_closed_as_one_matrix(self):
        source = (ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8")
        self.assertIn('(\"clinic.emar.order\", \"patient_id\"): \"res.partner\"', source)
        self.assertIn('(\"clinic.emar.order\", \"clinic_patient_id\"): \"clinic.patient\"', source)
        self.assertIn('\"patient_id\": patient.partner_id.id', source)
        self.assertIn('\"clinic_patient_id\": patient.id', source)
        self.assertIn('self._as_actor(order, manager_user).action_confirm()', source)
        access_matrix = source.split("ADVANCED_ACCESS_CONTRACTS =", 1)[1]
        message_contract = access_matrix.split('\"clinic.telemedicine.message\":', 1)[1].split("\n", 1)[0]
        self.assertIn('(\"read\", \"create\")', message_contract)
        self.assertNotIn('\"write\"', message_contract)
        nurse_contract = source.split('\"DEMO-USER-NUR-001\": {', 1)[1].split('}', 1)[0]
        self.assertIn('\"clinic.emar.order\": (\"read\",)', nurse_contract)
        self.assertNotIn('\"clinic.emar.order\": (\"read\", \"create\"', nurse_contract)
    def test_emar_medication_lines_have_exactly_one_header(self):
        """Prescription and execution lines must satisfy the owner XOR contract."""
        tree = ast.parse((ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8"))
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "_line_values":
                continue
            calls.append({
                keyword.arg for keyword in node.keywords
                if keyword.arg in {"order_id", "prescription_id"}
            })
        self.assertEqual(calls, [{"prescription_id"}, {"order_id"}])
        self.assertTrue(all(len(headers) == 1 for headers in calls))

    def test_semantic_workflow_prerequisites_are_explicit(self):
        source = (ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8")
        for token in (
            '"consent_id", "is_confidential"',
            '("clinic.care.plan", "consent_id"): "clinic.consent.form"',
            '("DEMO-CONSENT-TPL-GENERAL", "clinic.consent.template")',
            'template.state != "published"',
            'care_protocol.version_state != "published"',
            'not doctor.telemedicine_enabled',
            '"DEMO-CONSENT-CARE-SIGNED-001"',
            '"is_confidential": True, "consent_id": consent.id',
            'care.consent_id.state != "signed"',
            '"branch_id": False',
        ):
            self.assertIn(token, source)
        care_block = source.split("class AdvancedCarePostcareGenerator", 1)[1].split(
            "class AdvancedTelemedicineGenerator", 1
        )[0]
        self.assertLess(care_block.index('"DEMO-CONSENT-CARE-SIGNED-001"'), care_block.index('"DEMO-CARE-PLAN-001"'))
        self.assertLess(care_block.index("actor_consent.action_sign("), care_block.index("actor_care.action_activate()"))

    def test_actor_field_access_is_explicit_and_prefetch_bounded(self):
        source = (ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8")
        for token in (
            "ADVANCED_ACTOR_CONTEXT", '"prefetch_fields": False',
            "ADVANCED_FIELD_READ_CONTRACTS", "_as_actor",
            '("work_contact_id", "user_id")',
            "record.read(list(field_names))",
            "cannot read {model_name} fields",
        ):
            self.assertIn(token, source)
        self.assertEqual(source.count(".with_user("), 2)

    def test_every_prompt17_generator_prepares_whole_runtime_path(self):
        tree = ast.parse((ROOT / "generators/clinical/advanced.py").read_text(encoding="utf-8"))
        generator_classes = {
            "AdvancedImagingGenerator", "AdvancedEmarGenerator",
            "AdvancedCarePostcareGenerator", "AdvancedTelemedicineGenerator",
        }
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            if cls.name not in generator_classes:
                continue
            generate = next(
                node for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name == "generate"
            )
            calls = [
                node for node in ast.walk(generate)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_prepare_advanced_runtime"
            ]
            self.assertEqual(len(calls), 1, cls.name)

    def test_owner_temporal_api_contract_is_a_hard_gate(self):
        guardrail = (ROOT / "tools/clinic_demo_guardrail.py").read_text(encoding="utf-8")
        for token in (
            "PROMPT17_OWNER_ADDONS", "VALID_ODOO_TEMPORAL_HELPERS",
            "prompt17_owner_temporal_api_contract",
            "Invalid Prompt-17 owner temporal APIs",
            "Prompt-17 owner temporal API allowlist: PASS",
        ):
            self.assertIn(token, guardrail)

        owner = ROOT.parent / "clinic_emar" / "models/core/emar_prescription.py"
        if owner.exists():
            source = owner.read_text(encoding="utf-8")
            self.assertIn("from datetime import timedelta", source)
            self.assertIn("+ timedelta(days=rec.valid_days)", source)
            self.assertNotIn("fields.Date.timedelta", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)









