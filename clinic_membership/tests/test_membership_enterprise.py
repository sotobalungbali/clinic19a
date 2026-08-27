

# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from lxml import etree


@tagged('post_install', '-at_install')
class TestClinicMembershipEnterprise(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Plan = self.env['membership.plan']
        self.Contract = self.env['membership.contract']
        self.Benefit = self.env['membership.plan.benefit']
        self.partner = self.env['res.partner'].create({'name':'Membership Test Member'})
        self.plan = self.Plan.create({'name':'Gold Test','code':'GOLD-T','list_price':0.0,'duration_value':12,'duration_unit':'month'})
        self.benefit = self.Benefit.create({'plan_id':self.plan.id,'name':'10% Discount','benefit_type':'discount_percent','discount_percent':10.0})
        self.plan.action_activate()

    def test_01_plan_uses_odoo19_constraint_contract(self):
        self.assertIn('_code_company_uniq', self.Plan.__dict__)
    def test_02_contract_activation_builds_snapshot(self):
        c=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id})
        c.action_activate(); self.assertEqual(c.state,'active'); self.assertEqual(len(c.benefit_snapshot_ids),1)
    def test_03_snapshot_is_not_manually_creatable(self):
        c=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id}); c.action_activate()
        with self.assertRaises(UserError): self.env['membership.contract.benefit'].create({'contract_id':c.id,'source_benefit_id':self.benefit.id,'plan_id':self.plan.id,'company_id':self.env.company.id,'currency_id':self.env.company.currency_id.id,'name':'Bad','benefit_type':'quota'})
    def test_04_direct_contract_state_write_blocked(self):
        c=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id})
        with self.assertRaises(UserError): c.write({'state':'active'})
    def test_05_usage_discount(self):
        c=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id}); c.action_activate()
        u=self.env['membership.usage'].create({'contract_id':c.id,'unit_price':100.0,'qty':1.0})
        u.action_apply_best_benefit(); self.assertAlmostEqual(u.discount_amount,10.0)
    def test_06_usage_validation(self):
        c=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id}); c.action_activate()
        u=self.env['membership.usage'].create({'contract_id':c.id,'unit_price':100.0,'qty':1.0}); u.action_validate(); self.assertEqual(u.state,'validated')
    def test_07_contract_expiry_searchable(self): self.assertTrue(bool(self.Contract._fields['is_expired'].search))
    def test_08_voucher_expiry_searchable(self): self.assertTrue(bool(self.env['membership.voucher']._fields['is_expired'].search))
    def test_09_entitlement_depleted_stored(self): self.assertTrue(self.env['membership.contract.benefit']._fields['is_depleted'].store)
    def test_10_partner_api_owned_by_membership(self): self.assertIn('membership_reference', self.env['res.partner']._fields)
    def test_11_no_billing_hard_dependency_runtime(self): self.assertNotIn('clinic.billing.invoice', self.env['membership.contract']._fields)
    def test_12_event_contract_exists(self): self.assertIn('membership.integration.event', self.env)
    def test_13_config_is_schema_safe(self): self.assertFalse(self.env['res.config.settings']._fields['membership_require_paid_before_activation'].store)
    def test_14_hold_model_loaded(self): self.assertIn('membership.hold', self.env)
    def test_15_points_model_loaded(self): self.assertIn('membership.point.tx', self.env)
    def test_16_voucher_model_loaded(self): self.assertIn('membership.voucher', self.env)
    def test_17_booking_bridge_loaded(self): self.assertIn('membership_contract_id', self.env['booking.booking']._fields)
    def test_18_package_bridge_loaded(self): self.assertIn('membership_usage_count', self.env['clinic.package.usage']._fields)
    def test_19_emar_bridge_loaded(self): self.assertIn('membership_usage_count', self.env['clinic.emar.administration']._fields)
    def test_20_care_plan_bridge_loaded(self): self.assertIn('membership_usage_count', self.env['clinic.care.plan']._fields)
    def test_21_plan_active_commercial_lock(self):
        with self.assertRaises(UserError): self.plan.write({'list_price':99.0})
    def test_22_contract_single_active_same_plan(self):
        c1=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id}); c1.action_activate()
        c2=self.Contract.create({'plan_id':self.plan.id,'partner_id':self.partner.id})
        with self.assertRaises(Exception): c2.action_activate()
    def test_23_integration_event_retry_is_bounded(self): self.assertGreaterEqual(self.env['membership.integration.event'].MAX_ATTEMPTS,1)
    def test_24_wizard_models_loaded(self):
        for m in ('membership.contract.renew.wizard','membership.hold.request.wizard','membership.point.adjust.wizard'): self.assertIn(m,self.env)

    def test_25_odoo19_security_privilege_hierarchy(self):
        privilege = self.env.ref('clinic_membership.privilege_clinic_membership')
        user_group = self.env.ref('clinic_membership.group_clinic_membership_user')
        manager_group = self.env.ref('clinic_membership.group_clinic_membership_manager')
        self.assertEqual(user_group.privilege_id, privilege)
        self.assertEqual(manager_group.privilege_id, privilege)
        self.assertNotIn('category_id', self.env['res.groups']._fields)

    def test_26_search_views_follow_odoo19_filter_contract(self):
        """Every search filter has a technical name and search groups use Odoo 19 attrs."""
        search_view_ids = [
            "clinic_membership.view_membership_plan_search",
            "clinic_membership.view_membership_benefit_search",
            "clinic_membership.view_membership_contract_search",
            "clinic_membership.view_membership_contract_benefit_search",
            "clinic_membership.view_membership_usage_search",
            "clinic_membership.view_membership_voucher_search",
            "clinic_membership.view_membership_point_tx_search",
            "clinic_membership.view_membership_hold_search",
            "clinic_membership.view_membership_integration_event_search",
        ]
        for xmlid in search_view_ids:
            view = self.env.ref(xmlid)
            arch = etree.fromstring(view.arch_db.encode("utf-8"))
            for filter_node in arch.xpath(".//filter"):
                self.assertTrue(
                    filter_node.get("name"),
                    f"{xmlid}: every Odoo 19 search filter must have name",
                )
            for group_node in arch.xpath(".//group"):
                self.assertNotIn("expand", group_node.attrib, f"{xmlid}: legacy search group expand")
                self.assertNotIn("string", group_node.attrib, f"{xmlid}: legacy search group string")

    def test_27_odoo19_income_account_company_contract(self):
        """Revenue account selection follows Odoo 19 account.account company_ids."""
        Account = self.env["account.account"]
        self.assertNotIn("company_id", Account._fields)
        self.assertIn("company_ids", Account._fields)
        self.assertTrue(self.Plan._fields["income_account_id"].check_company)

        field_domain = self.Plan._fields["income_account_id"].domain
        self.assertNotIn("company_id", str(field_domain))

        company_domain = Account._check_company_domain(self.env.company)
        self.assertTrue(company_domain)
        income_account = Account.with_company(self.env.company).search(
            [*company_domain, ("account_type", "=", "income")],
            limit=1,
        )
        if income_account:
            self.assertIn(self.env.company, income_account.company_ids)
    def test_28_inline_entitlement_button_uses_child_model_method(self):
        """Inline One2many object buttons must execute on the row comodel."""
        view = self.env.ref("clinic_membership.view_membership_contract_form")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))

        buttons = arch.xpath(
            ".//field[@name='benefit_snapshot_ids']//button[@type='object']"
        )
        self.assertTrue(buttons, "Entitlements inline list must keep its row action")
        self.assertEqual(
            buttons[0].get("name"),
            "action_view_usages",
        )
        self.assertTrue(
            hasattr(self.env["membership.contract.benefit"], "action_view_usages")
        )
        self.assertFalse(
            hasattr(self.env["membership.contract.benefit"], "action_open_usages")
        )


    def test_29_membership_settings_uses_owned_odoo19_action(self):
        """Membership Settings menu must resolve to an addon-owned Odoo 19 action."""
        action = self.env.ref("clinic_membership.action_membership_settings")
        self.assertEqual(action._name, "ir.actions.act_window")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertEqual(action.view_mode, "form")
        self.assertIn("clinic_membership", action.context or "")

        menu = self.env.ref("clinic_membership.menu_membership_settings")
        self.assertEqual(menu.action, action)
