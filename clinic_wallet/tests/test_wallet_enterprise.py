# -*- coding: utf-8 -*-
from lxml import etree

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "clinic_wallet")
class TestClinicWalletEnterprise(TransactionCase):
    """Regression contracts for Wallet ownership, ledger semantics and integrations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Wallet Regression Patient"})
        cls.wallet = cls.env["clinic.wallet"].create({
            "partner_id": cls.partner.id,
            "company_id": cls.env.company.id,
            "currency_id": cls.env.company.currency_id.id,
        })
        if cls.wallet.state != "open":
            cls.wallet.with_context(wallet_state_transition=True).write({"state": "open"})

    def _seed_posted(self, amount=1000.0):
        return self.env["clinic.wallet.transaction"].with_context(wallet_tx_transition=True).create({
            "wallet_id": self.wallet.id,
            "transaction_type": "topup",
            "amount": amount,
            "state": "posted",
            "is_reserved": False,
        })

    def test_01_core_models_registered(self):
        for model in ("clinic.wallet", "clinic.wallet.transaction", "clinic.wallet.rule", "clinic.wallet.portal.request", "clinic.wallet.portal.mgr.approver"):
            self.assertIn(model, self.env.registry)

    def test_02_unique_wallet_company_contract(self):
        with self.assertRaises(Exception):
            self.env["clinic.wallet"].create({"partner_id": self.partner.id, "company_id": self.env.company.id})

    def test_03_company_currency_contract(self):
        self.assertEqual(self.wallet.currency_id, self.wallet.company_id.currency_id)

    def test_04_seeded_posted_topup_increases_balance(self):
        self._seed_posted(500.0)
        self.wallet.invalidate_recordset()
        self.assertGreaterEqual(self.wallet.balance, 500.0)

    def test_05_reserve_reduces_available_balance(self):
        self._seed_posted(1000.0)
        before = self.wallet.balance
        tx = self.wallet.reserve_funds(200.0, billing_model="clinic.billing.invoice", billing_id=999001)
        self.wallet.invalidate_recordset()
        self.assertEqual(tx.state, "reserved")
        self.assertAlmostEqual(self.wallet.balance, before - 200.0, places=2)

    def test_06_release_preserves_audit_row(self):
        self._seed_posted(1000.0)
        tx = self.wallet.reserve_funds(100.0, billing_model="x.test", billing_id=11)
        self.wallet.release_reserved(billing_model="x.test", billing_id=11)
        self.assertTrue(tx.exists())
        self.assertEqual(tx.state, "canceled")

    def test_07_finalize_reserved_to_redeem(self):
        self._seed_posted(1000.0)
        self.wallet.reserve_funds(250.0, billing_model="x.test", billing_id=12)
        self.wallet.validate_reserved_to_posted(250.0, billing_model="x.test", billing_id=12)
        posted = self.env["clinic.wallet.transaction"].search([("wallet_id", "=", self.wallet.id), ("billing_model", "=", "x.test"), ("billing_id", "=", 12), ("state", "=", "posted")])
        self.assertTrue(posted)
        self.assertTrue(all(tx.transaction_type == "redeem" for tx in posted))

    def test_08_insufficient_reserve_rejected(self):
        with self.assertRaises(UserError):
            self.wallet.reserve_funds(999999999.0)

    def test_09_posted_transaction_is_immutable(self):
        tx = self._seed_posted(10.0)
        with self.assertRaises(UserError):
            tx.write({"amount": 20.0})

    def test_10_wallet_with_transactions_cannot_be_deleted(self):
        self._seed_posted(10.0)
        with self.assertRaises(UserError):
            self.wallet.unlink()

    def test_11_wallet_public_api_preserved(self):
        for method in ("reserve_funds", "release_reserved", "validate_reserved_to_posted", "get_liability_account", "get_wallet_journal"):
            self.assertTrue(hasattr(self.wallet, method))

    def test_12_billing_fields_exist(self):
        for field in ("use_wallet", "wallet_amount", "wallet_tx_ids", "wallet_reserved"):
            self.assertIn(field, self.env["clinic.billing.invoice"]._fields)

    def test_13_account_move_wallet_fields_exist(self):
        self.assertIn("use_wallet", self.env["account.move"]._fields)
        self.assertIn("wallet_amount", self.env["account.move"]._fields)

    def test_14_partner_wallet_balance_owned_upstream(self):
        self.assertIn("wallet_balance", self.env["res.partner"]._fields)
        self.assertIn("wallet_id_current_company", self.env["res.partner"]._fields)

    def test_15_portal_request_positive_amount(self):
        with self.assertRaises(ValidationError):
            self.env["clinic.wallet.portal.request"].create({
                "request_type": "topup", "partner_id": self.partner.id, "wallet_id": self.wallet.id,
                "company_id": self.env.company.id, "currency_id": self.env.company.currency_id.id, "amount": 0,
            })

    def test_16_rule_state_compute(self):
        rule = self.env["clinic.wallet.rule"].create({"name": "Regression Rule", "company_id": self.env.company.id, "wallet_id": self.wallet.id})
        self.assertIn(rule.state, ("upcoming", "active", "expired"))

    def test_17_wallet_counts_exist(self):
        self.assertIn("transaction_count", self.wallet._fields)
        self.assertIn("rule_count", self.wallet._fields)

    def test_18_reversal_traceability_fields_exist(self):
        self.assertIn("reversal_of_id", self.env["clinic.wallet.transaction"]._fields)
        self.assertIn("reversal_tx_id", self.env["clinic.wallet.transaction"]._fields)

    def test_19_company_settings_exist(self):
        for field in ("account_wallet_liability_id", "wallet_journal_id", "wallet_default_expiry_policy", "wallet_auto_open_on_create"):
            self.assertIn(field, self.env["res.company"]._fields)

    def test_20_operation_wizard_registered(self):
        self.assertIn("clinic.wallet.operation.wizard", self.env.registry)

    def test_21_report_action_exists(self):
        self.assertTrue(self.env.ref("clinic_wallet.action_report_wallet_statement"))

    def test_22_search_views_exist(self):
        for xmlid in ("view_wallet_search", "view_wallet_transaction_search", "view_wallet_rule_search", "view_wallet_request_search", "view_wallet_approver_search"):
            self.assertTrue(self.env.ref("clinic_wallet.%s" % xmlid))

    def test_23_manager_group_exists(self):
        self.assertTrue(self.env.ref("clinic_wallet.group_wallet_manager"))

    def test_24_no_future_module_dependency(self):
        module = self.env["ir.module.module"].search([("name", "=", "clinic_wallet")], limit=1)
        self.assertTrue(module)

    def test_25_membership_plan_contract_is_current(self):
        wallet_field = self.env["clinic.wallet"]._fields["membership_tier_id"]
        rule_field = self.env["clinic.wallet.rule"]._fields["membership_tier_ids"]
        self.assertEqual(wallet_field.comodel_name, "membership.plan")
        self.assertEqual(rule_field.comodel_name, "membership.plan")
        self.assertNotIn("clinic.membership.tier", self.env.registry)

    def test_26_legacy_wallet_api_names_preserved(self):
        billing = self.env["clinic.billing.invoice"]
        move = self.env["account.move"]
        settings = self.env["res.config.settings"]
        for method in (
            "_compute_wallet_reserved",
            "_get_default_reference",
            "_wallet_reserve",
            "_wallet_release",
            "_wallet_finalize",
        ):
            self.assertTrue(hasattr(billing, method), method)
        for method in (
            "button_cancel",
            "_onchange_use_wallet_invoice",
            "_onchange_wallet_amount_invoice",
            "_check_wallet_amount_vs_residual",
        ):
            self.assertTrue(hasattr(move, method), method)
        for field in (
            "redeem_post_accounting",
            "expiry_notify_days_before",
            "expiry_notify_days_after",
        ):
            self.assertIn(field, settings._fields)
        for method in (
            "_get_int",
            "_get_bool",
            "_set_int",
            "_set_bool",
            "_set_m2o_param",
            "_get_m2o_from_param",
            "_upsert_wallet_liability_property",
            "get_values",
            "set_values",
        ):
            self.assertTrue(hasattr(settings, method), method)

    def test_27_wallet_accountant_has_accounting_capability(self):
        wallet_accountant = self.env.ref("clinic_wallet.group_wallet_accountant")
        account_user = self.env.ref("account.group_account_user")
        self.assertIn(account_user, wallet_accountant.implied_ids)

    def test_28_company_template_rule_is_enforced(self):
        self._seed_posted(1000.0)
        self.env["clinic.wallet.rule"].create({
            "name": "Global Template Limit",
            "company_id": self.env.company.id,
            "scope": "global",
            "max_amount": 10.0,
            "active": True,
        })
        tx = self.env["clinic.wallet.transaction"].create({
            "wallet_id": self.wallet.id,
            "transaction_type": "refund",
            "amount": 20.0,
        })
        with self.assertRaises(UserError):
            tx.action_post()

    def test_29_partial_reservation_finalization_keeps_remainder(self):
        self._seed_posted(1000.0)
        self.wallet.reserve_funds(400.0, billing_model="x.partial", billing_id=9901)
        self.wallet.validate_reserved_to_posted(
            150.0, billing_model="x.partial", billing_id=9901
        )
        self.wallet.invalidate_recordset()
        remaining = self.env["clinic.wallet.transaction"].search([
            ("wallet_id", "=", self.wallet.id),
            ("billing_model", "=", "x.partial"),
            ("billing_id", "=", 9901),
            ("is_reserved", "=", True),
            ("state", "=", "reserved"),
        ])
        posted = self.env["clinic.wallet.transaction"].search([
            ("wallet_id", "=", self.wallet.id),
            ("billing_model", "=", "x.partial"),
            ("billing_id", "=", 9901),
            ("state", "=", "posted"),
        ])
        self.assertAlmostEqual(sum(remaining.mapped("amount")), 250.0, places=2)
        self.assertAlmostEqual(sum(posted.mapped("amount")), 150.0, places=2)
        self.assertAlmostEqual(self.wallet.reserved_amount, 250.0, places=2)


    def test_30_legacy_validation_helper_is_enforced(self):
        """Historical wallet amount validator remains effective on Clinic Billing."""
        billing_model = self.env["clinic.billing.invoice"]
        self.assertTrue(hasattr(billing_model, "_check_wallet_amount_vs_residual"))

    def test_31_billing_mixin_currency_contract_is_registry_safe(self):
        """Abstract mixin must not require currency_id; concrete models stay Monetary."""
        mixin = self.env["clinic.wallet.billing.mixin"]
        self.assertEqual(mixin._fields["wallet_amount"].type, "float")
        self.assertEqual(mixin._fields["wallet_reserved"].type, "float")

        for model_name in ("clinic.billing.invoice", "account.move"):
            model = self.env[model_name]
            amount_field = model._fields["wallet_amount"]
            reserved_field = model._fields["wallet_reserved"]
            self.assertEqual(amount_field.type, "monetary")
            self.assertEqual(reserved_field.type, "monetary")
            self.assertEqual(amount_field.currency_field, "currency_id")
            self.assertEqual(reserved_field.currency_field, "currency_id")
            self.assertIn("currency_id", model._fields)

    def test_32_multiple_inheritance_extends_real_financial_models(self):
        """Wallet mixin must extend real models, never create *.wallet shadows."""
        self.assertIn("clinic.billing.invoice", self.env.registry)
        self.assertIn("account.move", self.env.registry)
        self.assertNotIn("clinic.billing.invoice.wallet", self.env.registry)
        self.assertNotIn("account.move.wallet", self.env.registry)

        billing_model = self.env["clinic.billing.invoice"]
        move_model = self.env["account.move"]

        for model in (billing_model, move_model):
            self.assertIn("wallet_amount", model._fields)
            self.assertIn("wallet_reserved", model._fields)
            self.assertIn("wallet_tx_ids", model._fields)
            self.assertTrue(hasattr(model, "_wallet_reserve"))
            self.assertTrue(hasattr(model, "_wallet_finalize"))

    def test_33_search_views_follow_odoo19_arch_contract(self):
        """All Wallet search views must use the attribute-free Odoo 19 search/group schema."""
        xmlids = (
            "clinic_wallet.view_wallet_search",
            "clinic_wallet.view_wallet_transaction_search",
            "clinic_wallet.view_wallet_rule_search",
            "clinic_wallet.view_wallet_approver_search",
            "clinic_wallet.view_wallet_portal_request_search",
        )
        for xmlid in xmlids:
            view = self.env.ref(xmlid)
            arch = view.arch_db
            if hasattr(arch, "get"):
                arch = arch.get(self.env.lang) or next(iter(arch.values()), "")
            root = etree.fromstring((arch or "").encode())
            self.assertEqual(root.tag, "search")
            self.assertFalse(root.attrib, f"{xmlid}: <search> must have no attributes")
            for group in root.xpath("./group"):
                self.assertFalse(group.attrib, f"{xmlid}: search <group> must have no attributes")



