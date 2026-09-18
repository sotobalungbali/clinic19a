




#!/usr/bin/env python3
"""Standalone MASTER PROMPT 10 source-contract regression tests."""
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATIENT = ROOT / "generators/patient/personas.py"
SOURCE_SHA = "6904ebf6d62ae5f60371fd91287d99b00eba10addb2d7f952602fb0165ef5c2b"


def assignment_values(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except Exception:
            pass
    return values


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


class TestPrompt10SourceContracts(unittest.TestCase):
    def test_build_version_and_source_fingerprint(self):
        manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.61")
        constants = (ROOT / "services/constants.py").read_text(encoding="utf-8")
        self.assertIn(SOURCE_SHA, constants)
        self.assertIn('"clinic_patient": "19.0.1.0.1"', constants)

    def test_patient_generator_registered_and_ordered(self):
        cls, meta = class_metadata(PATIENT, "PatientPersonaGenerator")
        self.assertEqual(meta["key"], "patient.personas")
        self.assertEqual(meta["phase"], "10_patient")
        self.assertEqual(meta["depends_on"], ("workforce.staff",))
        self.assertEqual(meta["scenario_keys"], ("SCN-PATIENT-NEW-01", "SCN-PATIENT-RET-01"))
        self.assertIn("clinic.patient.identifier", meta["owned_models"])
        self.assertIn("clinic.patient.condition", meta["owned_models"])
        self.assertTrue(any(ast.unparse(dec) == "GENERATOR_REGISTRY.register" for dec in cls.decorator_list))
        self.assertIn("from . import patient", (ROOT / "generators/__init__.py").read_text())

    def test_profile_patient_budgets_and_stable_core_personas(self):
        values = assignment_values(PATIENT)
        core = values["CORE_PERSONAS"]
        cohort_counts = values["COHORT_COUNTS"]
        calculated = {key: len(core) + count for key, count in cohort_counts.items()}
        self.assertEqual(calculated, {
            "compact": 16, "standard": 24, "full_enterprise": 32,
        })
        self.assertEqual(len(core), 16)
        codes = {item["code"] for item in core}
        for token in {
            "NEW-001", "RET-001", "ELDER-001", "PED-001", "CHRON-001",
            "FREQ-001", "PKG-001", "IMG-001", "EMAR-001", "TELE-001",
            "MEM-001", "INS-001", "INC-001", "NOSHOW-001", "VIP-001", "REF-001",
        }:
            self.assertIn(token, codes)

    def test_identity_and_source_business_sequence_contract(self):
        text = PATIENT.read_text(encoding="utf-8")
        self.assertIn('f"DEMO-PAT-{code}"', text)
        self.assertIn('f"DEMO-PAT-PARTNER-{code}"', text)
        self.assertIn('f"DEMO-PATID-{label}-{code}"', text)
        self.assertIn('"clinic_patient.seq_patient_code"', text)
        patient_values = text[text.index('patient_values = {'):text.index('patient, patient_ref = self._ensure', text.index('patient_values = {'))]
        self.assertNotIn('"patient_code"', patient_values)
        self.assertIn('patient.patient_code', text)

    def test_synthetic_only_and_deterministic(self):
        text = PATIENT.read_text(encoding="utf-8")
        self.assertIn("@clinicone-demo.invalid", text)
        self.assertIn("Synthetic Demo Residence", text)
        self.assertIn("Synthetic demo", text)
        self.assertNotRegex(text, r"\bimport random\b|\bfrom random\b")
        self.assertNotIn("uuid4", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("faker", text.lower())

    def test_branch_demographic_and_persona_journey_foundations(self):
        text = PATIENT.read_text(encoding="utf-8")
        for token in (
            '"branch_id": branch.id', '"birth_date":', '"gender": spec["gender"]',
            '"billing_policy":', '"pacs_patient_id":', '"dicom_patient_id":',
            '"emar_barcode":', '"allow_portal_booking": True', '"bpjs_no":',
            '"SCN-REFERRAL-01"', '"SCN-SESSION-02"', '"SCN-INCIDENT-01"',
        ):
            self.assertIn(token, text)

    def test_no_premature_downstream_transactions(self):
        text = PATIENT.read_text(encoding="utf-8")
        _, meta = class_metadata(PATIENT, "PatientPersonaGenerator")
        forbidden_owned = {
            "booking.booking", "clinic.encounter", "clinic.insurance.authorization",
            "membership.contract", "clinic.telemedicine.session", "clinical.imaging",
            "clinic.emar.order", "clinic.incident", "clinic.referral", "clinic.treatment.session",
        }
        self.assertFalse(forbidden_owned.intersection(meta["owned_models"]))
        for model in forbidden_owned:
            self.assertNotIn(f'ctx.env["{model}"].create', text)

    def test_patient_identifier_foundation(self):
        text = PATIENT.read_text(encoding="utf-8")
        for token in (
            '"MRN"', '"NIK"', '"BPJS"', '"clinic.patient.identifier.type"',
            '"clinic.patient.identifier"', '"is_national_id": True',
            '"is_insurance_member": True', '"partner_mapping": "custom_nik"',
        ):
            self.assertIn(token, text)

    def test_reset_policy_and_child_first_sequences(self):
        policy = (ROOT / "services/reset_policy_registry.py").read_text(encoding="utf-8")
        for model in (
            "clinic.patient", "clinic.patient.identifier.type", "clinic.patient.identifier",
            "clinic.patient.condition", "clinic.patient.tag", "clinic.patient.allergy",
        ):
            self.assertIn(model, policy)
        text = PATIENT.read_text(encoding="utf-8")
        self.assertIn("RESET_DEACTIVATE, 900", text)
        self.assertIn("RESET_DEACTIVATE, 850", text)
        self.assertIn("RESET_DEACTIVATE, 700", text)
        self.assertIn("RESET_DEACTIVATE, 650", text)

    def test_progressive_prompt10_run_adoption_is_bounded(self):
        text = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        self.assertIn("progressive_prompt10_adoption", text)
        self.assertIn('"patient.personas" not in generated_keys', text)
        self.assertIn('"patient.personas" not in checkpoint_generators', text)
        self.assertIn("generated_keys <= completed_prompt09_generators", text)
        self.assertIn("checkpoint_generators <= completed_prompt09_generators", text)

    def test_success_notification_no_longer_claims_foundation_only(self):
        text = (ROOT / "services/execution_engine.py").read_text(encoding="utf-8")
        self.assertIn("patient-persona", text)
        self.assertIn("Prompt-11 clinical/commercial", text)
        self.assertNotIn("FOUNDATION & ORGANIZATION are now real demo data", text)

    def test_runtime_guardrails(self):
        text = PATIENT.read_text(encoding="utf-8")
        self.assertNotIn(".sudo(", text)
        self.assertNotIn(".execute(", text)
        self.assertNotIn(".cr.commit(", text)
        self.assertNotIn("create_date", text)
        self.assertNotIn("write_date", text)
        self.assertIn("with self.env.cr.savepoint()", (ROOT / "services/execution_engine.py").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
























