from pathlib import Path

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.generator_registry import GENERATOR_REGISTRY


@tagged("post_install", "-at_install")
class TestPrompt18Contract(TransactionCase):
    def test_registry_order_and_dependencies(self):
        expected = {
            "commercial.billing": (750, ("clinical.telemedicine",)),
            "commercial.ar": (760, ("commercial.billing",)),
            "commercial.ap": (770, ("commercial.ar",)),
        }
        for key, (sequence, dependencies) in expected.items():
            generator = GENERATOR_REGISTRY.get(key)
            self.assertEqual(generator.sequence, sequence)
            self.assertEqual(generator.depends_on, dependencies)
            self.assertEqual(generator.phase, "18_commercial")
        self.assertTrue(GENERATOR_REGISTRY.validate())

    def test_whole_path_contract_and_financial_reset_policy(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "generators/commercial/finance.py").read_text()
        for token in (
            "COMMERCIAL_CONTRACTS", "COMMERCIAL_GROUPS",
            "MASTER PROMPT 18 whole-path runtime preflight failed",
            "action_create_clinic_billing", "create_from_billing",
            "action_generate_account_move", "action_post_account_move",
            "action_submit", "action_approve", "action_post",
            "RESET_FRESH_DB_ONLY", "DEMO-BILL-001", "DEMO-AR-001", "DEMO-AP-001",
            "_reconcile_actor_scope", "_prepare_deferred_billing_line",
            "allowed_company_ids", "allowed_branch_ids",
            "base.group_partner_manager",
        ):
            self.assertIn(token, source)

    def test_stage_aware_adoption_is_explicit(self):
        root = Path(__file__).resolve().parents[1]
        run_source = (root / "models/demo_run.py").read_text()
        helper = (root / "services/progressive_adoption.py").read_text()
        for token in (
            "prompt18_sequence", "progressive_prompt18_adoption",
            "prompt18_runtime_repair_adoption", "prompt18_failed_key",
            "Prompt 18 progressive contract adopted after completed Prompt-17 scope",
        ):
            self.assertIn(token, run_source)
        self.assertIn("checkpoints == completed_generators | prefix | {failed_key}", helper)

    def test_ar_demo_identity_has_narrow_owner_context_contract(self):
        root = Path(__file__).resolve().parents[2]
        ar_source = (root / "clinic_ar/models/ar_invoice.py").read_text()
        demo_source = (root / "clinic_demo/generators/commercial/finance.py").read_text()
        self.assertIn('self.env.context.get("clinic_demo_ar_name")', ar_source)
        self.assertIn('clinic_demo_ar_name="DEMO-AR-001"', demo_source)
        billing_source = (root / "clinic_billing/models/billing_invoice.py").read_text()
        self.assertIn('self.env.context.get("clinic_demo_billing_name")', billing_source)
        self.assertIn('clinic_demo_billing_name="DEMO-BILL-001"', demo_source)

    def test_owner_accounting_uses_real_billing_lines(self):
        root = Path(__file__).resolve().parents[2]
        billing_source = (root / "clinic_billing/models/billing_invoice.py").read_text()
        method = billing_source.split("def _collect_planned_lines", 1)[1].split(
            "def _apply_pricing_rules", 1
        )[0]
        self.assertIn("self.line_ids.sorted", method)
        self.assertIn("line.get_effective_unit_price()", method)
        self.assertIn("line.tax_ids.ids", method)
        self.assertNotIn("_ensure_placeholder_service_product", method)






















