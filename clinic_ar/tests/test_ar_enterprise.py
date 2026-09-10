# -*- coding: utf-8 -*-
from pathlib import Path

from odoo.tests.common import TransactionCase


class TestClinicAREnterprise(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Invoice = cls.env["clinic.ar.invoice"]
        cls.Line = cls.env["clinic.ar.invoice.line"]
        cls.Payment = cls.env["clinic.ar.payment"]
        cls.Allocation = cls.env["clinic.ar.allocation"]
        cls.AllocationLine = cls.env["clinic.ar.allocation.line"]
        cls.FollowupLevel = cls.env["clinic.ar.followup.level"]
        cls.Followup = cls.env["clinic.ar.followup"]
        cls.Statement = cls.env["clinic.ar.statement"]
        cls.StatementLine = cls.env["clinic.ar.statement.line"]
        cls.Event = cls.env["clinic.ar.integration.event"]

    def test_01_owner_models_exist(self):
        for model in (self.Invoice, self.Line, self.Payment, self.Allocation, self.AllocationLine, self.FollowupLevel, self.Followup, self.Statement, self.StatementLine, self.Event):
            self.assertTrue(model._name)

    def test_02_billing_uses_actual_owner_model(self):
        self.assertEqual(self.Invoice._fields["billing_id"].comodel_name, "clinic.billing.invoice")

    def test_03_booking_uses_actual_owner_model(self):
        self.assertEqual(self.Invoice._fields["booking_id"].comodel_name, "booking.booking")

    def test_04_membership_uses_actual_owner_model(self):
        self.assertEqual(self.Invoice._fields["membership_id"].comodel_name, "membership.contract")

    def test_05_treatment_session_uses_actual_owner_model(self):
        self.assertEqual(self.Invoice._fields["treatment_session_id"].comodel_name, "clinic.treatment.session")

    def test_06_invoice_accounting_binding_exists(self):
        self.assertEqual(self.Invoice._fields["move_id"].comodel_name, "account.move")

    def test_07_receipt_uses_account_payment(self):
        self.assertEqual(self.Payment._fields["account_payment_id"].comodel_name, "account.payment")

    def test_08_invoice_line_account_is_company_checked(self):
        self.assertTrue(self.Line._fields["income_account_id"].check_company)

    def test_09_account_account_uses_company_ids(self):
        Account = self.env["account.account"]
        self.assertNotIn("company_id", Account._fields)
        self.assertIn("company_ids", Account._fields)

    def test_10_security_privilege_contract(self):
        user = self.env.ref("clinic_ar.group_clinic_ar_user")
        manager = self.env.ref("clinic_ar.group_clinic_ar_manager")
        self.assertTrue(user.privilege_id)
        self.assertEqual(user.privilege_id, manager.privilege_id)
        self.assertIn(user, manager.implied_ids)

    def test_11_user_group_implies_internal_user(self):
        self.assertIn(self.env.ref("base.group_user"), self.env.ref("clinic_ar.group_clinic_ar_user").implied_ids)

    def test_12_invoice_state_contract(self):
        self.assertEqual(dict(self.Invoice._fields["state"].selection).keys() >= {"draft", "posted", "cancelled"}, True)

    def test_13_receipt_state_contract(self):
        self.assertEqual(dict(self.Payment._fields["state"].selection).keys() >= {"draft", "posted", "cancelled"}, True)

    def test_14_allocation_state_contract(self):
        self.assertEqual(dict(self.Allocation._fields["state"].selection).keys() >= {"draft", "validated", "done", "cancelled"}, True)

    def test_15_statement_state_contract(self):
        self.assertEqual(dict(self.Statement._fields["state"].selection).keys() >= {"draft", "generated", "sent", "cancelled"}, True)

    def test_16_followup_state_contract(self):
        self.assertIn("scheduled", dict(self.Followup._fields["state"].selection))
        self.assertIn("failed", dict(self.Followup._fields["state"].selection))

    def test_17_invoice_has_aging_fields(self):
        for name in ("is_overdue", "days_overdue", "aging_bucket", "amount_residual"):
            self.assertIn(name, self.Invoice._fields)

    def test_18_partner_credit_control_fields_exist(self):
        Partner = self.env["res.partner"]
        for name in ("ar_credit_limit", "ar_allow_overlimit", "ar_on_hold", "ar_overdue_guard_days"):
            self.assertIn(name, Partner._fields)

    def test_19_partner_aging_metrics_exist(self):
        Partner = self.env["res.partner"]
        for name in ("ar_outstanding", "ar_overdue", "ar_aging_current", "ar_aging_90_plus"):
            self.assertIn(name, Partner._fields)

    def test_20_billing_reverse_bridge_exists(self):
        Billing = self.env["clinic.billing.invoice"]
        self.assertIn("ar_invoice_ids", Billing._fields)
        self.assertTrue(hasattr(Billing, "action_create_or_open_ar"))

    def test_21_account_move_reverse_bridge_exists(self):
        Move = self.env["account.move"]
        self.assertIn("ar_invoice_ids", Move._fields)
        self.assertIn("ar_payment_ids", Move._fields)

    def test_22_statement_line_is_managed_ledger(self):
        self.assertTrue(hasattr(self.StatementLine, "_check_managed_mutation"))

    def test_23_allocation_line_has_row_action(self):
        self.assertTrue(hasattr(self.AllocationLine, "action_open_invoice"))

    def test_24_invoice_line_has_billing_row_action(self):
        self.assertTrue(hasattr(self.Line, "action_open_billing_line"))

    def test_25_event_retry_is_bounded(self):
        self.assertEqual(self.Event.MAX_ATTEMPTS, 3)

    def test_26_settings_are_company_key_scoped(self):
        Settings = self.env["res.config.settings"].with_context(allowed_company_ids=[self.env.company.id]).create({})
        self.assertIn(f"clinic_ar.company.{self.env.company.id}.", Settings._clinic_ar_key("probe"))

    def test_27_no_hard_dependency_on_wallet_model(self):
        self.assertNotIn("wallet_id", self.Invoice._fields)

    def test_28_invoice_has_strict_event_outbox(self):
        self.assertTrue(hasattr(self.Invoice, "_emit_event"))
        self.assertTrue(hasattr(self.Event, "enqueue"))

    def test_29_payment_has_open_credit_allocation_action(self):
        self.assertTrue(hasattr(self.Payment, "action_create_allocation"))

    def test_30_followup_has_manual_and_email_channels(self):
        values = dict(self.FollowupLevel._fields["reminder_type"].selection)
        self.assertIn("email", values)
        self.assertIn("call", values)

    def test_31_statement_has_generation_action(self):
        self.assertTrue(hasattr(self.Statement, "action_generate"))
        self.assertTrue(hasattr(self.Statement, "action_send"))

    def test_32_ar_invoice_can_be_created_from_billing(self):
        self.assertTrue(hasattr(self.Invoice, "create_from_billing"))
    def test_33_small_residual_writeoff_contract_preserved(self):
        Company = self.env["res.company"]
        for name in ("ar_writeoff_account_id", "ar_writeoff_threshold", "ar_default_general_journal_id"):
            self.assertIn(name, Company._fields)
        self.assertTrue(hasattr(self.env["account.move"], "action_ar_writeoff_small_residual"))

    def test_34_account_move_receivable_helpers_preserved(self):
        Move = self.env["account.move"]
        for name in ("ar_is_ar_invoice_move", "ar_is_ar_payment_move", "ar_receivable_line_ids"):
            self.assertIn(name, Move._fields)
        self.assertTrue(hasattr(Move, "ar_get_open_receivable_lines"))

    def test_35_res_currency_fields_do_not_use_check_company(self):
        Currency = self.env["res.currency"]
        self.assertNotIn("company_id", Currency._fields)

        for model in (self.Invoice, self.Payment, self.Allocation):
            field = model._fields["currency_id"]
            self.assertEqual(field.comodel_name, "res.currency")
            self.assertFalse(field.check_company)

    def test_36_billing_view_bridge_is_runtime_safe_and_idempotent(self):
        """Billing form decoration must not depend on a hard XPath at module load."""
        self.Invoice._ensure_optional_billing_views()

        xmlids = (
            "clinic_ar.view_billing_invoice_form_clinic_ar",
            "clinic_ar.view_billing_payment_form_clinic_ar",
        )
        first_ids = []
        for xmlid in xmlids:
            view = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(view, "Expected runtime-safe Billing integration view: %s" % xmlid)
            first_ids.append(view.id)

        self.Invoice._ensure_optional_billing_views()
        second_ids = [
            self.env.ref(xmlid, raise_if_not_found=False).id
            for xmlid in xmlids
        ]
        self.assertEqual(first_ids, second_ids)

    def test_37_missing_billing_parent_view_is_non_blocking(self):
        """A missing upstream view XML ID must never abort the AR business module."""
        result = self.Invoice._upsert_optional_inherited_view(
            parent_xmlid="clinic_billing.__clinic_ar_missing_parent_test__",
            local_xmlid_name="__clinic_ar_missing_parent_test_view__",
            view_name="clinic.ar.missing.parent.test",
            model_name="clinic.billing.payment",
            arch_candidates=("<data/>",),
        )
        self.assertFalse(result)



