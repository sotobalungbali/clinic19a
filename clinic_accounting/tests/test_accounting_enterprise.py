from lxml import etree

from odoo.tests.common import TransactionCase


PERSISTENT_MODELS = (
    "clinic.accounting.ledger",
    "clinic.accounting.adjustment",
    "clinic.accounting.adjustment.line",
    "clinic.accounting.close",
    "clinic.accounting.close.check",
    "clinic.accounting.statement",
    "clinic.accounting.statement.line",
)


class TestClinicAccountingEnterprise(TransactionCase):

    def test_01_accounting_models_exist(self):
        for model in PERSISTENT_MODELS:
            self.assertIn(model, self.env.registry)

    def test_02_accounting_support_mixin_exists(self):
        self.assertIn("clinic.accounting.company.mixin", self.env.registry)

    def test_03_standard_accounting_models_exist(self):
        for model in ("account.account", "account.journal", "account.move", "account.move.line"):
            self.assertIn(model, self.env.registry)

    def test_04_upstream_financial_models_exist(self):
        for model in (
            "clinic.billing.invoice",
            "clinic.ar.invoice",
            "clinic.ar.payment",
            "clinic.ap",
            "clinic.wallet",
            "clinic.wallet.transaction",
            "clinic.finance.transaction",
            "clinic.finance.transfer",
            "clinic.finance.cash.session",
        ):
            self.assertIn(model, self.env.registry)

    def test_05_no_downstream_localization_dependency(self):
        module = self.env["ir.module.module"].search([("name", "=", "clinic_accounting")], limit=1)
        self.assertTrue(module)
        self.assertNotIn("clinic_l10n_id", module.dependencies_id.mapped("name"))

    def test_06_ledger_uses_standard_journals(self):
        self.assertEqual(
            self.env["clinic.accounting.ledger"]._fields["journal_ids"].comodel_name,
            "account.journal",
        )

    def test_07_ledger_uses_standard_accounts(self):
        self.assertEqual(
            self.env["clinic.accounting.ledger"]._fields["account_ids"].comodel_name,
            "account.account",
        )

    def test_08_adjustment_posts_standard_move(self):
        self.assertEqual(
            self.env["clinic.accounting.adjustment"]._fields["move_id"].comodel_name,
            "account.move",
        )

    def test_09_adjustment_line_uses_standard_account(self):
        self.assertEqual(
            self.env["clinic.accounting.adjustment.line"]._fields["account_id"].comodel_name,
            "account.account",
        )

    def test_10_move_has_adjustment_reverse_link(self):
        self.assertIn("clinic_accounting_adjustment_id", self.env["account.move"]._fields)

    def test_11_move_has_wallet_reverse_link(self):
        field = self.env["account.move"]._fields["clinic_wallet_transaction_ids"]
        self.assertEqual(field.comodel_name, "clinic.wallet.transaction")
        self.assertEqual(field.inverse_name, "move_id")

    def test_12_move_has_source_classification(self):
        move = self.env["account.move"]
        self.assertIn("clinic_accounting_source", move._fields)
        self.assertIn("clinic_accounting_source_detail", move._fields)
        self.assertIn("clinic_accounting_origin_count", move._fields)

    def test_13_move_line_has_stored_source_bridge(self):
        line = self.env["account.move.line"]
        self.assertIn("clinic_accounting_source", line._fields)
        self.assertIn("clinic_accounting_adjustment_id", line._fields)

    def test_14_source_selection_has_all_financial_owners(self):
        selection = dict(self.env["account.move"]._fields["clinic_accounting_source"].selection)
        for value in ("finance", "billing", "ar", "ap", "wallet", "adjustment", "mixed", "other"):
            self.assertIn(value, selection)

    def test_15_finance_move_traceability_contract(self):
        move = self.env["account.move"]
        self.assertIn("clinic_finance_transaction_id", move._fields)
        self.assertIn("clinic_finance_transfer_id", move._fields)

    def test_16_billing_move_traceability_contract(self):
        self.assertIn("clinic_invoice_id", self.env["account.move"]._fields)

    def test_17_ap_move_traceability_contract(self):
        self.assertIn("clinic_ap_ids", self.env["account.move"]._fields)

    def test_18_ar_move_traceability_contract(self):
        move = self.env["account.move"]
        self.assertIn("ar_invoice_ids", move._fields)
        self.assertIn("ar_payment_ids", move._fields)

    def test_19_wallet_transaction_move_contract(self):
        wallet_tx = self.env["clinic.wallet.transaction"]
        for field in ("move_id", "journal_id", "state", "date", "amount"):
            self.assertIn(field, wallet_tx._fields)

    def test_20_billing_close_contract(self):
        billing = self.env["clinic.billing.invoice"]
        for field in ("company_id", "invoice_date", "state", "move_id"):
            self.assertIn(field, billing._fields)
        states = dict(billing._fields["state"].selection)
        self.assertIn("posted", states)
        self.assertIn("paid", states)

    def test_21_ar_close_contract(self):
        ar = self.env["clinic.ar.invoice"]
        for field in ("company_id", "invoice_date", "state", "move_id"):
            self.assertIn(field, ar._fields)
        self.assertIn("posted", dict(ar._fields["state"].selection))

    def test_22_ap_close_contract(self):
        ap = self.env["clinic.ap"]
        for field in ("company_id", "invoice_date", "state", "move_id"):
            self.assertIn(field, ap._fields)
        states = dict(ap._fields["state"].selection)
        self.assertIn("posted", states)
        self.assertIn("partial", states)

    def test_23_finance_transaction_close_contract(self):
        tx = self.env["clinic.finance.transaction"]
        for field in ("company_id", "transaction_date", "state", "posting_policy", "move_id"):
            self.assertIn(field, tx._fields)

    def test_24_finance_transfer_close_contract(self):
        transfer = self.env["clinic.finance.transfer"]
        for field in ("company_id", "transfer_date", "state", "move_id"):
            self.assertIn(field, transfer._fields)

    def test_25_finance_cash_session_close_contract(self):
        session = self.env["clinic.finance.cash.session"]
        for field in ("company_id", "opened_at", "state"):
            self.assertIn(field, session._fields)

    def test_26_native_fiscal_lock_date_exists(self):
        self.assertIn("fiscalyear_lock_date", self.env["res.company"]._fields)

    def test_27_native_hard_lock_date_exists(self):
        self.assertIn("hard_lock_date", self.env["res.company"]._fields)

    def test_28_native_account_company_contract_is_odoo19(self):
        self.assertIn("company_ids", self.env["account.account"]._fields)

    def test_29_native_account_internal_group_exists(self):
        self.assertIn("internal_group", self.env["account.account"]._fields)

    def test_30_native_receivable_payable_reconciliation_fields_exist(self):
        line = self.env["account.move.line"]
        self.assertIn("reconciled", line._fields)
        account = self.env["account.account"]
        selection = dict(account._fields["account_type"].selection)
        self.assertIn("asset_receivable", selection)
        self.assertIn("liability_payable", selection)

    def test_31_branch_accounting_contract(self):
        self.assertIn("branch_id", self.env["account.move"]._fields)
        self.assertIn("branch_id", self.env["account.move.line"]._fields)
        self.assertIn("working_branch_id", self.env["res.users"]._fields)
        self.assertIn("default_branch_id", self.env["res.company"]._fields)

    def test_32_adjustment_workflow(self):
        states = dict(self.env["clinic.accounting.adjustment"]._fields["state"].selection)
        for state in ("draft", "submitted", "approved", "posted", "cancelled"):
            self.assertIn(state, states)

    def test_33_close_workflow(self):
        states = dict(self.env["clinic.accounting.close"]._fields["state"].selection)
        for state in ("draft", "preflight", "ready", "closed", "cancelled"):
            self.assertIn(state, states)

    def test_34_statement_workflow(self):
        states = dict(self.env["clinic.accounting.statement"]._fields["state"].selection)
        for state in ("draft", "generated", "locked"):
            self.assertIn(state, states)

    def test_35_statement_types_complete(self):
        types = dict(self.env["clinic.accounting.statement"]._fields["statement_type"].selection)
        for value in (
            "trial_balance",
            "general_ledger",
            "profit_loss",
            "balance_sheet",
            "journal_audit",
            "source_summary",
        ):
            self.assertIn(value, types)

    def test_36_statement_generation_methods_exist(self):
        model = self.env["clinic.accounting.statement"]
        for method in (
            "_generate_trial_balance",
            "_generate_general_ledger",
            "_generate_profit_loss",
            "_generate_balance_sheet",
            "_generate_journal_audit",
            "_generate_source_summary",
        ):
            self.assertTrue(hasattr(model, method))

    def test_37_close_preflight_method_exists(self):
        self.assertTrue(hasattr(self.env["clinic.accounting.close"], "_preflight_items"))

    def test_38_close_applies_native_lock_through_action(self):
        self.assertTrue(hasattr(self.env["clinic.accounting.close"], "action_close_period"))

    def test_39_company_settings_exist(self):
        company = self.env["res.company"]
        for field in (
            "clinic_accounting_default_ledger_id",
            "clinic_accounting_adjustment_journal_id",
            "clinic_accounting_adjustment_approval_threshold",
            "clinic_accounting_close_require_reconciled_receivable",
            "clinic_accounting_close_require_reconciled_payable",
            "clinic_accounting_auto_monthly_trial_balance",
        ):
            self.assertIn(field, company._fields)

    def test_40_security_groups_exist(self):
        for xmlid in (
            "clinic_accounting.group_clinic_accounting_user",
            "clinic_accounting.group_clinic_accounting_accountant",
            "clinic_accounting.group_clinic_accounting_approver",
            "clinic_accounting.group_clinic_accounting_manager",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_41_accountant_implies_account_user(self):
        accountant = self.env.ref("clinic_accounting.group_clinic_accounting_accountant")
        self.assertIn(self.env.ref("account.group_account_user"), accountant.implied_ids)

    def test_42_manager_implies_odoo_account_manager(self):
        manager = self.env.ref("clinic_accounting.group_clinic_accounting_manager")
        self.assertIn(self.env.ref("account.group_account_manager"), manager.implied_ids)

    def test_43_manager_implies_approver(self):
        manager = self.env.ref("clinic_accounting.group_clinic_accounting_manager")
        approver = self.env.ref("clinic_accounting.group_clinic_accounting_approver")
        self.assertIn(approver, manager.implied_ids)

    def test_44_approver_implies_accountant(self):
        approver = self.env.ref("clinic_accounting.group_clinic_accounting_approver")
        accountant = self.env.ref("clinic_accounting.group_clinic_accounting_accountant")
        self.assertIn(accountant, approver.implied_ids)

    def test_45_search_views_follow_clinicone_odoo19_contract(self):
        xmlids = (
            "clinic_accounting.view_accounting_ledger_search",
            "clinic_accounting.view_accounting_adjustment_search",
            "clinic_accounting.view_accounting_adjustment_line_search",
            "clinic_accounting.view_accounting_close_search",
            "clinic_accounting.view_accounting_close_check_search",
            "clinic_accounting.view_accounting_statement_search",
            "clinic_accounting.view_accounting_statement_line_search",
        )
        for xmlid in xmlids:
            view = self.env.ref(xmlid)
            arch = view.arch_db
            if hasattr(arch, "get"):
                arch = arch.get(self.env.lang) or next(iter(arch.values()), "")
            root = etree.fromstring((arch or "").encode())
            self.assertEqual(root.tag, "search")
            self.assertFalse(root.attrib)
            for group in root.xpath("./group"):
                self.assertFalse(group.attrib)

    def test_46_every_persistent_model_has_search_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "search")], limit=1),
                model,
            )

    def test_47_every_persistent_model_has_list_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "list")], limit=1),
                model,
            )

    def test_48_every_persistent_model_has_form_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "form")], limit=1),
                model,
            )

    def test_49_statement_analysis_views_exist(self):
        self.assertTrue(self.env.ref("clinic_accounting.view_accounting_statement_pivot"))
        self.assertTrue(self.env.ref("clinic_accounting.view_accounting_statement_graph"))

    def test_50_statement_report_exists(self):
        self.assertTrue(self.env.ref("clinic_accounting.action_report_accounting_statement"))

    def test_51_close_report_exists(self):
        self.assertTrue(self.env.ref("clinic_accounting.action_report_accounting_close"))

    def test_52_monthly_trial_balance_cron_exists(self):
        self.assertTrue(self.env.ref("clinic_accounting.cron_accounting_monthly_trial_balance"))

    def test_53_settings_action_is_local(self):
        action = self.env.ref("clinic_accounting.action_clinic_accounting_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertIn("clinic_accounting", action.context or "")

    def test_54_native_entry_search_action_exists(self):
        action = self.env.ref("clinic_accounting.action_clinic_accounting_journal_entries")
        self.assertEqual(action.res_model, "account.move")

    def test_55_native_item_search_action_exists(self):
        action = self.env.ref("clinic_accounting.action_clinic_accounting_journal_items")
        self.assertEqual(action.res_model, "account.move.line")

    def test_56_statement_lines_are_generated_model(self):
        statement = self.env["clinic.accounting.statement"]
        line = self.env["clinic.accounting.statement.line"]
        self.assertEqual(statement._fields["line_ids"].comodel_name, line._name)
        self.assertEqual(line._fields["statement_id"].comodel_name, statement._name)

    def test_57_close_checks_are_generated_model(self):
        close = self.env["clinic.accounting.close"]
        check = self.env["clinic.accounting.close.check"]
        self.assertEqual(close._fields["check_ids"].comodel_name, check._name)
        self.assertEqual(check._fields["close_id"].comodel_name, close._name)

    def test_58_adjustment_lines_are_owned_by_adjustment(self):
        adjustment = self.env["clinic.accounting.adjustment"]
        line = self.env["clinic.accounting.adjustment.line"]
        self.assertEqual(adjustment._fields["line_ids"].comodel_name, line._name)
        self.assertEqual(line._fields["adjustment_id"].comodel_name, adjustment._name)

    def test_59_source_summary_uses_stored_move_line_source(self):
        field = self.env["account.move.line"]._fields["clinic_accounting_source"]
        self.assertTrue(field.store)

    def test_60_accounting_does_not_replace_legal_ledger(self):
        self.assertNotIn("clinic.accounting.move", self.env.registry)
        self.assertNotIn("clinic.accounting.move.line", self.env.registry)
