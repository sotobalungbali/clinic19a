#!/usr/bin/env python3
"""Standalone MASTER PROMPT 18 whole-path source contracts."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT.parent
FINANCE = ROOT / "generators/commercial/finance.py"
BILLING = SUITE / "clinic_billing/models/billing_invoice.py"


class TestPrompt18SourceContracts(unittest.TestCase):
    def test_versions_and_registry(self):
        demo_manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        billing_manifest = ast.literal_eval(ast.parse((SUITE / "clinic_billing/__manifest__.py").read_text()).body[0].value)
        ap_manifest = ast.literal_eval(ast.parse((SUITE / "clinic_ap/__manifest__.py").read_text()).body[0].value)
        self.assertEqual(demo_manifest["version"], "19.0.1.0.46")
        self.assertEqual(billing_manifest["version"], "19.0.3.0.5")
        self.assertEqual(ap_manifest["version"], "19.0.3.0.3")
        source = FINANCE.read_text()
        for key in ("commercial.billing", "commercial.ar", "commercial.ap"):
            self.assertIn(f'key = "{key}"', source)

    def test_actor_scope_precedes_protected_session_read(self):
        source = FINANCE.read_text()
        method = source.split("def _prepare_whole_path", 1)[1].split("def _prepare_deferred_billing_line", 1)[0]
        self.assertLess(method.index("_reconcile_actor_scope"), method.index('"DEMO-SESSION-001"'))
        for token in (
            "allowed_company_ids", "allowed_branch_ids", "record_user=manager",
            '"base.group_partner_manager"',
            '"clinic.treatment.session": ("read", "write")',
            '"clinic.treatment.session.line": ("read", "write")',
        ):
            self.assertIn(token, source)

    def test_deferred_line_has_exact_shape_guard(self):
        source = FINANCE.read_text()
        method = source.split("def _prepare_deferred_billing_line", 1)[1].split("def _bind", 1)[0]
        for token in (
            "line.is_billable", "line.product_id", "line.price_unit",
            '"product_id": product.id', '"is_billable": True',
            "action_prepare_billing", "len(payloads) != 1",
        ):
            self.assertIn(token, method)

    def test_accounting_move_uses_real_billing_lines(self):
        method = BILLING.read_text().split("def _collect_planned_lines", 1)[1].split(
            "def _apply_pricing_rules", 1
        )[0]
        for token in (
            'self.line_ids.sorted("sequence")', "line.get_effective_unit_price()",
            "line.tax_ids.ids", "_resolve_income_account(line.product_id)",
        ):
            self.assertIn(token, method)
        self.assertNotIn("_ensure_placeholder_service_product", method)

    def test_accounting_lines_are_a_related_mirror(self):
        source = BILLING.read_text()
        self.assertIn('related="move_id.line_ids"', source)
        self.assertNotIn('inverse_name="move_id"', source)

    def test_runtime_generator_has_no_privilege_or_sequence_bypass(self):
        source = FINANCE.read_text()
        for forbidden in (".sudo(", ".cr.commit(", ".execute(", "next_by_code", "uuid4"):
            self.assertNotIn(forbidden, source)

    def test_prompt18_ap_uses_the_odoo19_uom_contract(self):
        finance = FINANCE.read_text()
        ap_line = (SUITE / "clinic_ap/models/ap_line.py").read_text()
        self.assertIn('"product_uom_id": product.uom_id.id', finance)
        self.assertIn("line.product_uom_id = line.product_id.uom_id", ap_line)
        self.assertNotIn("uom_po_id", finance)
        self.assertNotIn("uom_po_id", ap_line)
        self.assertIn('("product.product", "uom_id"): "uom.uom"', finance)


if __name__ == "__main__":
    unittest.main()






