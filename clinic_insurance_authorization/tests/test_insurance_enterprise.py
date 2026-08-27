from lxml import etree

from odoo.tests.common import TransactionCase


OWNED_MODELS = (
    "clinic.insurance.plan",
    "clinic.insurance.plan.rule",
    "clinic.insurance.policy",
    "clinic.insurance.eligibility.check",
    "clinic.insurance.authorization",
    "clinic.insurance.authorization.line",
)


class TestClinicInsuranceEnterprise(TransactionCase):

    def test_01_owned_models_exist(self):
        for model in OWNED_MODELS:
            self.assertIn(model, self.env.registry)

    def test_02_company_mixin_exists(self):
        self.assertIn("clinic.insurance.company.mixin", self.env.registry)

    def test_03_billing_owned_claim_exists(self):
        self.assertIn("clinic.insurance.claim", self.env.registry)

    def test_04_billing_owned_claim_line_exists(self):
        self.assertIn("clinic.insurance.claim.line", self.env.registry)

    def test_05_claim_owner_module_remains_billing(self):
        model = self.env["ir.model"]._get("clinic.insurance.claim")
        xmlid = model.get_external_id().get(model.id, "")
        self.assertTrue(xmlid.startswith("clinic_billing."), xmlid)

    def test_06_claim_line_owner_module_remains_billing(self):
        model = self.env["ir.model"]._get("clinic.insurance.claim.line")
        xmlid = model.get_external_id().get(model.id, "")
        self.assertTrue(xmlid.startswith("clinic_billing."), xmlid)

    def test_07_plan_links_insurer_partner(self):
        self.assertEqual(
            self.env["clinic.insurance.plan"]._fields["insurer_partner_id"].comodel_name,
            "res.partner",
        )

    def test_08_plan_uses_native_settlement_journal(self):
        self.assertEqual(
            self.env["clinic.insurance.plan"]._fields["settlement_journal_id"].comodel_name,
            "account.journal",
        )

    def test_09_plan_has_benefit_rules(self):
        self.assertEqual(
            self.env["clinic.insurance.plan"]._fields["rule_ids"].comodel_name,
            "clinic.insurance.plan.rule",
        )

    def test_10_benefit_rule_treatment_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.plan.rule"]._fields["treatment_catalog_id"].comodel_name,
            "clinic.treatment.catalog",
        )

    def test_11_benefit_rule_procedure_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.plan.rule"]._fields["procedure_catalog_id"].comodel_name,
            "clinic.procedure.catalog",
        )

    def test_12_benefit_rule_product_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.plan.rule"]._fields["product_id"].comodel_name,
            "product.product",
        )

    def test_13_policy_links_clinic_patient(self):
        self.assertEqual(
            self.env["clinic.insurance.policy"]._fields["patient_id"].comodel_name,
            "clinic.patient",
        )

    def test_14_policy_partner_snapshot_exists(self):
        field = self.env["clinic.insurance.policy"]._fields["partner_id"]
        self.assertEqual(field.comodel_name, "res.partner")
        self.assertTrue(field.store)

    def test_15_policy_plan_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.policy"]._fields["plan_id"].comodel_name,
            "clinic.insurance.plan",
        )

    def test_16_policy_workflow_complete(self):
        selection = dict(self.env["clinic.insurance.policy"]._fields["state"].selection)
        for value in ("draft", "verified", "active", "suspended", "expired", "cancelled"):
            self.assertIn(value, selection)

    def test_17_policy_current_valid_is_searchable(self):
        field = self.env["clinic.insurance.policy"]._fields["currently_valid"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_18_policy_eligibility_state_is_searchable(self):
        field = self.env["clinic.insurance.policy"]._fields["eligibility_state"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_19_eligibility_policy_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.eligibility.check"]._fields["policy_id"].comodel_name,
            "clinic.insurance.policy",
        )

    def test_20_eligibility_workflow_complete(self):
        selection = dict(self.env["clinic.insurance.eligibility.check"]._fields["state"].selection)
        for value in ("draft", "pending", "eligible", "ineligible", "error", "expired", "cancelled"):
            self.assertIn(value, selection)

    def test_21_eligibility_has_payer_evidence_fields(self):
        model = self.env["clinic.insurance.eligibility.check"]
        for field in (
            "verification_method",
            "external_reference",
            "response_code",
            "response_message",
            "valid_until",
            "attachment_ids",
        ):
            self.assertIn(field, model._fields)

    def test_22_authorization_policy_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["policy_id"].comodel_name,
            "clinic.insurance.policy",
        )

    def test_23_authorization_patient_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["patient_id"].comodel_name,
            "clinic.patient",
        )

    def test_24_authorization_booking_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["booking_id"].comodel_name,
            "booking.booking",
        )

    def test_25_authorization_appointment_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["appointment_id"].comodel_name,
            "clinic.appointment",
        )

    def test_26_authorization_encounter_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["encounter_id"].comodel_name,
            "clinic.encounter",
        )

    def test_27_authorization_treatment_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["treatment_id"].comodel_name,
            "clinic.treatment",
        )

    def test_28_authorization_billing_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization"]._fields["billing_invoice_id"].comodel_name,
            "clinic.billing.invoice",
        )

    def test_29_authorization_workflow_complete(self):
        selection = dict(self.env["clinic.insurance.authorization"]._fields["state"].selection)
        for value in (
            "draft",
            "prepared",
            "submitted",
            "pending",
            "approved",
            "partial",
            "rejected",
            "expired",
            "cancelled",
        ):
            self.assertIn(value, selection)

    def test_30_authorization_search_fields_are_stored(self):
        model = self.env["clinic.insurance.authorization"]
        for field in ("authorization_required", "eligibility_ok", "currently_valid"):
            self.assertTrue(model._fields[field].store, field)
            self.assertTrue(model._fields[field].index, field)

    def test_31_authorization_has_claim_create_action(self):
        self.assertTrue(hasattr(self.env["clinic.insurance.authorization"], "action_create_claim"))

    def test_32_authorization_line_parent_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization.line"]._fields["authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_33_authorization_line_state_stored(self):
        field = self.env["clinic.insurance.authorization.line"]._fields["state"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_34_authorization_line_rule_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.authorization.line"]._fields["benefit_rule_id"].comodel_name,
            "clinic.insurance.plan.rule",
        )

    def test_35_authorization_line_amounts_are_stored(self):
        model = self.env["clinic.insurance.authorization.line"]
        for field in (
            "requested_amount",
            "insurer_payable_amount",
            "patient_responsibility_amount",
        ):
            self.assertTrue(model._fields[field].store, field)

    def test_36_claim_has_structured_policy_link(self):
        self.assertEqual(
            self.env["clinic.insurance.claim"]._fields["policy_id"].comodel_name,
            "clinic.insurance.policy",
        )

    def test_37_claim_has_structured_authorization_link(self):
        self.assertEqual(
            self.env["clinic.insurance.claim"]._fields["authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_38_claim_has_eligibility_link(self):
        self.assertEqual(
            self.env["clinic.insurance.claim"]._fields["eligibility_check_id"].comodel_name,
            "clinic.insurance.eligibility.check",
        )

    def test_39_claim_payer_status_complete(self):
        selection = dict(self.env["clinic.insurance.claim"]._fields["payer_status"].selection)
        for value in (
            "not_sent",
            "received",
            "under_review",
            "approved",
            "partially_approved",
            "denied",
            "settled",
        ):
            self.assertIn(value, selection)

    def test_40_claim_policy_valid_is_searchable(self):
        field = self.env["clinic.insurance.claim"]._fields["policy_valid"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_41_claim_authorization_valid_is_searchable(self):
        field = self.env["clinic.insurance.claim"]._fields["authorization_valid"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_42_claim_line_authorization_contract(self):
        self.assertEqual(
            self.env["clinic.insurance.claim.line"]._fields["authorization_line_id"].comodel_name,
            "clinic.insurance.authorization.line",
        )

    def test_43_claim_line_variance_is_searchable(self):
        field = self.env["clinic.insurance.claim.line"]._fields["authorization_variance"]
        self.assertTrue(field.store)

    def test_44_billing_claim_sequence_is_preserved(self):
        self.assertTrue(self.env["ir.sequence"].search([("code", "=", "clinic.insurance.claim")], limit=1))

    def test_45_billing_claim_payment_owner_is_preserved(self):
        self.assertEqual(
            self.env["clinic.insurance.claim"]._fields["settlement_payment_id"].comodel_name,
            "clinic.billing.payment",
        )

    def test_46_partner_has_insurer_marker(self):
        partner = self.env["res.partner"]
        for field in ("is_insurer", "insurer_code", "payer_external_id"):
            self.assertIn(field, partner._fields)

    def test_47_patient_has_policy_relationship(self):
        self.assertEqual(
            self.env["clinic.patient"]._fields["insurance_policy_ids"].comodel_name,
            "clinic.insurance.policy",
        )

    def test_48_patient_has_authorization_relationship(self):
        self.assertEqual(
            self.env["clinic.patient"]._fields["insurance_authorization_ids"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_49_patient_expected_open_insurance_method_exists(self):
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_open_insurance"))

    def test_50_patient_expected_action_xmlid_exists(self):
        self.assertTrue(
            self.env.ref("clinic_insurance_authorization.action_clinic_insurance_authorization")
        )
        self.assertTrue(
            self.env.ref("clinic_insurance_authorization.action_clinic_insurance_authorization_from_patient")
        )

    def test_51_booking_structured_insurance_fields_exist(self):
        booking = self.env["booking.booking"]
        self.assertEqual(booking._fields["insurance_policy_id"].comodel_name, "clinic.insurance.policy")
        self.assertEqual(
            booking._fields["insurance_authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_52_booking_create_authorization_action_exists(self):
        self.assertTrue(hasattr(self.env["booking.booking"], "action_create_insurance_authorization"))

    def test_53_appointment_insurance_policy_field_resolved(self):
        self.assertEqual(
            self.env["clinic.appointment"]._fields["insurance_policy_id"].comodel_name,
            "clinic.insurance.policy",
        )

    def test_54_appointment_authorization_field_resolved(self):
        self.assertEqual(
            self.env["clinic.appointment"]._fields["authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_55_treatment_insurance_policy_field_resolved(self):
        self.assertEqual(
            self.env["clinic.treatment"]._fields["insurance_policy_id"].comodel_name,
            "clinic.insurance.policy",
        )

    def test_56_treatment_authorization_field_resolved(self):
        self.assertEqual(
            self.env["clinic.treatment"]._fields["authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_57_encounter_structured_insurance_fields_exist(self):
        encounter = self.env["clinic.encounter"]
        self.assertEqual(encounter._fields["insurance_policy_id"].comodel_name, "clinic.insurance.policy")
        self.assertEqual(
            encounter._fields["insurance_authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_58_billing_structured_insurance_fields_exist(self):
        invoice = self.env["clinic.billing.invoice"]
        self.assertEqual(invoice._fields["insurance_policy_id"].comodel_name, "clinic.insurance.policy")
        self.assertEqual(
            invoice._fields["insurance_authorization_id"].comodel_name,
            "clinic.insurance.authorization",
        )

    def test_59_billing_historical_insurance_fields_preserved(self):
        invoice = self.env["clinic.billing.invoice"]
        for field in (
            "insurer_partner_id",
            "insurance_policy_number",
            "insurance_coverage_percent",
            "insurance_copay_percent",
            "insurance_claim_state",
            "insurance_claim_ids",
        ):
            self.assertIn(field, invoice._fields)

    def test_60_company_insurance_settings_exist(self):
        company = self.env["res.company"]
        for field in (
            "clinic_insurance_default_plan_id",
            "clinic_insurance_require_eligibility_before_authorization",
            "clinic_insurance_default_authorization_valid_days",
            "clinic_insurance_claim_require_authorization",
            "clinic_insurance_auto_link_policy_to_billing",
        ):
            self.assertIn(field, company._fields)

    def test_61_security_groups_exist(self):
        for xmlid in (
            "clinic_insurance_authorization.group_clinic_insurance_user",
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            "clinic_insurance_authorization.group_clinic_insurance_adjudicator",
            "clinic_insurance_authorization.group_clinic_insurance_manager",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_62_insurance_user_implies_billing_user(self):
        group = self.env.ref("clinic_insurance_authorization.group_clinic_insurance_user")
        self.assertIn(self.env.ref("clinic_billing.group_clinic_billing_user"), group.implied_ids)

    def test_63_insurance_manager_implies_billing_manager(self):
        group = self.env.ref("clinic_insurance_authorization.group_clinic_insurance_manager")
        self.assertIn(self.env.ref("clinic_billing.group_clinic_billing_manager"), group.implied_ids)

    def test_64_owned_models_have_search_views(self):
        for model in OWNED_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "search")], limit=1),
                model,
            )

    def test_65_owned_models_have_list_views(self):
        for model in OWNED_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "list")], limit=1),
                model,
            )

    def test_66_owned_models_have_form_views(self):
        for model in OWNED_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "form")], limit=1),
                model,
            )

    def test_67_search_views_follow_clinicone_odoo19_contract(self):
        xmlids = (
            "clinic_insurance_authorization.view_insurance_plan_search",
            "clinic_insurance_authorization.view_insurance_plan_rule_search",
            "clinic_insurance_authorization.view_insurance_policy_search",
            "clinic_insurance_authorization.view_insurance_eligibility_search",
            "clinic_insurance_authorization.view_insurance_authorization_search",
            "clinic_insurance_authorization.view_insurance_authorization_line_search",
            "clinic_insurance_authorization.view_insurance_claim_enterprise_search",
            "clinic_insurance_authorization.view_insurance_claim_line_enterprise_search",
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

    def test_68_claim_enterprise_views_exist(self):
        for xmlid in (
            "clinic_insurance_authorization.view_insurance_claim_enterprise_search",
            "clinic_insurance_authorization.view_insurance_claim_enterprise_list",
            "clinic_insurance_authorization.view_insurance_claim_enterprise_form",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_69_claim_line_enterprise_views_exist(self):
        for xmlid in (
            "clinic_insurance_authorization.view_insurance_claim_line_enterprise_search",
            "clinic_insurance_authorization.view_insurance_claim_line_enterprise_list",
            "clinic_insurance_authorization.view_insurance_claim_line_enterprise_form",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_70_authorization_pdf_exists(self):
        self.assertTrue(
            self.env.ref("clinic_insurance_authorization.action_report_insurance_authorization")
        )

    def test_71_claim_pdf_exists(self):
        self.assertTrue(
            self.env.ref("clinic_insurance_authorization.action_report_insurance_claim")
        )

    def test_72_expiry_crons_exist(self):
        for xmlid in (
            "clinic_insurance_authorization.cron_insurance_expire_policies",
            "clinic_insurance_authorization.cron_insurance_expire_eligibility",
            "clinic_insurance_authorization.cron_insurance_expire_authorizations",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_73_settings_action_is_local(self):
        action = self.env.ref("clinic_insurance_authorization.action_insurance_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertIn("clinic_insurance_authorization", action.context or "")

    def test_74_no_parallel_claim_model_exists(self):
        self.assertNotIn("clinic.insurance.authorization.claim", self.env.registry)
        self.assertNotIn("clinic.insurance.claim.v2", self.env.registry)

    def test_75_no_parallel_settlement_ledger_exists(self):
        self.assertNotIn("clinic.insurance.payment", self.env.registry)
        self.assertNotIn("clinic.insurance.account.move", self.env.registry)

    def test_76_partner_primary_policy_contract(self):
        field = self.env["res.partner"]._fields["insurance_policy_id"]
        self.assertEqual(field.comodel_name, "clinic.insurance.policy")

    def test_77_appointment_authorization_state_related_chain(self):
        field = self.env["clinic.appointment"]._fields["insurance_authorization_state"]
        self.assertEqual(field.related, ("authorization_id", "state"))
        self.assertIn("authorization_id", self.env["clinic.appointment"]._fields)

    def test_78_treatment_authorization_state_related_chain(self):
        field = self.env["clinic.treatment"]._fields["insurance_authorization_state"]
        self.assertEqual(field.related, ("authorization_id", "state"))
        self.assertIn("authorization_id", self.env["clinic.treatment"]._fields)

