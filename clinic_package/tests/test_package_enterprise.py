
# -*- coding: utf-8 -*-
"""Enterprise regression tests for the package domain.

These tests are intentionally workflow-oriented: they protect lifecycle,
snapshot integrity, redemption balance, transfer governance, vouchers, and the
stable downstream integration contract.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "clinic_package")
class TestClinicPackageEnterprise(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Package Test Patient"})
        cls.patient = cls.env["clinic.patient"].create(
            {"name": "Package Test Patient", "partner_id": cls.partner.id, "company_id": cls.company.id}
        )
        cls.target_partner = cls.env["res.partner"].create({"name": "Transfer Target"})
        cls.target_patient = cls.env["clinic.patient"].create(
            {"name": "Transfer Target", "partner_id": cls.target_partner.id, "company_id": cls.company.id}
        )
        cls.policy = cls.env["clinic.package.policy"].create(
            {
                "name": "Test Governed Policy",
                "company_id": cls.company.id,
                "allow_pause": True,
                "allow_transfer": True,
                "transfer_scope": "any",
                "transfer_max_times": 2,
                "transfer_min_remaining_pct": 0.0,
                "allow_refund": True,
            }
        )
        cls.pricing = cls.env["clinic.package.pricing"].create(
            {"name": "Test Pricing", "company_id": cls.company.id}
        )

    def _make_package(self, name="Enterprise Package", credit=1000.0):
        package = self.env["clinic.package"].create(
            {
                "name": name,
                "company_id": self.company.id,
                "list_price": 900.0,
                "cost_price": 400.0,
                "duration_value": 6,
                "duration_uom": "month",
                "policy_id": self.policy.id,
                "pricing_id": self.pricing.id,
            }
        )
        self.env["clinic.package.line"].create(
            {
                "package_id": package.id,
                "name": "Wallet Credit",
                "line_type": "credit",
                "credit_amount": credit,
            }
        )
        return package

    def _make_active_allocation(self, credit=1000.0):
        package = self._make_package(credit=credit)
        package.action_activate()
        allocation = self.env["clinic.package.allocation"].create(
            {"package_id": package.id, "patient_id": self.patient.id, "company_id": self.company.id}
        )
        allocation.action_activate()
        return package, allocation

    def test_01_package_activation_requires_components(self):
        package = self.env["clinic.package"].create(
            {"name": "Empty Package", "company_id": self.company.id, "duration_value": 1}
        )
        with self.assertRaises(UserError):
            package.action_activate()

    def test_02_package_activation_and_margin(self):
        package = self._make_package()
        package.action_activate()
        self.assertEqual(package.state, "active")
        self.assertEqual(package.margin_amount, 500.0)
        self.assertTrue(package.code and package.code != "/")

    def test_03_allocation_activation_builds_snapshot(self):
        _package, allocation = self._make_active_allocation()
        self.assertEqual(allocation.state, "active")
        self.assertEqual(len(allocation.line_ids), 1)
        self.assertEqual(allocation.line_ids.credit_amount_total, 1000.0)

    def test_04_allocation_state_cannot_be_bypassed(self):
        package = self._make_package()
        package.action_activate()
        allocation = self.env["clinic.package.allocation"].create(
            {"package_id": package.id, "patient_id": self.patient.id}
        )
        with self.assertRaises(UserError):
            allocation.write({"state": "active"})

    def test_05_snapshot_is_immutable_after_activation(self):
        _package, allocation = self._make_active_allocation()
        with self.assertRaises(UserError):
            allocation.line_ids.write({"credit_amount_total": 999999.0})

    def test_06_credit_redemption_reduces_balance(self):
        _package, allocation = self._make_active_allocation()
        line = allocation.line_ids
        usage = self.env["clinic.package.usage"].create(
            {"allocation_id": allocation.id, "allocation_line_id": line.id, "credit_used": 250.0}
        )
        usage.action_confirm()
        self.assertEqual(usage.state, "confirmed")
        self.assertEqual(line.remaining_credit, 750.0)

    def test_07_over_redemption_is_blocked(self):
        _package, allocation = self._make_active_allocation(credit=100.0)
        usage = self.env["clinic.package.usage"].create(
            {"allocation_id": allocation.id, "allocation_line_id": allocation.line_ids.id, "credit_used": 101.0}
        )
        with self.assertRaises(UserError):
            usage.action_confirm()

    def test_08_confirmed_redemption_is_immutable(self):
        _package, allocation = self._make_active_allocation()
        usage = self.env["clinic.package.usage"].create(
            {"allocation_id": allocation.id, "allocation_line_id": allocation.line_ids.id, "credit_used": 50.0}
        )
        usage.action_confirm()
        with self.assertRaises(UserError):
            usage.write({"credit_used": 60.0})

    def test_09_pause_and_resume_are_governed_actions(self):
        _package, allocation = self._make_active_allocation()
        allocation.action_pause()
        self.assertEqual(allocation.state, "paused")
        allocation.action_resume()
        self.assertEqual(allocation.state, "active")

    def test_10_transfer_updates_patient_with_audit_counter(self):
        _package, allocation = self._make_active_allocation()
        allocation._transfer_to_patient(self.target_patient, note="Approved family transfer")
        self.assertEqual(allocation.patient_id, self.target_patient)
        self.assertEqual(allocation.partner_id, self.target_partner)
        self.assertEqual(allocation.transfer_count, 1)

    def test_11_voucher_issue_and_redeem_creates_allocation(self):
        package = self._make_package(name="Voucher Package")
        package.action_activate()
        voucher = self.env["clinic.package.voucher"].create(
            {"package_id": package.id, "patient_id": self.patient.id, "company_id": self.company.id}
        )
        voucher.action_issue()
        self.assertEqual(voucher.state, "issued")
        voucher._redeem_to_patient(self.patient)
        self.assertEqual(voucher.state, "redeemed")
        self.assertEqual(voucher.redeemed_allocation_id.state, "active")

    def test_12_voucher_code_is_unique(self):
        package = self._make_package(name="Unique Voucher Package")
        voucher_a = self.env["clinic.package.voucher"].create({"package_id": package.id})
        voucher_b = self.env["clinic.package.voucher"].create({"package_id": package.id})
        self.assertNotEqual(voucher_a.code, voucher_b.code)

    def test_13_pricing_floor_is_enforced(self):
        pricing = self.env["clinic.package.pricing"].create(
            {"name": "Floor Pricing", "company_id": self.company.id, "floor_price": 800.0}
        )
        self.env["clinic.package.pricing.rule"].create(
            {"pricing_id": pricing.id, "name": "Large Discount", "rule_type": "percent", "percent_value": 90.0}
        )
        package = self._make_package(name="Floor Package")
        package.pricing_id = pricing
        result = pricing.compute_package_price(package, self.partner, 1.0)
        self.assertEqual(result["final_total"], 800.0)

    def test_14_integration_event_created_on_activation(self):
        package = self._make_package(name="Event Package")
        package.action_activate()
        event = self.env["clinic.package.integration.event"].search(
            [("source_model", "=", "clinic.package"), ("source_res_id", "=", package.id), ("event_code", "=", "package.activated")],
            limit=1,
        )
        self.assertTrue(event)
        self.assertEqual(event.state, "pending")

    def test_15_event_retry_limit_is_bounded(self):
        event = self.env["clinic.package.integration.event"].create(
            {
                "event_code": "test.failed",
                "source_model": "res.partner",
                "source_res_id": self.partner.id,
                "company_id": self.company.id,
                "state": "failed",
                "attempt_count": 1,
                "max_attempts": 1,
            }
        )
        with self.assertRaises(UserError):
            event.action_retry()


    def test_16_optional_view_bridge_missing_parent_is_non_blocking(self):
        """A missing cross-addon XML ID must never abort package loading."""
        result = self.env["clinic.package"]._upsert_optional_inherited_view(
            parent_xmlid="clinic_patient.__clinic_package_missing_parent_test__",
            local_xmlid_name="__missing_parent_test_view__",
            view_name="clinic.package.missing.parent.test",
            model_name="clinic.patient",
            arch_db="<data/>",
        )
        self.assertFalse(result)

    def test_17_optional_cross_addon_view_bridge_is_idempotent(self):
        """Current-source patient/booking/care-plan bridges can be re-applied safely."""
        package_model = self.env["clinic.package"]
        package_model._ensure_optional_cross_addon_views()

        xmlids = (
            "clinic_package.view_clinic_patient_form_package",
            "clinic_package.view_booking_booking_form_package",
            "clinic_package.view_clinic_care_plan_form_package",
            "clinic_package.view_emar_order_form_package",
            "clinic_package.view_emar_schedule_form_package",
            "clinic_package.view_emar_administration_form_package",
            "clinic_package.view_emar_prescription_form_package",
        )
        first_ids = []
        for xmlid in xmlids:
            view = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(view, "Expected runtime-safe integration view: %s" % xmlid)
            first_ids.append(view.id)

        package_model._ensure_optional_cross_addon_views()
        second_ids = [
            self.env.ref(xmlid, raise_if_not_found=False).id
            for xmlid in xmlids
        ]
        self.assertEqual(first_ids, second_ids)

    def test_18_allocation_line_depletion_is_searchable_and_recomputed(self):
        """Wizard/booking domains must be able to search is_depleted safely."""
        _package, allocation = self._make_active_allocation(credit=100.0)
        line = allocation.line_ids

        field = self.env["clinic.package.allocation.line"]._fields["is_depleted"]
        self.assertTrue(field.store)
        self.assertIn(line, self.env["clinic.package.allocation.line"].search([
            ("id", "=", line.id),
            ("is_depleted", "=", False),
        ]))

        usage = self.env["clinic.package.usage"].create(
            {
                "allocation_id": allocation.id,
                "allocation_line_id": line.id,
                "credit_used": 100.0,
            }
        )
        usage.action_confirm()
        self.assertTrue(line.is_depleted)
        self.assertIn(line, self.env["clinic.package.allocation.line"].search([
            ("id", "=", line.id),
            ("is_depleted", "=", True),
        ]))

        usage.action_cancel()
        self.assertFalse(line.is_depleted)

    def test_19_redeem_wizard_domain_contract_uses_searchable_field(self):
        """Protect the Odoo 19 view contract that triggered the runtime defect."""
        Line = self.env["clinic.package.allocation.line"]
        self.assertTrue(Line._fields["is_depleted"].store)
        self.assertTrue(Line._fields["allocation_id"].store)

    def test_20_company_package_settings_are_schema_safe(self):
        """Package configuration must never require physical res_company columns."""
        Company = self.env["res.company"]
        for field_name in (
            "clinic_pkg_default_pricing_id",
            "clinic_pkg_default_policy_id",
            "clinic_pkg_voucher_prefix",
            "clinic_pkg_voucher_code_length",
            "clinic_pkg_voucher_valid_days",
            "clinic_pkg_auto_expire_allocations",
            "clinic_pkg_auto_expire_vouchers",
        ):
            self.assertFalse(
                Company._fields[field_name].store,
                "%s must remain non-stored" % field_name,
            )

    def test_21_company_package_settings_roundtrip(self):
        """Company-scoped parameter storage must preserve the public API."""
        self.company._clinic_pkg_write_parameter_values(
            {
                "clinic_pkg_default_pricing_id": self.pricing,
                "clinic_pkg_default_policy_id": self.policy,
                "clinic_pkg_voucher_prefix": "TST",
                "clinic_pkg_voucher_code_length": 14,
                "clinic_pkg_voucher_valid_days": 45,
                "clinic_pkg_auto_expire_allocations": True,
                "clinic_pkg_auto_expire_vouchers": False,
            }
        )
        values = self.company._clinic_pkg_read_parameter_values()
        self.assertEqual(values["clinic_pkg_default_pricing_id"], self.pricing)
        self.assertEqual(values["clinic_pkg_default_policy_id"], self.policy)
        self.assertEqual(values["clinic_pkg_voucher_prefix"], "TST")
        self.assertEqual(values["clinic_pkg_voucher_code_length"], 14)
        self.assertEqual(values["clinic_pkg_voucher_valid_days"], 45)
        self.assertTrue(values["clinic_pkg_auto_expire_allocations"])
        self.assertFalse(values["clinic_pkg_auto_expire_vouchers"])

    def test_22_emar_traceability_contract_fields_exist(self):
        """Package redemptions own links; eMAR keeps clinical ownership."""
        Usage = self.env["clinic.package.usage"]
        expected = {
            "emar_order_id": "clinic.emar.order",
            "emar_schedule_id": "clinic.emar.schedule",
            "emar_administration_id": "clinic.emar.administration",
            "emar_prescription_id": "clinic.emar.prescription",
        }
        for field_name, comodel in expected.items():
            self.assertIn(field_name, Usage._fields)
            self.assertEqual(Usage._fields[field_name].comodel_name, comodel)

    def test_23_emar_reverse_navigation_contract_exists(self):
        """eMAR models expose non-invasive package navigation."""
        for model_name in (
            "clinic.emar.order",
            "clinic.emar.schedule",
            "clinic.emar.administration",
            "clinic.emar.prescription",
        ):
            Model = self.env[model_name]
            self.assertIn("package_usage_count", Model._fields)
            self.assertTrue(hasattr(Model, "action_view_package_usages"))

    def test_24_package_manager_implies_package_user(self):
        manager = self.env.ref("clinic_package.group_clinic_package_manager")
        user_group = self.env.ref("clinic_package.group_clinic_package_user")
        self.assertIn(user_group, manager.implied_ids)

