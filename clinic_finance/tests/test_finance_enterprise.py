from lxml import etree

from odoo.tests.common import TransactionCase


PERSISTENT_MODELS = (
    "clinic.finance.category",
    "clinic.finance.account",
    "clinic.finance.transaction",
    "clinic.finance.transfer",
    "clinic.finance.fund.request",
    "clinic.finance.cash.session",
    "clinic.finance.cash.count.line",
    "clinic.finance.position",
    "clinic.finance.position.line",
)


class TestClinicFinanceEnterprise(TransactionCase):

    def test_01_finance_models_exist(self):
        for model in PERSISTENT_MODELS:
            self.assertIn(model, self.env.registry)

    def test_02_upstream_finance_models_exist(self):
        for model in (
            "clinic.billing.invoice", "clinic.ar.invoice", "clinic.ar.payment",
            "clinic.ap", "clinic.cashflow", "clinic.wallet", "clinic.wallet.transaction",
        ):
            self.assertIn(model, self.env.registry)

    def test_03_standard_accounting_backbone_exists(self):
        self.assertIn("account.journal", self.env.registry)
        self.assertIn("account.move", self.env.registry)
        self.assertIn("account.move.line", self.env.registry)

    def test_04_transaction_uses_standard_journal_entry(self):
        self.assertEqual(self.env["clinic.finance.transaction"]._fields["move_id"].comodel_name, "account.move")

    def test_05_transfer_uses_standard_journal_entry(self):
        self.assertEqual(self.env["clinic.finance.transfer"]._fields["move_id"].comodel_name, "account.move")

    def test_06_finance_account_uses_standard_journal(self):
        self.assertEqual(self.env["clinic.finance.account"]._fields["journal_id"].comodel_name, "account.journal")

    def test_07_transaction_sequence_exists(self):
        self.assertTrue(self.env["ir.sequence"].search([("code", "=", "clinic.finance.transaction")], limit=1))

    def test_08_transfer_sequence_exists(self):
        self.assertTrue(self.env["ir.sequence"].search([("code", "=", "clinic.finance.transfer")], limit=1))

    def test_09_request_sequence_exists(self):
        self.assertTrue(self.env["ir.sequence"].search([("code", "=", "clinic.finance.fund.request")], limit=1))

    def test_10_cash_session_sequence_exists(self):
        self.assertTrue(self.env["ir.sequence"].search([("code", "=", "clinic.finance.cash.session")], limit=1))

    def test_11_position_sequence_exists(self):
        self.assertTrue(self.env["ir.sequence"].search([("code", "=", "clinic.finance.position")], limit=1))

    def test_12_transaction_workflow(self):
        states = dict(self.env["clinic.finance.transaction"]._fields["state"].selection)
        for state in ("draft", "submitted", "approved", "posted", "cancelled"):
            self.assertIn(state, states)

    def test_13_transfer_workflow(self):
        states = dict(self.env["clinic.finance.transfer"]._fields["state"].selection)
        for state in ("draft", "submitted", "approved", "posted", "cancelled"):
            self.assertIn(state, states)

    def test_14_fund_request_workflow(self):
        states = dict(self.env["clinic.finance.fund.request"]._fields["state"].selection)
        for state in ("draft", "submitted", "approved", "rejected", "disbursed", "cancelled"):
            self.assertIn(state, states)

    def test_15_cash_session_workflow(self):
        states = dict(self.env["clinic.finance.cash.session"]._fields["state"].selection)
        for state in ("draft", "open", "closing", "closed", "cancelled"):
            self.assertIn(state, states)

    def test_16_treasury_position_workflow(self):
        states = dict(self.env["clinic.finance.position"]._fields["state"].selection)
        for state in ("draft", "refreshed", "locked"):
            self.assertIn(state, states)

    def test_17_account_move_reverse_traceability(self):
        move = self.env["account.move"]
        self.assertIn("clinic_finance_transaction_id", move._fields)
        self.assertIn("clinic_finance_transfer_id", move._fields)

    def test_18_journal_reverse_mapping(self):
        journal = self.env["account.journal"]
        self.assertIn("clinic_finance_account_ids", journal._fields)
        self.assertIn("clinic_finance_account_count", journal._fields)

    def test_19_origin_reference_is_reference(self):
        self.assertEqual(self.env["clinic.finance.transaction"]._fields["origin_ref"].type, "reference")

    def test_20_position_integrates_ar_ap_wallet(self):
        Position = self.env["clinic.finance.position"]
        for method in ("_prepare_ar_line", "_prepare_ap_line", "_prepare_wallet_line"):
            self.assertTrue(hasattr(Position, method))

    def test_21_position_links_ap_cashflow(self):
        self.assertEqual(
            self.env["clinic.finance.position"]._fields["cashflow_id"].comodel_name,
            "clinic.cashflow",
        )

    def test_22_cash_count_fields_exist(self):
        model = self.env["clinic.finance.cash.count.line"]
        for field in ("denomination", "quantity", "subtotal", "session_id"):
            self.assertIn(field, model._fields)

    def test_23_company_settings_exist(self):
        company = self.env["res.company"]
        for field in (
            "finance_general_journal_id", "finance_default_account_id",
            "finance_approval_threshold", "finance_cash_variance_tolerance",
            "finance_variance_gain_account_id", "finance_variance_loss_account_id",
            "finance_auto_daily_position", "finance_position_include_ar",
            "finance_position_include_ap", "finance_position_include_wallet",
        ):
            self.assertIn(field, company._fields)

    def test_24_security_groups_exist(self):
        for xmlid in (
            "clinic_finance.group_clinic_finance_user",
            "clinic_finance.group_clinic_finance_cashier",
            "clinic_finance.group_clinic_finance_approver",
            "clinic_finance.group_clinic_finance_manager",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_25_manager_implies_approver(self):
        manager = self.env.ref("clinic_finance.group_clinic_finance_manager")
        approver = self.env.ref("clinic_finance.group_clinic_finance_approver")
        self.assertIn(approver, manager.implied_ids)

    def test_26_approver_implies_cashier(self):
        approver = self.env.ref("clinic_finance.group_clinic_finance_approver")
        cashier = self.env.ref("clinic_finance.group_clinic_finance_cashier")
        self.assertIn(cashier, approver.implied_ids)

    def test_27_cashier_implies_account_user(self):
        cashier = self.env.ref("clinic_finance.group_clinic_finance_cashier")
        self.assertIn(self.env.ref("account.group_account_user"), cashier.implied_ids)

    def test_28_search_views_follow_odoo19_contract(self):
        xmlids = (
            "clinic_finance.view_finance_category_search",
            "clinic_finance.view_finance_account_search",
            "clinic_finance.view_finance_transaction_search",
            "clinic_finance.view_finance_transfer_search",
            "clinic_finance.view_fund_request_search",
            "clinic_finance.view_cash_session_search",
            "clinic_finance.view_cash_count_line_search",
            "clinic_finance.view_finance_position_search",
            "clinic_finance.view_finance_position_line_search",
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

    def test_29_every_persistent_model_has_search_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "search")], limit=1), model)

    def test_30_every_persistent_model_has_list_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "list")], limit=1), model)

    def test_31_every_persistent_model_has_form_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "form")], limit=1), model)

    def test_32_transaction_analysis_views_exist(self):
        self.assertTrue(self.env.ref("clinic_finance.view_finance_transaction_pivot"))
        self.assertTrue(self.env.ref("clinic_finance.view_finance_transaction_graph"))

    def test_33_treasury_analysis_views_exist(self):
        self.assertTrue(self.env.ref("clinic_finance.view_finance_position_pivot"))
        self.assertTrue(self.env.ref("clinic_finance.view_finance_position_graph"))

    def test_34_treasury_report_exists(self):
        self.assertTrue(self.env.ref("clinic_finance.action_report_treasury_position"))

    def test_35_daily_treasury_cron_exists(self):
        self.assertTrue(self.env.ref("clinic_finance.cron_finance_daily_position"))

    def test_36_settings_action_is_local(self):
        action = self.env.ref("clinic_finance.action_clinic_finance_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertIn("clinic_finance", action.context or "")

    def test_37_account_company_contract_is_odoo19(self):
        account = self.env["account.account"]
        self.assertIn("company_ids", account._fields)

    def test_38_treasury_lines_are_generated_breakdown(self):
        position = self.env["clinic.finance.position"]
        line = self.env["clinic.finance.position.line"]
        self.assertEqual(position._fields["line_ids"].comodel_name, "clinic.finance.position.line")
        self.assertEqual(line._fields["position_id"].comodel_name, "clinic.finance.position")

    def test_39_fund_request_links_disbursement(self):
        self.assertEqual(
            self.env["clinic.finance.fund.request"]._fields["transaction_id"].comodel_name,
            "clinic.finance.transaction",
        )

    def test_40_cash_session_links_variance_transaction(self):
        self.assertEqual(
            self.env["clinic.finance.cash.session"]._fields["variance_transaction_id"].comodel_name,
            "clinic.finance.transaction",
        )

    def test_41_ar_contract_for_treasury_position(self):
        model = self.env["clinic.ar.invoice"]
        for field in ("company_id", "currency_id", "invoice_date", "state", "amount_residual"):
            self.assertIn(field, model._fields)
        self.assertIn("posted", dict(model._fields["state"].selection))

    def test_42_ap_contract_for_treasury_position(self):
        model = self.env["clinic.ap"]
        for field in ("company_id", "currency_id", "invoice_date", "state", "amount_residual"):
            self.assertIn(field, model._fields)
        states = dict(model._fields["state"].selection)
        self.assertIn("posted", states)
        self.assertIn("partial", states)

    def test_43_wallet_contract_for_treasury_position(self):
        model = self.env["clinic.wallet"]
        for field in ("company_id", "currency_id", "state", "balance"):
            self.assertIn(field, model._fields)
        states = dict(model._fields["state"].selection)
        self.assertIn("open", states)
        self.assertIn("suspended", states)

    def test_44_ap_cashflow_contract(self):
        model = self.env["clinic.cashflow"]
        for field in (
            "company_id", "currency_id", "state", "as_of_date",
            "is_pinned", "ending_balance",
        ):
            self.assertIn(field, model._fields)
        self.assertIn("generated", dict(model._fields["state"].selection))

    def test_45_branch_contract(self):
        self.assertIn("working_branch_id", self.env["res.users"]._fields)
        self.assertIn("default_branch_id", self.env["res.company"]._fields)
        self.assertIn("branch_id", self.env["account.move"]._fields)
        self.assertIn("branch_id", self.env["account.move.line"]._fields)

    def test_46_finance_position_lines_are_not_manually_owned_upstream(self):
        position = self.env["clinic.finance.position"]
        self.assertTrue(hasattr(position, "action_refresh"))
        self.assertTrue(hasattr(position, "_prepare_liquidity_lines"))

