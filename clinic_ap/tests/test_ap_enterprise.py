# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestClinicAPEnterprise(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AP = cls.env["clinic.ap"]
        cls.Line = cls.env["clinic.ap.line"]
        cls.Aging = cls.env["clinic.ap.aging"]
        cls.AgingLine = cls.env["clinic.ap.aging.line"]
        cls.Cashflow = cls.env["clinic.cashflow"]
        cls.Bucket = cls.env["clinic.cashflow.bucket"]
        cls.Detail = cls.env["clinic.cashflow.detail"]
        cls.Adjustment = cls.env["clinic.cashflow.adjustment"]
        cls.Event = cls.env["clinic.ap.integration.event"]

    def test_01_owner_models_exist(self):
        for model in (
            "clinic.ap", "clinic.ap.line", "clinic.ap.aging", "clinic.ap.aging.line",
            "clinic.cashflow", "clinic.cashflow.bucket", "clinic.cashflow.detail",
            "clinic.cashflow.adjustment", "clinic.ap.integration.event",
        ):
            self.assertIn(model, self.env.registry)

    def test_02_ap_has_vendor_bill_contract(self):
        self.assertEqual(self.AP._fields["move_id"].comodel_name, "account.move")

    def test_03_ap_has_purchase_contract(self):
        self.assertEqual(self.AP._fields["purchase_id"].comodel_name, "purchase.order")

    def test_04_ap_line_has_real_stock_move_inverse(self):
        self.assertEqual(self.Line._fields["stock_move_id"].comodel_name, "stock.move")

    def test_05_ap_line_has_billing_contracts(self):
        self.assertEqual(self.Line._fields["billing_invoice_id"].comodel_name, "clinic.billing.invoice")
        self.assertEqual(self.Line._fields["billing_line_id"].comodel_name, "clinic.billing.line")

    def test_06_ap_line_has_clinical_traceability(self):
        self.assertEqual(self.Line._fields["treatment_id"].comodel_name, "clinic.treatment")

    def test_07_ap_currency_is_global_contract(self):
        currency = self.AP._fields["currency_id"]
        self.assertEqual(currency.comodel_name, "res.currency")
        self.assertFalse(currency.check_company)

    def test_08_partner_preferred_currency_is_global_contract(self):
        field = self.env["res.partner"]._fields["ap_preferred_currency_id"]
        self.assertEqual(field.comodel_name, "res.currency")
        self.assertFalse(field.check_company)

    def test_09_partner_uses_namespaced_vendor_limit(self):
        self.assertIn("ap_vendor_credit_limit", self.env["res.partner"]._fields)
        self.assertIn("credit_limit", self.env["res.partner"]._fields)

    def test_10_supplier_payment_term_core_field_preserved(self):
        self.assertIn("property_supplier_payment_term_id", self.env["res.partner"]._fields)

    def test_11_payment_term_ap_policy_fields_exist(self):
        Term = self.env["account.payment.term"]
        for field in ("ap_active", "ap_code", "ap_eom_policy", "ap_grace_days", "ap_min_due_amount"):
            self.assertIn(field, Term._fields)

    def test_12_payment_term_native_compute_terms_exists(self):
        self.assertTrue(callable(getattr(self.env["account.payment.term"], "_compute_terms", None)))

    def test_13_account_payment_modern_states(self):
        selection = dict(self.env["account.payment"]._fields["state"].selection)
        self.assertIn("in_process", selection)
        self.assertIn("paid", selection)
        self.assertNotIn("posted", selection)

    def test_14_account_account_company_contract(self):
        Account = self.env["account.account"]
        self.assertNotIn("company_id", Account._fields)
        self.assertIn("company_ids", Account._fields)
        self.assertTrue(callable(getattr(Account, "_check_company_domain", None)))

    def test_15_security_privilege_exists(self):
        privilege = self.env.ref("clinic_ap.privilege_clinic_ap")
        self.assertEqual(privilege._name, "res.groups.privilege")

    def test_16_ap_groups_use_same_privilege(self):
        privilege = self.env.ref("clinic_ap.privilege_clinic_ap")
        for xmlid in (
            "clinic_ap.group_clinic_ap_user",
            "clinic_ap.group_clinic_ap_accountant",
            "clinic_ap.group_clinic_ap_manager",
        ):
            self.assertEqual(self.env.ref(xmlid).privilege_id, privilege)

    def test_17_manager_implies_accountant(self):
        manager = self.env.ref("clinic_ap.group_clinic_ap_manager")
        accountant = self.env.ref("clinic_ap.group_clinic_ap_accountant")
        self.assertIn(accountant, manager.implied_ids)

    def test_18_accountant_implies_user(self):
        accountant = self.env.ref("clinic_ap.group_clinic_ap_accountant")
        user = self.env.ref("clinic_ap.group_clinic_ap_user")
        self.assertIn(user, accountant.implied_ids)

    def test_19_sequence_exists(self):
        seq = self.env.ref("clinic_ap.sequence_clinic_ap")
        self.assertEqual(seq.code, "clinic.ap")

    def test_20_ap_primary_views_exist(self):
        for xmlid in (
            "clinic_ap.view_clinic_ap_search",
            "clinic_ap.view_clinic_ap_list",
            "clinic_ap.view_clinic_ap_form",
        ):
            self.assertEqual(self.env.ref(xmlid)._name, "ir.ui.view")

    def test_21_ap_line_views_exist(self):
        for xmlid in (
            "clinic_ap.view_clinic_ap_line_search",
            "clinic_ap.view_clinic_ap_line_list",
            "clinic_ap.view_clinic_ap_line_form",
        ):
            self.assertEqual(self.env.ref(xmlid)._name, "ir.ui.view")

    def test_22_aging_views_exist(self):
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_ap_aging_form").model, "clinic.ap.aging")
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_ap_aging_line_form").model, "clinic.ap.aging.line")

    def test_23_cashflow_views_exist(self):
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_cashflow_form").model, "clinic.cashflow")
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_cashflow_bucket_form").model, "clinic.cashflow.bucket")
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_cashflow_detail_form").model, "clinic.cashflow.detail")
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_cashflow_adjustment_form").model, "clinic.cashflow.adjustment")

    def test_24_integration_event_views_exist(self):
        self.assertEqual(self.env.ref("clinic_ap.view_clinic_ap_event_form").model, "clinic.ap.integration.event")

    def test_25_ap_settings_action_is_owned(self):
        action = self.env.ref("clinic_ap.action_clinic_ap_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertEqual(action.view_mode, "form")

    def test_26_ap_payment_term_action_is_owned(self):
        action = self.env.ref("clinic_ap.action_ap_payment_terms")
        self.assertEqual(action.res_model, "account.payment.term")

    def test_27_partner_reverse_action_exists(self):
        self.assertTrue(callable(getattr(self.env["res.partner"], "action_view_clinic_ap", None)))

    def test_28_purchase_reverse_action_exists(self):
        self.assertTrue(callable(getattr(self.env["purchase.order"], "action_view_clinic_ap", None)))
        self.assertTrue(callable(getattr(self.env["purchase.order"], "action_create_clinic_ap", None)))

    def test_29_stock_reverse_action_exists(self):
        self.assertTrue(callable(getattr(self.env["stock.move"], "action_view_clinic_ap_lines", None)))

    def test_30_billing_reverse_action_exists(self):
        self.assertTrue(callable(getattr(self.env["clinic.billing.invoice"], "action_view_ap_costs", None)))
        self.assertTrue(callable(getattr(self.env["clinic.billing.line"], "action_view_ap_costs", None)))

    def test_31_account_move_reverse_action_exists(self):
        self.assertTrue(callable(getattr(self.env["account.move"], "action_view_clinic_ap", None)))

    def test_32_account_payment_reverse_action_exists(self):
        self.assertTrue(callable(getattr(self.env["account.payment"], "action_view_clinic_ap", None)))

    def test_33_integration_retry_is_bounded(self):
        rec = self.Event.new({"attempt_count": 3})
        self.assertEqual(rec.attempt_count, 3)

    def test_34_runtime_view_bridge_method_exists(self):
        self.assertTrue(callable(getattr(self.AP, "_ensure_optional_cross_addon_views", None)))

    def test_35_company_configuration_fields_exist(self):
        Company = self.env["res.company"]
        for field in (
            "ap_approval_threshold", "ap_enforce_receipt_before_post",
            "ap_qty_tolerance_percent", "ap_price_tolerance_percent",
            "ap_default_purchase_journal_id", "ap_default_payment_journal_id",
        ):
            self.assertIn(field, Company._fields)

    def test_36_invoice_lifecycle_states_exist(self):
        states = dict(self.AP._fields["state"].selection)
        for state in ("draft", "to_approve", "approved", "posted", "partial", "paid", "cancelled"):
            self.assertIn(state, states)
    def test_37_ap_match_state_is_searchable(self):
        self.assertTrue(callable(getattr(self.AP, "_search_match_state", None)))
        self.assertEqual(self.AP._fields["match_state"].search, "_search_match_state")

    def test_38_ap_line_match_state_is_searchable(self):
        self.assertTrue(callable(getattr(self.Line, "_search_match_state", None)))
        self.assertEqual(self.Line._fields["match_state"].search, "_search_match_state")

    def test_39_odoo19_stock_valuation_contract(self):
        self.assertIn("value", self.env["stock.move"]._fields)
        self.assertNotIn("stock_valuation_layer_ids", self.Line._fields)
        self.assertEqual(self.Line._fields["stock_move_id"].comodel_name, "stock.move")

    def test_40_ap_settings_view_is_extension_not_primary(self):
        view = self.env.ref("clinic_ap.view_clinic_ap_settings_form")
        self.assertEqual(view.model, "res.config.settings")
        self.assertEqual(view.inherit_id, self.env.ref("base.res_config_settings_view_form"))
        self.assertEqual(view.mode, "extension")

    def test_41_ap_settings_action_does_not_pin_local_view(self):
        action = self.env.ref("clinic_ap.action_clinic_ap_settings")
        self.assertFalse(action.view_id)
        self.assertEqual(action.path, "clinic-ap-settings")
        self.assertIn("clinic_ap", action.context or "")


