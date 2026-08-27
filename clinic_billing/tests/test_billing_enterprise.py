# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


PERSISTENT_MODELS = [
    "clinic.billing.invoice",
    "clinic.billing.line",
    "clinic.billing.payment",
    "clinic.billing.payment.line",
    "clinic.billing.discount.rule",
    "clinic.billing.discount.redemption",
    "clinic.billing.voucher.program",
    "clinic.billing.voucher",
    "clinic.billing.voucher.redemption",
    "clinic.insurance.claim",
    "clinic.insurance.claim.line",
    "clinic.billing.commission.rule",
    "clinic.billing.commission.line",
    "clinic.billing.commission.settlement",
    "clinic.billing.gateway.tx",
    "clinic.billing.gateway.event",
    "clinic.billing.membership.usage",
    "clinic.treatment.billing.link",
    "clinic.billing.integration.event",
]


@tagged("post_install", "-at_install")
class TestClinicBillingEnterprise(TransactionCase):
    """Registry/UI/security contracts for the ClinicOne billing owner module."""

    def test_01_owner_models_are_registered(self):
        for model_name in PERSISTENT_MODELS:
            self.assertIn(model_name, self.env)

    def test_02_invoice_has_enterprise_core_fields(self):
        required = {
            "line_ids", "clinic_patient_id", "clinic_doctor_id", "patient_id",
            "booking_id", "encounter_id", "care_plan_id", "package_allocation_id",
            "move_id", "state", "amount_total", "amount_residual",
        }
        self.assertFalse(required - set(self.env["clinic.billing.invoice"]._fields))

    def test_03_billing_line_has_typed_clinical_traceability(self):
        required = {
            "treatment_id", "booking_id", "encounter_id", "care_plan_id",
            "care_plan_line_id", "package_usage_id", "emar_administration_id",
            "treatment_usage_id", "room_id", "device_id",
        }
        self.assertFalse(required - set(self.env["clinic.billing.line"]._fields))

    def test_04_invoice_line_contract_is_explicit(self):
        field = self.env["clinic.billing.invoice"]._fields["line_ids"]
        self.assertEqual(field.comodel_name, "clinic.billing.line")
        self.assertEqual(field.inverse_name, "invoice_id")

    def test_05_payment_orchestration_models_are_registered(self):
        self.assertIn("clinic.billing.payment", self.env)
        self.assertIn("clinic.billing.payment.line", self.env)
        self.assertIn("clinic.billing.payment.account.builder", self.env)

    def test_06_account_payment_bridge_fields_exist(self):
        fields_map = self.env["account.payment"]._fields
        self.assertIn("clinic_invoice_id", fields_map)
        self.assertIn("clinic_payment_id", fields_map)
        self.assertIn("clinic_gateway_tx_id", fields_map)

    def test_07_odoo19_account_payment_contract_is_used(self):
        fields_map = self.env["account.payment"]._fields
        self.assertIn("memo", fields_map)
        self.assertIn("payment_reference", fields_map)
        state_values = dict(fields_map["state"].selection)
        self.assertIn("in_process", state_values)
        self.assertIn("paid", state_values)

    def test_08_patient_bridge_is_registered(self):
        self.assertIn("billing_invoice_count", self.env["clinic.patient"]._fields)
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_view_billing_invoices"))

    def test_09_doctor_bridge_is_registered(self):
        self.assertIn("billing_invoice_count", self.env["clinic.doctor"]._fields)
        self.assertTrue(hasattr(self.env["clinic.doctor"], "action_view_billing_invoices"))

    def test_10_booking_bridge_is_registered(self):
        self.assertIn("billing_invoice_count", self.env["booking.booking"]._fields)
        self.assertTrue(hasattr(self.env["booking.booking"], "action_view_billing_invoices"))

    def test_11_encounter_bridge_is_registered(self):
        self.assertIn("billing_invoice_count", self.env["clinic.encounter"]._fields)
        self.assertTrue(hasattr(self.env["clinic.encounter"], "action_view_billing_invoices"))

    def test_12_care_plan_bridge_is_registered(self):
        self.assertIn("billing_document_count", self.env["clinic.care.plan"]._fields)
        self.assertTrue(hasattr(self.env["clinic.care.plan"], "action_view_billing_documents"))

    def test_13_package_allocation_bridge_is_registered(self):
        self.assertIn("billing_document_count", self.env["clinic.package.allocation"]._fields)

    def test_14_package_usage_bridge_is_registered(self):
        self.assertIn("billing_line_count", self.env["clinic.package.usage"]._fields)

    def test_15_emar_administration_bridge_is_registered(self):
        self.assertIn("billing_line_count", self.env["clinic.emar.administration"]._fields)

    def test_16_invoice_sequence_exists(self):
        seq = self.env["ir.sequence"].sudo().search([("code", "=", "clinic.billing.invoice")], limit=1)
        self.assertTrue(seq)

    def test_17_integration_event_sequence_exists(self):
        seq = self.env["ir.sequence"].sudo().search([("code", "=", "clinic.billing.integration.event")], limit=1)
        self.assertTrue(seq)

    def test_18_invoice_search_view_exists(self):
        self.assertTrue(self.env.ref("clinic_billing.view_clinic_billing_invoice_search"))

    def test_19_invoice_list_view_exists(self):
        self.assertTrue(self.env.ref("clinic_billing.view_clinic_billing_invoice_list"))

    def test_20_invoice_form_view_exists(self):
        self.assertTrue(self.env.ref("clinic_billing.view_clinic_billing_invoice_form"))

    def test_21_all_primary_models_have_search_list_form_views(self):
        View = self.env["ir.ui.view"].sudo()
        for model_name in PERSISTENT_MODELS:
            views = View.search([("model", "=", model_name), ("type", "in", ("search", "list", "form"))])
            types = set(views.mapped("type"))
            self.assertTrue({"search", "list", "form"}.issubset(types), model_name)

    def test_22_acl_contract_covers_every_persistent_model(self):
        Access = self.env["ir.model.access"].sudo()
        Model = self.env["ir.model"].sudo()
        for model_name in PERSISTENT_MODELS:
            model = Model.search([("model", "=", model_name)], limit=1)
            self.assertTrue(model, model_name)
            self.assertTrue(Access.search_count([("model_id", "=", model.id)]), model_name)

    def test_23_company_rules_exist_for_owner_models(self):
        Rule = self.env["ir.rule"].sudo()
        Model = self.env["ir.model"].sudo()
        for model_name in PERSISTENT_MODELS:
            model = Model.search([("model", "=", model_name)], limit=1)
            self.assertTrue(Rule.search_count([("model_id", "=", model.id)]), model_name)

    def test_24_invoice_state_lifecycle_contract(self):
        selection = dict(self.env["clinic.billing.invoice"]._fields["state"].selection)
        for value in ("draft", "confirmed", "posted", "paid", "cancelled"):
            self.assertIn(value, selection)

    def test_25_payment_state_lifecycle_contract(self):
        selection = dict(self.env["clinic.billing.payment"]._fields["state"].selection)
        for value in ("draft", "confirmed", "posted", "cancelled"):
            self.assertIn(value, selection)

    def test_26_overdue_field_is_searchable(self):
        field = self.env["clinic.billing.invoice"]._fields["is_overdue"]
        self.assertTrue(field.search)

    def test_27_paid_field_is_searchable(self):
        field = self.env["clinic.billing.invoice"]._fields["is_paid"]
        self.assertTrue(field.search)

    def test_28_runtime_ui_bridge_method_exists(self):
        self.assertTrue(hasattr(self.env["clinic.billing.invoice"], "_ensure_cross_addon_billing_views"))

    def test_29_integration_event_lifecycle_methods_exist(self):
        model = self.env["clinic.billing.integration.event"]
        for method in ("action_mark_processed", "action_retry", "action_ignore"):
            self.assertTrue(hasattr(model, method))

    def test_30_clinical_import_actions_exist(self):
        model = self.env["clinic.billing.invoice"]
        for method in ("action_import_from_booking", "action_import_from_care_plan", "action_import_from_emar"):
            self.assertTrue(hasattr(model, method))

    def test_31_accounting_actions_exist(self):
        model = self.env["clinic.billing.invoice"]
        for method in (
            "action_generate_account_move",
            "action_sync_lines_to_account_move",
            "action_post_account_move",
            "action_register_payment",
        ):
            self.assertTrue(hasattr(model, method))

    def test_32_billing_line_financial_amounts_are_stored(self):
        fields_map = self.env["clinic.billing.line"]._fields
        for field_name in ("subtotal_excl_tax", "tax_amount", "total_incl_tax"):
            self.assertTrue(fields_map[field_name].store, field_name)

    def test_33_integration_event_model_is_company_scoped(self):
        field = self.env["clinic.billing.integration.event"]._fields["company_id"]
        self.assertEqual(field.comodel_name, "res.company")

    def test_34_soft_wallet_does_not_become_hard_registry_owner(self):
        # clinic.wallet is consumed only through soft lookup; billing does not own it.
        self.assertNotEqual(self.env["clinic.billing.membership.usage"]._name, "clinic.wallet")

    def test_35_odoo19_billing_group_privilege_hierarchy(self):
        privilege = self.env.ref("clinic_billing.privilege_clinic_billing")
        user_group = self.env.ref("clinic_billing.group_clinic_billing_user")
        cashier_group = self.env.ref("clinic_billing.group_clinic_billing_cashier")
        manager_group = self.env.ref("clinic_billing.group_clinic_billing_manager")
        self.assertEqual(user_group.privilege_id, privilege)
        self.assertEqual(cashier_group.privilege_id, privilege)
        self.assertEqual(manager_group.privilege_id, privilege)

    def test_36_odoo19_account_account_company_contract(self):
        Account = self.env["account.account"]
        self.assertNotIn("company_id", Account._fields)
        self.assertIn("company_ids", Account._fields)
        self.assertTrue(hasattr(Account, "_check_company_domain"))

    def test_37_commission_accounts_enforce_company_consistency(self):
        fields_map = self.env["clinic.billing.commission.settlement"]._fields
        self.assertTrue(fields_map["expense_account_id"].check_company)
        self.assertTrue(fields_map["payable_account_id"].check_company)

    def test_38_settings_accounts_enforce_company_consistency(self):
        fields_map = self.env["res.config.settings"]._fields
        self.assertTrue(fields_map["commission_expense_account_id"].check_company)
        self.assertTrue(fields_map["commission_payable_account_id"].check_company)

    def test_39_doctor_accounts_enforce_company_consistency(self):
        fields_map = self.env["res.partner"]._fields
        self.assertTrue(fields_map["commission_expense_account_id"].check_company)
        self.assertTrue(fields_map["commission_payable_account_id"].check_company)

    def test_40_odoo19_core_partner_credit_limit_contract(self):
        field = self.env["res.partner"]._fields["credit_limit"]
        self.assertEqual(field.type, "float")
        self.assertTrue(field.company_dependent)

