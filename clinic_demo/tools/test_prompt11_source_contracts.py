




#!/usr/bin/env python3
"""Standalone MASTER PROMPT 11 source-contract regression tests."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "generators/master"
CATALOG = MASTER / "catalog.py"
CONSENT = MASTER / "consent.py"
COMMERCIAL = MASTER / "commercial.py"
SOURCE_SHA = "8e0d2be47034b5841642ba056df294825f71a6040f7f27b77cd6da32ef417ab2"


def assignments(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                result[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return result


def class_meta(path, class_name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    result = {}
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        result[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    return cls, result


class TestPrompt11SourceContracts(unittest.TestCase):
    def test_build_version_and_source_contract(self):
        manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.46")
        constants = (ROOT / "services/constants.py").read_text(encoding="utf-8")
        self.assertIn(SOURCE_SHA, constants)
        self.assertIn('GENERATOR_VERSION = "19.0.1.0.46"', constants)

    def test_three_master_generators_are_registered_in_order(self):
        expected = (
            (CATALOG, "MasterCatalogGenerator", "master.catalog", 400, ("patient.personas",)),
            (CONSENT, "MasterConsentGenerator", "master.consent", 410, ("master.catalog",)),
            (COMMERCIAL, "MasterCommercialGenerator", "master.commercial", 420, ("master.consent",)),
        )
        for path, cls_name, key, sequence, deps in expected:
            cls, meta = class_meta(path, cls_name)
            self.assertEqual(meta["key"], key)
            self.assertEqual(meta["phase"], "11_master")
            self.assertEqual(meta["sequence"], sequence)
            self.assertEqual(meta["depends_on"], deps)
            self.assertTrue(any(ast.unparse(dec) == "GENERATOR_REGISTRY.register" for dec in cls.decorator_list))
        self.assertIn("from . import master", (ROOT / "generators/__init__.py").read_text())

    def test_catalog_profile_budgets_preserve_golden_prerequisites(self):
        vals = assignments(CATALOG)
        self.assertEqual(vals["PROFILE_TREATMENT_COUNTS"], {"compact": 8, "standard": 9, "full_enterprise": 10})
        self.assertEqual(vals["PROFILE_IMAGING_COUNTS"], {"compact": 2, "standard": 3, "full_enterprise": 3})
        self.assertEqual(vals["PROFILE_MEDICATION_COUNTS"], {"compact": 3, "standard": 4, "full_enterprise": 5})
        codes = [item["code"] for item in vals["TREATMENT_SPECS"]]
        for code in ("CONSULT-GEN", "FOLLOW-UP", "PHYSIO", "SKIN-PROC", "TELE-CONSULT", "IMG-XR", "IMG-US"):
            self.assertIn(code, codes[:8])

    def test_treatment_pricing_and_native_product_bridge_are_source_driven(self):
        text = CATALOG.read_text(encoding="utf-8")
        for token in (
            '"clinic.treatment.category"', '"clinic.treatment"', '"clinic.treatment.pricelist"',
            '"clinic.treatment.pricelist.item"', 'treatment.catalog_id.product_tmpl_id',
            '"base_price"', '"minimum_price"', '"pricing_policy"',
        ):
            self.assertIn(token, text)
        self.assertIn('"consent_required": False', text)

    def test_care_imaging_emar_masters_use_owner_workflow_and_anchor_date(self):
        text = CATALOG.read_text(encoding="utf-8")
        for token in (
            '"clinic.care.protocol"', '"clinic.care.protocol.step"', 'protocol.action_submit_review()',
            'protocol.action_publish()', '"effective_date": fields.Date.to_date(ctx.run.anchor_date)',
            '"clinical.imaging.type"', '"clinical.imaging.protocol"', '"clinical.imaging.type.prep"',
            '"clinic.emar.medication.profile"', '"Demo Iodinated Contrast Agent"',
        ):
            self.assertIn(token, text)

    def test_consent_governance_is_published_through_business_action(self):
        text = CONSENT.read_text(encoding="utf-8")
        for token in (
            '"legal_governed": True', '"state": "draft"', 'template.action_publish()',
            '"clinic.consent.template.version"', '"state": "published"',
            '"consent_default_template_id": template.id', '"consent_required": True',
        ):
            self.assertIn(token, text)

    def test_package_and_membership_are_master_only_and_safe_mode_neutral(self):
        text = COMMERCIAL.read_text(encoding="utf-8")
        for token in (
            'package.action_activate()', 'event.action_cancel()', 'plan.action_activate()',
            'event.action_ignore()', '"clinic.package.line"', '"membership.plan.benefit"',
            '"product.template"',
        ):
            self.assertIn(token, text)
        self.assertIn("Prompt 11 creates plan policy only", text)

    def test_insurance_and_wallet_master_prerequisites_exist_without_patient_transactions(self):
        text = COMMERCIAL.read_text(encoding="utf-8")
        for token in (
            '"is_insurer": True', '"clinic.insurance.plan"', '"clinic.insurance.plan.rule"',
            'clinic_insurance_authorization.group_clinic_insurance_manager',
            'plan.with_user(manager_user).action_activate()', '"clinic.wallet.rule"',
            '"membership_tier_ids"',
        ):
            self.assertIn(token, text)

    def test_no_premature_transaction_ownership(self):
        forbidden = {
            "clinic.package.allocation", "clinic.package.usage", "membership.contract",
            "clinic.wallet", "clinic.wallet.transaction", "clinic.insurance.policy",
            "clinic.insurance.authorization", "clinic.billing.invoice", "clinic.billing.payment",
            "clinic.consent.form", "clinical.imaging.request", "clinic.emar.order",
        }
        for path, cls_name in ((CATALOG, "MasterCatalogGenerator"), (CONSENT, "MasterConsentGenerator"), (COMMERCIAL, "MasterCommercialGenerator")):
            _cls, meta = class_meta(path, cls_name)
            self.assertFalse(forbidden.intersection(meta["owned_models"]))

    def test_reset_policy_is_model_specific(self):
        text = (ROOT / "services/reset_policy_registry.py").read_text(encoding="utf-8")
        for model in (
            "clinic.treatment", "clinic.care.protocol", "clinical.imaging.type",
            "clinic.emar.medication.profile", "clinic.consent.template", "clinic.package",
            "membership.plan", "clinic.insurance.plan", "clinic.wallet.rule",
            "clinic.package.line", "membership.plan.benefit", "clinic.insurance.plan.rule",
        ):
            self.assertIn(model, text)
        self.assertIn("RESET_FRESH_DB_ONLY", text)
        self.assertIn("RESET_DEACTIVATE", text)

    def test_prompt11_progressive_adoption_is_bounded(self):
        text = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        self.assertIn("progressive_prompt11_adoption", text)
        self.assertIn("generated_keys <= completed_prompt10_generators", text)
        self.assertIn("checkpoint_generators <= completed_prompt10_generators", text)
        self.assertIn('"patient.personas" in checkpoint_generators', text)
        self.assertIn('prompt11_generators = {"master.catalog", "master.consent", "master.commercial"}', text)

    def test_registered_scope_notification_reflects_prompt11(self):
        text = (ROOT / "services/execution_engine.py").read_text(encoding="utf-8")
        self.assertIn("Prompt-11 clinical/commercial", text)
        self.assertIn("Prompt-12 room/device/resource scheduling", text)
        self.assertIn("35-generator enterprise registry", text)

    def test_owner_sequence_preflight_is_explicit(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in (CATALOG, CONSENT, COMMERCIAL))
        for code in (
            "clinic.care.protocol", "clinic.consent.template", "clinic.package",
            "clinic.package.integration.event", "membership.plan",
        ):
            self.assertIn(code, text)
        self.assertIn("missing sequence", text)

    def test_determinism_and_runtime_guardrails(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in (CATALOG, CONSENT, COMMERCIAL))
        self.assertNotIn(".sudo(", text)
        self.assertNotIn(".execute(", text)
        self.assertNotIn(".cr.commit(", text)
        self.assertNotIn("uuid4", text)
        self.assertNotIn("random.", text)
        self.assertNotIn("date.today()", text)
        self.assertNotIn("create_date", text)
        self.assertNotIn("write_date", text)
        self.assertIn("fields.Date.to_date(ctx.run.anchor_date)", text)

    def test_prompt11_registered_count_is_eight(self):
        generator_files = list((ROOT / "generators").rglob("*.py"))
        keys = []
        for path in generator_files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
                decorated = any(ast.unparse(dec) == "GENERATOR_REGISTRY.register" for dec in cls.decorator_list)
                if not decorated:
                    continue
                for node in cls.body:
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "key" for t in node.targets):
                        keys.append(ast.literal_eval(node.value))
        self.assertGreaterEqual(len(set(keys)), 8)
        self.assertTrue({"master.catalog", "master.consent", "master.commercial"}.issubset(keys))

    def test_functional_manager_security_context_covers_restricted_prompt11_models(self):
        catalog = CATALOG.read_text(encoding="utf-8")
        commercial = COMMERCIAL.read_text(encoding="utf-8")
        reference = (ROOT / "services/reference_service.py").read_text(encoding="utf-8")
        self.assertIn("CATALOG_MANAGER_GROUPS", catalog)
        self.assertIn("clinic_emar.group_emar_manager", catalog)
        self.assertIn('DEMO-USER-MGR', catalog)
        self.assertIn("record_user=manager_user", catalog)
        for xmlid in (
            "clinic_package.group_clinic_package_manager",
            "clinic_membership.group_clinic_membership_manager",
            "clinic_insurance_authorization.group_clinic_insurance_manager",
            "clinic_wallet.group_wallet_manager",
        ):
            self.assertIn(xmlid, commercial)
        for model in (
            "clinic.package", "clinic.package.line", "membership.plan",
            "membership.plan.benefit", "clinic.insurance.plan",
            "clinic.insurance.plan.rule", "clinic.wallet.rule",
        ):
            self.assertIn(model, commercial)
        self.assertIn("RESTRICTED_COMMERCIAL_MODELS", commercial)
        self.assertIn("record_user=None", reference)
        self.assertIn("model.with_user(record_user)", reference)
        self.assertNotIn(".sudo(", catalog)
        self.assertNotIn(".sudo(", commercial)

    def test_prompt11_acl_runtime_repair_adoption_is_bounded(self):
        text = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        self.assertIn("prompt11_catalog_failed", text)
        self.assertIn("no_prompt11_references", text)
        self.assertIn("prompt11_acl_repair_checkpoint_shape", text)
        self.assertIn("prompt11_acl_runtime_repair_adoption", text)
        self.assertIn('checkpoint.generator_key == "master.catalog"', text)
        self.assertIn('checkpoint.state == "failed"', text)
        self.assertIn('not (generated_keys & prompt11_generators)', text)


    def test_membership_owner_acl_runtime_repair_contract(self):
        commercial = COMMERCIAL.read_text(encoding="utf-8")
        constants = (ROOT / "services/constants.py").read_text(encoding="utf-8")
        self.assertIn("COMMERCIAL_CREATE_ACCESS_MODELS", commercial)
        self.assertIn('check_access("create")', commercial)
        self.assertIn("MASTER PROMPT 11 commercial ACL preflight failed", commercial)
        self.assertIn('"membership.plan"', commercial)
        self.assertIn('"membership.plan.benefit"', commercial)
        self.assertIn('"clinic_membership": "19.0.3.0.6"', constants)

    def test_master_commercial_acl_runtime_repair_adoption_is_bounded(self):
        text = (ROOT / "models/demo_run.py").read_text(encoding="utf-8")
        self.assertIn("prompt11_commercial_failed", text)
        self.assertIn("no_prompt11_commercial_references", text)
        self.assertIn("prompt11_commercial_acl_runtime_repair_adoption", text)
        self.assertIn('checkpoint.generator_key == "master.commercial"', text)
        self.assertIn('reference.generator_key == "master.commercial"', text)
        self.assertIn('"master.catalog" in checkpoint_generators', text)
        self.assertIn('"master.consent" in checkpoint_generators', text)



if __name__ == "__main__":
    unittest.main(verbosity=2)









