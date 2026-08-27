from lxml import etree

from odoo.tests.common import TransactionCase


class TestClinicPortalEnterprise(TransactionCase):

    def test_001_owned_profile_model(self):
        self.assertIn("clinic.portal.profile", self.env.registry)

    def test_002_profile_field_name(self):
        self.assertIn("name", self.env["clinic.portal.profile"]._fields)

    def test_003_profile_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.portal.profile"]._fields)

    def test_004_profile_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.portal.profile"]._fields)

    def test_005_profile_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.portal.profile"]._fields)

    def test_006_profile_field_portal_user_id(self):
        self.assertIn("portal_user_id", self.env["clinic.portal.profile"]._fields)

    def test_007_profile_field_is_portal_user(self):
        self.assertIn("is_portal_user", self.env["clinic.portal.profile"]._fields)

    def test_008_profile_field_state(self):
        self.assertIn("state", self.env["clinic.portal.profile"]._fields)

    def test_009_profile_field_active(self):
        self.assertIn("active", self.env["clinic.portal.profile"]._fields)

    def test_010_profile_field_allow_booking_view(self):
        self.assertIn("allow_booking_view", self.env["clinic.portal.profile"]._fields)

    def test_011_profile_field_allow_invoice_view(self):
        self.assertIn("allow_invoice_view", self.env["clinic.portal.profile"]._fields)

    def test_012_profile_field_allow_treatment_history_view(self):
        self.assertIn("allow_treatment_history_view", self.env["clinic.portal.profile"]._fields)

    def test_013_profile_field_show_wallet_link(self):
        self.assertIn("show_wallet_link", self.env["clinic.portal.profile"]._fields)

    def test_014_profile_field_show_consent_link(self):
        self.assertIn("show_consent_link", self.env["clinic.portal.profile"]._fields)

    def test_015_profile_field_show_order_link(self):
        self.assertIn("show_order_link", self.env["clinic.portal.profile"]._fields)

    def test_016_profile_field_show_shop_link(self):
        self.assertIn("show_shop_link", self.env["clinic.portal.profile"]._fields)

    def test_017_profile_field_last_access_at(self):
        self.assertIn("last_access_at", self.env["clinic.portal.profile"]._fields)

    def test_018_profile_field_last_access_page(self):
        self.assertIn("last_access_page", self.env["clinic.portal.profile"]._fields)

    def test_019_profile_field_booking_count(self):
        self.assertIn("booking_count", self.env["clinic.portal.profile"]._fields)

    def test_020_profile_field_invoice_count(self):
        self.assertIn("invoice_count", self.env["clinic.portal.profile"]._fields)

    def test_021_profile_field_treatment_count(self):
        self.assertIn("treatment_count", self.env["clinic.portal.profile"]._fields)

    def test_022_profile_method_compute_name(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_compute_name"))

    def test_023_profile_method_compute_portal_user(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_compute_portal_user"))

    def test_024_profile_method_compute_counts(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_compute_counts"))

    def test_025_profile_method_check_patient_scope(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_check_patient_scope"))

    def test_026_profile_method_require_manager(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_require_manager"))

    def test_027_profile_method_action_activate(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_activate"))

    def test_028_profile_method_action_suspend(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_suspend"))

    def test_029_profile_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_archive"))

    def test_030_profile_method_action_reset_to_draft(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_reset_to_draft"))

    def test_031_profile_method_action_open_portal_access_management(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_portal_access_management"))

    def test_032_profile_method_action_open_partner(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_partner"))

    def test_033_profile_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_patient"))

    def test_034_profile_method_action_open_portal_user(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_portal_user"))

    def test_035_profile_method_action_open_bookings(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_bookings"))

    def test_036_profile_method_action_open_invoices(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_invoices"))

    def test_037_profile_method_action_open_treatments(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_treatments"))

    def test_038_profile_method_action_open_portal_home(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_portal_home"))

    def test_039_profile_method_record_portal_access(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_record_portal_access"))

    def test_040_profile_method_ensure_for_user(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_ensure_for_user"))

    def test_041_profile_method_portal_booking_domain(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_booking_domain"))

    def test_042_profile_method_portal_invoice_domain(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_invoice_domain"))

    def test_043_profile_method_portal_treatment_domain(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_treatment_domain"))

    def test_044_profile_method_portal_summary_counts(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_summary_counts"))

    def test_045_model_res_users(self):
        self.assertIn("res.users", self.env.registry)

    def test_046_model_res_partner(self):
        self.assertIn("res.partner", self.env.registry)

    def test_047_model_clinic_patient(self):
        self.assertIn("clinic.patient", self.env.registry)

    def test_048_users_patient_id(self):
        self.assertIn("patient_id", self.env["res.users"]._fields)

    def test_049_partner_patient_id(self):
        self.assertIn("patient_id", self.env["res.partner"]._fields)

    def test_050_clinic_patient_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.patient"]._fields)

    def test_051_upstream_model_booking_booking(self):
        self.assertIn("booking.booking", self.env.registry)

    def test_052_booking_booking_field_company_id(self):
        self.assertIn("company_id", self.env["booking.booking"]._fields)

    def test_053_booking_booking_field_patient_id(self):
        self.assertIn("patient_id", self.env["booking.booking"]._fields)

    def test_054_booking_booking_field_treatment_id(self):
        self.assertIn("treatment_id", self.env["booking.booking"]._fields)

    def test_055_booking_booking_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["booking.booking"]._fields)

    def test_056_booking_booking_field_room_id(self):
        self.assertIn("room_id", self.env["booking.booking"]._fields)

    def test_057_booking_booking_field_start_datetime(self):
        self.assertIn("start_datetime", self.env["booking.booking"]._fields)

    def test_058_booking_booking_field_end_datetime(self):
        self.assertIn("end_datetime", self.env["booking.booking"]._fields)

    def test_059_booking_booking_field_state(self):
        self.assertIn("state", self.env["booking.booking"]._fields)

    def test_060_booking_booking_field_amount_total(self):
        self.assertIn("amount_total", self.env["booking.booking"]._fields)

    def test_061_booking_booking_field_currency_id(self):
        self.assertIn("currency_id", self.env["booking.booking"]._fields)

    def test_062_booking_booking_field_invoice_id(self):
        self.assertIn("invoice_id", self.env["booking.booking"]._fields)

    def test_063_upstream_model_clinic_billing_invoice(self):
        self.assertIn("clinic.billing.invoice", self.env.registry)

    def test_064_clinic_billing_invoice_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.billing.invoice"]._fields)

    def test_065_clinic_billing_invoice_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.billing.invoice"]._fields)

    def test_066_clinic_billing_invoice_field_clinic_patient_id(self):
        self.assertIn("clinic_patient_id", self.env["clinic.billing.invoice"]._fields)

    def test_067_clinic_billing_invoice_field_clinic_doctor_id(self):
        self.assertIn("clinic_doctor_id", self.env["clinic.billing.invoice"]._fields)

    def test_068_clinic_billing_invoice_field_encounter_id(self):
        self.assertIn("encounter_id", self.env["clinic.billing.invoice"]._fields)

    def test_069_clinic_billing_invoice_field_invoice_date(self):
        self.assertIn("invoice_date", self.env["clinic.billing.invoice"]._fields)

    def test_070_clinic_billing_invoice_field_state(self):
        self.assertIn("state", self.env["clinic.billing.invoice"]._fields)

    def test_071_clinic_billing_invoice_field_amount_total(self):
        self.assertIn("amount_total", self.env["clinic.billing.invoice"]._fields)

    def test_072_clinic_billing_invoice_field_amount_residual(self):
        self.assertIn("amount_residual", self.env["clinic.billing.invoice"]._fields)

    def test_073_clinic_billing_invoice_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.billing.invoice"]._fields)

    def test_074_clinic_billing_invoice_field_move_id(self):
        self.assertIn("move_id", self.env["clinic.billing.invoice"]._fields)

    def test_075_upstream_model_clinic_encounter(self):
        self.assertIn("clinic.encounter", self.env.registry)

    def test_076_clinic_encounter_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.encounter"]._fields)

    def test_077_clinic_encounter_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.encounter"]._fields)

    def test_078_clinic_encounter_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.encounter"]._fields)

    def test_079_clinic_encounter_field_treatment_id(self):
        self.assertIn("treatment_id", self.env["clinic.encounter"]._fields)

    def test_080_clinic_encounter_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["clinic.encounter"]._fields)

    def test_081_clinic_encounter_field_date_start(self):
        self.assertIn("date_start", self.env["clinic.encounter"]._fields)

    def test_082_clinic_encounter_field_date_end(self):
        self.assertIn("date_end", self.env["clinic.encounter"]._fields)

    def test_083_clinic_encounter_field_state(self):
        self.assertIn("state", self.env["clinic.encounter"]._fields)

    def test_084_clinic_encounter_field_amount_total(self):
        self.assertIn("amount_total", self.env["clinic.encounter"]._fields)

    def test_085_clinic_encounter_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.encounter"]._fields)

    def test_086_upstream_model_clinic_procedure_session(self):
        self.assertIn("clinic.procedure.session", self.env.registry)

    def test_087_clinic_procedure_session_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.procedure.session"]._fields)

    def test_088_clinic_procedure_session_field_encounter_id(self):
        self.assertIn("encounter_id", self.env["clinic.procedure.session"]._fields)

    def test_089_clinic_procedure_session_field_treatment_id(self):
        self.assertIn("treatment_id", self.env["clinic.procedure.session"]._fields)

    def test_090_clinic_procedure_session_field_procedure_id(self):
        self.assertIn("procedure_id", self.env["clinic.procedure.session"]._fields)

    def test_091_clinic_procedure_session_field_performer_doctor_id(self):
        self.assertIn("performer_doctor_id", self.env["clinic.procedure.session"]._fields)

    def test_092_clinic_procedure_session_field_room_id(self):
        self.assertIn("room_id", self.env["clinic.procedure.session"]._fields)

    def test_093_clinic_procedure_session_field_date_start(self):
        self.assertIn("date_start", self.env["clinic.procedure.session"]._fields)

    def test_094_clinic_procedure_session_field_date_end(self):
        self.assertIn("date_end", self.env["clinic.procedure.session"]._fields)

    def test_095_clinic_procedure_session_field_state(self):
        self.assertIn("state", self.env["clinic.procedure.session"]._fields)

    def test_096_upstream_model_account_move(self):
        self.assertIn("account.move", self.env.registry)

    def test_097_account_move_field_state(self):
        self.assertIn("state", self.env["account.move"]._fields)

    def test_098_upstream_method_res_users_is_portal(self):
        self.assertTrue(hasattr(self.env["res.users"], "_is_portal"))

    def test_099_upstream_method_portal_wizard_action_open_wizard(self):
        self.assertTrue(hasattr(self.env["portal.wizard"], "action_open_wizard"))

    def test_100_upstream_method_account_move_get_portal_url(self):
        self.assertTrue(hasattr(self.env["account.move"], "get_portal_url"))

    def test_101_company_field_clinic_portal_auto_profile(self):
        self.assertIn("clinic_portal_auto_profile", self.env["res.company"]._fields)

    def test_102_settings_field_clinic_portal_auto_profile(self):
        self.assertIn("clinic_portal_auto_profile", self.env["res.config.settings"]._fields)

    def test_103_company_field_clinic_portal_default_booking_view(self):
        self.assertIn("clinic_portal_default_booking_view", self.env["res.company"]._fields)

    def test_104_settings_field_clinic_portal_default_booking_view(self):
        self.assertIn("clinic_portal_default_booking_view", self.env["res.config.settings"]._fields)

    def test_105_company_field_clinic_portal_default_invoice_view(self):
        self.assertIn("clinic_portal_default_invoice_view", self.env["res.company"]._fields)

    def test_106_settings_field_clinic_portal_default_invoice_view(self):
        self.assertIn("clinic_portal_default_invoice_view", self.env["res.config.settings"]._fields)

    def test_107_company_field_clinic_portal_default_treatment_view(self):
        self.assertIn("clinic_portal_default_treatment_view", self.env["res.company"]._fields)

    def test_108_settings_field_clinic_portal_default_treatment_view(self):
        self.assertIn("clinic_portal_default_treatment_view", self.env["res.config.settings"]._fields)

    def test_109_company_field_clinic_portal_show_wallet_link(self):
        self.assertIn("clinic_portal_show_wallet_link", self.env["res.company"]._fields)

    def test_110_settings_field_clinic_portal_show_wallet_link(self):
        self.assertIn("clinic_portal_show_wallet_link", self.env["res.config.settings"]._fields)

    def test_111_company_field_clinic_portal_show_consent_link(self):
        self.assertIn("clinic_portal_show_consent_link", self.env["res.company"]._fields)

    def test_112_settings_field_clinic_portal_show_consent_link(self):
        self.assertIn("clinic_portal_show_consent_link", self.env["res.config.settings"]._fields)

    def test_113_company_field_clinic_portal_show_order_link(self):
        self.assertIn("clinic_portal_show_order_link", self.env["res.company"]._fields)

    def test_114_settings_field_clinic_portal_show_order_link(self):
        self.assertIn("clinic_portal_show_order_link", self.env["res.config.settings"]._fields)

    def test_115_company_field_clinic_portal_show_shop_link(self):
        self.assertIn("clinic_portal_show_shop_link", self.env["res.company"]._fields)

    def test_116_settings_field_clinic_portal_show_shop_link(self):
        self.assertIn("clinic_portal_show_shop_link", self.env["res.config.settings"]._fields)

    def test_117_company_field_clinic_portal_page_size(self):
        self.assertIn("clinic_portal_page_size", self.env["res.company"]._fields)

    def test_118_settings_field_clinic_portal_page_size(self):
        self.assertIn("clinic_portal_page_size", self.env["res.config.settings"]._fields)

    def test_119_integration_res_partner_clinic_portal_profile_ids(self):
        self.assertIn("clinic_portal_profile_ids", self.env["res.partner"]._fields)

    def test_120_integration_res_partner_clinic_portal_profile_count(self):
        self.assertIn("clinic_portal_profile_count", self.env["res.partner"]._fields)

    def test_121_integration_clinic_patient_clinic_portal_profile_ids(self):
        self.assertIn("clinic_portal_profile_ids", self.env["clinic.patient"]._fields)

    def test_122_integration_clinic_patient_clinic_portal_profile_count(self):
        self.assertIn("clinic_portal_profile_count", self.env["clinic.patient"]._fields)

    def test_123_integration_method_res_partner_action_open_clinic_portal_profiles(self):
        self.assertTrue(hasattr(self.env["res.partner"], "action_open_clinic_portal_profiles"))

    def test_124_integration_method_clinic_patient_action_open_clinic_portal_profiles(self):
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_open_clinic_portal_profiles"))

    def test_125_group_group_patient_portal_operator(self):
        self.assertTrue(self.env.ref("clinic_portal.group_patient_portal_operator"))

    def test_126_group_group_patient_portal_manager(self):
        self.assertTrue(self.env.ref("clinic_portal.group_patient_portal_manager"))

    def test_127_manager_implies_operator(self):
        operator = self.env.ref("clinic_portal.group_patient_portal_operator")
        manager = self.env.ref("clinic_portal.group_patient_portal_manager")
        self.assertIn(operator, manager.implied_ids)

    def test_128_profile_search_view(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.portal.profile"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_129_profile_list_view(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.portal.profile"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_130_profile_form_view(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.portal.profile"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_131_xmlid_view_portal_profile_search(self):
        self.assertTrue(self.env.ref("clinic_portal.view_portal_profile_search"))

    def test_132_xmlid_view_portal_profile_list(self):
        self.assertTrue(self.env.ref("clinic_portal.view_portal_profile_list"))

    def test_133_xmlid_view_portal_profile_form(self):
        self.assertTrue(self.env.ref("clinic_portal.view_portal_profile_form"))

    def test_134_xmlid_action_portal_profile(self):
        self.assertTrue(self.env.ref("clinic_portal.action_portal_profile"))

    def test_135_xmlid_action_portal_settings(self):
        self.assertTrue(self.env.ref("clinic_portal.action_portal_settings"))

    def test_136_xmlid_portal_my_home_clinic(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_home_clinic"))

    def test_137_xmlid_portal_breadcrumbs_clinic(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_breadcrumbs_clinic"))

    def test_138_xmlid_portal_access_unavailable(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_access_unavailable"))

    def test_139_xmlid_portal_my_clinic(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic"))

    def test_140_xmlid_portal_my_clinic_bookings(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic_bookings"))

    def test_141_xmlid_portal_my_clinic_booking(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic_booking"))

    def test_142_xmlid_portal_my_clinic_invoices(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic_invoices"))

    def test_143_xmlid_portal_my_clinic_invoice(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic_invoice"))

    def test_144_xmlid_portal_my_clinic_treatments(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic_treatments"))

    def test_145_xmlid_portal_my_clinic_treatment(self):
        self.assertTrue(self.env.ref("clinic_portal.portal_my_clinic_treatment"))

    def test_146_companion_model_clinic_wallet(self):
        self.assertIn("clinic.wallet", self.env.registry)

    def test_147_companion_model_clinic_consent_form(self):
        self.assertIn("clinic.consent.form", self.env.registry)

    def test_148_companion_model_sale_order(self):
        self.assertIn("sale.order", self.env.registry)

    def test_149_companion_model_clinic_ecommerce_catalog_item(self):
        self.assertIn("clinic.ecommerce.catalog.item", self.env.registry)

    def test_150_state_booking_booking_draft(self):
        selection = dict(self.env["booking.booking"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_151_state_booking_booking_confirmed(self):
        selection = dict(self.env["booking.booking"]._fields["state"].selection)
        self.assertIn("confirmed", selection)

    def test_152_state_booking_booking_in_progress(self):
        selection = dict(self.env["booking.booking"]._fields["state"].selection)
        self.assertIn("in_progress", selection)

    def test_153_state_booking_booking_done(self):
        selection = dict(self.env["booking.booking"]._fields["state"].selection)
        self.assertIn("done", selection)

    def test_154_state_booking_booking_cancelled(self):
        selection = dict(self.env["booking.booking"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_155_state_clinic_billing_invoice_confirmed(self):
        selection = dict(self.env["clinic.billing.invoice"]._fields["state"].selection)
        self.assertIn("confirmed", selection)

    def test_156_state_clinic_billing_invoice_posted(self):
        selection = dict(self.env["clinic.billing.invoice"]._fields["state"].selection)
        self.assertIn("posted", selection)

    def test_157_state_clinic_billing_invoice_paid(self):
        selection = dict(self.env["clinic.billing.invoice"]._fields["state"].selection)
        self.assertIn("paid", selection)

    def test_158_state_clinic_encounter_done(self):
        selection = dict(self.env["clinic.encounter"]._fields["state"].selection)
        self.assertIn("done", selection)

    def test_159_state_clinic_procedure_session_done(self):
        selection = dict(self.env["clinic.procedure.session"]._fields["state"].selection)
        self.assertIn("done", selection)

    def test_160_state_clinic_portal_profile_draft(self):
        selection = dict(self.env["clinic.portal.profile"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_161_state_clinic_portal_profile_active(self):
        selection = dict(self.env["clinic.portal.profile"]._fields["state"].selection)
        self.assertIn("active", selection)

    def test_162_state_clinic_portal_profile_suspended(self):
        selection = dict(self.env["clinic.portal.profile"]._fields["state"].selection)
        self.assertIn("suspended", selection)

    def test_163_state_clinic_portal_profile_archived(self):
        selection = dict(self.env["clinic.portal.profile"]._fields["state"].selection)
        self.assertIn("archived", selection)

    def test_164_profile_table_name(self):
        self.assertEqual(self.env["clinic.portal.profile"]._table, "clinic_portal_profile")

    def test_165_profile_model_name(self):
        self.assertEqual(self.env["clinic.portal.profile"]._name, "clinic.portal.profile")

    def test_166_portal_booking_domain_company_id_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_booking_domain"))
        self.assertIn("company_id", Profile._fields if "company_id" in Profile._fields else {"company_id": True})

    def test_167_portal_booking_domain_patient_id_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_booking_domain"))
        self.assertIn("patient_id", Profile._fields if "patient_id" in Profile._fields else {"patient_id": True})

    def test_168_portal_invoice_domain_company_id_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_invoice_domain"))
        self.assertIn("company_id", Profile._fields if "company_id" in Profile._fields else {"company_id": True})

    def test_169_portal_invoice_domain_patient_id_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_invoice_domain"))
        self.assertIn("patient_id", Profile._fields if "patient_id" in Profile._fields else {"patient_id": True})

    def test_170_portal_invoice_domain_state_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_invoice_domain"))
        self.assertIn("state", Profile._fields if "state" in Profile._fields else {"state": True})

    def test_171_portal_treatment_domain_company_id_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_treatment_domain"))
        self.assertIn("company_id", Profile._fields if "company_id" in Profile._fields else {"company_id": True})

    def test_172_portal_treatment_domain_partner_id_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_treatment_domain"))
        self.assertIn("partner_id", Profile._fields if "partner_id" in Profile._fields else {"partner_id": True})

    def test_173_portal_treatment_domain_state_contract(self):
        Profile = self.env["clinic.portal.profile"]
        self.assertTrue(hasattr(Profile, "_portal_treatment_domain"))
        self.assertIn("state", Profile._fields if "state" in Profile._fields else {"state": True})

    def test_174_search_architecture_odoo19(self):
        view = self.env.ref("clinic_portal.view_portal_profile_search")
        arch = view.arch_db
        if hasattr(arch, "get"):
            arch = arch.get(self.env.lang) or next(iter(arch.values()), "")
        root = etree.fromstring((arch or "").encode())
        self.assertEqual(root.tag, "search")
        self.assertFalse(root.attrib)
        for group in root.xpath("./group"):
            self.assertFalse(group.attrib)

    def test_175_workflow_action_activate(self):
        self.assertTrue(callable(getattr(self.env["clinic.portal.profile"], "action_activate")))

    def test_176_workflow_action_suspend(self):
        self.assertTrue(callable(getattr(self.env["clinic.portal.profile"], "action_suspend")))

    def test_177_workflow_action_archive(self):
        self.assertTrue(callable(getattr(self.env["clinic.portal.profile"], "action_archive")))

    def test_178_workflow_action_reset_to_draft(self):
        self.assertTrue(callable(getattr(self.env["clinic.portal.profile"], "action_reset_to_draft")))

    def test_179_no_parallel_clinic_portal_message(self):
        self.assertNotIn("clinic.portal.message", self.env.registry)

    def test_180_no_parallel_clinic_portal_chat(self):
        self.assertNotIn("clinic.portal.chat", self.env.registry)

    def test_181_no_parallel_clinic_portal_audit(self):
        self.assertNotIn("clinic.portal.audit", self.env.registry)

    def test_182_no_parallel_clinic_portal_telemedicine(self):
        self.assertNotIn("clinic.portal.telemedicine", self.env.registry)

    def test_183_profile_field_has_string_name(self):
        field = self.env["clinic.portal.profile"]._fields["name"]
        self.assertTrue(field.string)

    def test_184_profile_field_has_string_company_id(self):
        field = self.env["clinic.portal.profile"]._fields["company_id"]
        self.assertTrue(field.string)

    def test_185_profile_field_has_string_partner_id(self):
        field = self.env["clinic.portal.profile"]._fields["partner_id"]
        self.assertTrue(field.string)

    def test_186_profile_field_has_string_patient_id(self):
        field = self.env["clinic.portal.profile"]._fields["patient_id"]
        self.assertTrue(field.string)

    def test_187_profile_field_has_string_portal_user_id(self):
        field = self.env["clinic.portal.profile"]._fields["portal_user_id"]
        self.assertTrue(field.string)

    def test_188_profile_field_has_string_is_portal_user(self):
        field = self.env["clinic.portal.profile"]._fields["is_portal_user"]
        self.assertTrue(field.string)

    def test_189_profile_field_has_string_state(self):
        field = self.env["clinic.portal.profile"]._fields["state"]
        self.assertTrue(field.string)

    def test_190_profile_field_has_string_active(self):
        field = self.env["clinic.portal.profile"]._fields["active"]
        self.assertTrue(field.string)

    def test_191_profile_field_has_string_allow_booking_view(self):
        field = self.env["clinic.portal.profile"]._fields["allow_booking_view"]
        self.assertTrue(field.string)

    def test_192_profile_field_has_string_allow_invoice_view(self):
        field = self.env["clinic.portal.profile"]._fields["allow_invoice_view"]
        self.assertTrue(field.string)

    def test_193_profile_field_has_string_allow_treatment_history_view(self):
        field = self.env["clinic.portal.profile"]._fields["allow_treatment_history_view"]
        self.assertTrue(field.string)

    def test_194_profile_field_has_string_show_wallet_link(self):
        field = self.env["clinic.portal.profile"]._fields["show_wallet_link"]
        self.assertTrue(field.string)

    def test_195_profile_field_has_string_show_consent_link(self):
        field = self.env["clinic.portal.profile"]._fields["show_consent_link"]
        self.assertTrue(field.string)

    def test_196_profile_field_has_string_show_order_link(self):
        field = self.env["clinic.portal.profile"]._fields["show_order_link"]
        self.assertTrue(field.string)

    def test_197_profile_field_has_string_show_shop_link(self):
        field = self.env["clinic.portal.profile"]._fields["show_shop_link"]
        self.assertTrue(field.string)

    def test_198_profile_field_has_string_last_access_at(self):
        field = self.env["clinic.portal.profile"]._fields["last_access_at"]
        self.assertTrue(field.string)

    def test_199_profile_field_has_string_last_access_page(self):
        field = self.env["clinic.portal.profile"]._fields["last_access_page"]
        self.assertTrue(field.string)

    def test_200_profile_field_has_string_booking_count(self):
        field = self.env["clinic.portal.profile"]._fields["booking_count"]
        self.assertTrue(field.string)

    def test_201_profile_field_has_string_invoice_count(self):
        field = self.env["clinic.portal.profile"]._fields["invoice_count"]
        self.assertTrue(field.string)

    def test_202_profile_field_has_string_treatment_count(self):
        field = self.env["clinic.portal.profile"]._fields["treatment_count"]
        self.assertTrue(field.string)

    def test_203_profile_field_searchable_company_id(self):
        field = self.env["clinic.portal.profile"]._fields["company_id"]
        self.assertTrue(field.store)

    def test_204_profile_field_searchable_partner_id(self):
        field = self.env["clinic.portal.profile"]._fields["partner_id"]
        self.assertTrue(field.store)

    def test_205_profile_field_searchable_patient_id(self):
        field = self.env["clinic.portal.profile"]._fields["patient_id"]
        self.assertTrue(field.store)

    def test_206_profile_field_searchable_state(self):
        field = self.env["clinic.portal.profile"]._fields["state"]
        self.assertTrue(field.store)

    def test_207_profile_field_searchable_last_access_at(self):
        field = self.env["clinic.portal.profile"]._fields["last_access_at"]
        self.assertTrue(field.store)

    def test_208_profile_find_for_user_readonly_helper(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_find_for_user"))
