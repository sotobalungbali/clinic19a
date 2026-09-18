from lxml import etree

from odoo.tests.common import TransactionCase


class TestClinicReportsEnterprise(TransactionCase):

    def test_001_owned_model_1(self):
        self.assertIn("clinic.report.definition", self.env.registry)

    def test_002_owned_model_2(self):
        self.assertIn("clinic.report.run", self.env.registry)

    def test_003_owned_model_3(self):
        self.assertIn("clinic.report.metric", self.env.registry)

    def test_004_owned_model_4(self):
        self.assertIn("clinic.report.detail", self.env.registry)

    def test_005_owned_model_5(self):
        self.assertIn("clinic.report.schedule", self.env.registry)

    def test_006_model_clinic_report_company_mixin(self):
        self.assertIn("clinic.report.company.mixin", self.env.registry)

    def test_007_model_clinic_report_engine_financial(self):
        self.assertIn("clinic.report.engine.financial", self.env.registry)

    def test_008_model_clinic_report_engine_operational(self):
        self.assertIn("clinic.report.engine.operational", self.env.registry)

    def test_009_model_clinic_report_engine_clinical(self):
        self.assertIn("clinic.report.engine.clinical", self.env.registry)

    def test_010_model_clinic_report_generate_wizard(self):
        self.assertIn("clinic.report.generate.wizard", self.env.registry)

    def test_011_definition_field_name(self):
        self.assertIn("name", self.env["clinic.report.definition"]._fields)

    def test_012_definition_field_code(self):
        self.assertIn("code", self.env["clinic.report.definition"]._fields)

    def test_013_definition_field_family(self):
        self.assertIn("family", self.env["clinic.report.definition"]._fields)

    def test_014_definition_field_report_key(self):
        self.assertIn("report_key", self.env["clinic.report.definition"]._fields)

    def test_015_definition_field_state(self):
        self.assertIn("state", self.env["clinic.report.definition"]._fields)

    def test_016_definition_field_methodology(self):
        self.assertIn("methodology", self.env["clinic.report.definition"]._fields)

    def test_017_definition_field_default_detail_limit(self):
        self.assertIn("default_detail_limit", self.env["clinic.report.definition"]._fields)

    def test_018_definition_field_allow_branch_filter(self):
        self.assertIn("allow_branch_filter", self.env["clinic.report.definition"]._fields)

    def test_019_definition_field_include_details_by_default(self):
        self.assertIn("include_details_by_default", self.env["clinic.report.definition"]._fields)

    def test_020_definition_field_run_ids(self):
        self.assertIn("run_ids", self.env["clinic.report.definition"]._fields)

    def test_021_definition_field_run_count(self):
        self.assertIn("run_count", self.env["clinic.report.definition"]._fields)

    def test_022_definition_field_schedule_count(self):
        self.assertIn("schedule_count", self.env["clinic.report.definition"]._fields)

    def test_023_definition_method_action_activate(self):
        self.assertTrue(hasattr(self.env["clinic.report.definition"], "action_activate"))

    def test_024_definition_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.report.definition"], "action_archive"))

    def test_025_definition_method_action_reset_to_draft(self):
        self.assertTrue(hasattr(self.env["clinic.report.definition"], "action_reset_to_draft"))

    def test_026_definition_method_action_generate_report(self):
        self.assertTrue(hasattr(self.env["clinic.report.definition"], "action_generate_report"))

    def test_027_definition_method_action_view_runs(self):
        self.assertTrue(hasattr(self.env["clinic.report.definition"], "action_view_runs"))

    def test_028_definition_method_action_view_schedules(self):
        self.assertTrue(hasattr(self.env["clinic.report.definition"], "action_view_schedules"))

    def test_029_run_field_name(self):
        self.assertIn("name", self.env["clinic.report.run"]._fields)

    def test_030_run_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.report.run"]._fields)

    def test_031_run_field_schedule_id(self):
        self.assertIn("schedule_id", self.env["clinic.report.run"]._fields)

    def test_032_run_field_family(self):
        self.assertIn("family", self.env["clinic.report.run"]._fields)

    def test_033_run_field_report_key(self):
        self.assertIn("report_key", self.env["clinic.report.run"]._fields)

    def test_034_run_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.report.run"]._fields)

    def test_035_run_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.report.run"]._fields)

    def test_036_run_field_date_from(self):
        self.assertIn("date_from", self.env["clinic.report.run"]._fields)

    def test_037_run_field_date_to(self):
        self.assertIn("date_to", self.env["clinic.report.run"]._fields)

    def test_038_run_field_include_details(self):
        self.assertIn("include_details", self.env["clinic.report.run"]._fields)

    def test_039_run_field_detail_limit(self):
        self.assertIn("detail_limit", self.env["clinic.report.run"]._fields)

    def test_040_run_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.report.run"]._fields)

    def test_041_run_field_state(self):
        self.assertIn("state", self.env["clinic.report.run"]._fields)

    def test_042_run_field_generated_at(self):
        self.assertIn("generated_at", self.env["clinic.report.run"]._fields)

    def test_043_run_field_generated_by_id(self):
        self.assertIn("generated_by_id", self.env["clinic.report.run"]._fields)

    def test_044_run_field_finalized_at(self):
        self.assertIn("finalized_at", self.env["clinic.report.run"]._fields)

    def test_045_run_field_finalized_by_id(self):
        self.assertIn("finalized_by_id", self.env["clinic.report.run"]._fields)

    def test_046_run_field_error_message(self):
        self.assertIn("error_message", self.env["clinic.report.run"]._fields)

    def test_047_run_field_methodology_snapshot(self):
        self.assertIn("methodology_snapshot", self.env["clinic.report.run"]._fields)

    def test_048_run_field_metric_ids(self):
        self.assertIn("metric_ids", self.env["clinic.report.run"]._fields)

    def test_049_run_field_detail_ids(self):
        self.assertIn("detail_ids", self.env["clinic.report.run"]._fields)

    def test_050_run_field_metric_count(self):
        self.assertIn("metric_count", self.env["clinic.report.run"]._fields)

    def test_051_run_field_detail_count(self):
        self.assertIn("detail_count", self.env["clinic.report.run"]._fields)

    def test_052_run_field_csv_file(self):
        self.assertIn("csv_file", self.env["clinic.report.run"]._fields)

    def test_053_run_field_csv_filename(self):
        self.assertIn("csv_filename", self.env["clinic.report.run"]._fields)

    def test_054_run_method_actionxgenerate(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_generate"))

    def test_055_run_method_actionxfinalize(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_finalize"))

    def test_056_run_method_actionxresetxtoxdraft(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_reset_to_draft"))

    def test_057_run_method_actionxarchive(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_archive"))

    def test_058_run_method_actionxviewxmetrics(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_view_metrics"))

    def test_059_run_method_actionxviewxdetails(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_view_details"))

    def test_060_run_method_actionxdownloadxcsv(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_download_csv"))

    def test_061_run_method_actionxprintxpdf(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_print_pdf"))

    def test_062_run_method_addxmetric(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_add_metric"))

    def test_063_run_method_addxdetail(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_add_detail"))

    def test_064_run_method_reportxdomain(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_report_domain"))

    def test_065_engine_generate_fin_revenue(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_revenue"))

    def test_066_engine_generate_fin_receivables(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_receivables"))

    def test_067_engine_generate_fin_payables(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_payables"))

    def test_068_engine_generate_fin_cashflow(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_cashflow"))

    def test_069_engine_generate_fin_accounting(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_accounting"))

    def test_070_engine_generate_fin_tax(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_tax"))

    def test_071_engine_generate_fin_insurance(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_fin_insurance"))

    def test_072_engine_generate_ops_booking(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_ops_booking"))

    def test_073_engine_generate_ops_queue(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_ops_queue"))

    def test_074_engine_generate_ops_room(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_ops_room"))

    def test_075_engine_generate_ops_inventory(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_ops_inventory"))

    def test_076_engine_generate_ops_membership(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_ops_membership"))

    def test_077_engine_generate_ops_wallet(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_ops_wallet"))

    def test_078_engine_generate_clinical_encounter(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_clinical_encounter"))

    def test_079_engine_generate_clinical_procedure(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_clinical_procedure"))

    def test_080_engine_generate_clinical_triage(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_clinical_triage"))

    def test_081_engine_generate_clinical_adverse(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_clinical_adverse"))

    def test_082_engine_generate_clinical_postcare(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_clinical_postcare"))

    def test_083_engine_generate_clinical_feedback(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "_generate_clinical_feedback"))

    def test_084_clinic_report_metric_field_run_id(self):
        self.assertIn("run_id", self.env["clinic.report.metric"]._fields)

    def test_085_clinic_report_metric_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.report.metric"]._fields)

    def test_086_clinic_report_metric_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.report.metric"]._fields)

    def test_087_clinic_report_metric_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.report.metric"]._fields)

    def test_088_clinic_report_metric_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.report.metric"]._fields)

    def test_089_clinic_report_metric_field_code(self):
        self.assertIn("code", self.env["clinic.report.metric"]._fields)

    def test_090_clinic_report_metric_field_name(self):
        self.assertIn("name", self.env["clinic.report.metric"]._fields)

    def test_091_clinic_report_metric_field_metric_type(self):
        self.assertIn("metric_type", self.env["clinic.report.metric"]._fields)

    def test_092_clinic_report_metric_field_value(self):
        self.assertIn("value", self.env["clinic.report.metric"]._fields)

    def test_093_clinic_report_metric_field_display_value(self):
        self.assertIn("display_value", self.env["clinic.report.metric"]._fields)

    def test_094_clinic_report_detail_field_run_id(self):
        self.assertIn("run_id", self.env["clinic.report.detail"]._fields)

    def test_095_clinic_report_detail_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.report.detail"]._fields)

    def test_096_clinic_report_detail_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.report.detail"]._fields)

    def test_097_clinic_report_detail_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.report.detail"]._fields)

    def test_098_clinic_report_detail_field_event_date(self):
        self.assertIn("event_date", self.env["clinic.report.detail"]._fields)

    def test_099_clinic_report_detail_field_reference(self):
        self.assertIn("reference", self.env["clinic.report.detail"]._fields)

    def test_100_clinic_report_detail_field_label(self):
        self.assertIn("label", self.env["clinic.report.detail"]._fields)

    def test_101_clinic_report_detail_field_source_model(self):
        self.assertIn("source_model", self.env["clinic.report.detail"]._fields)

    def test_102_clinic_report_detail_field_source_res_id(self):
        self.assertIn("source_res_id", self.env["clinic.report.detail"]._fields)

    def test_103_clinic_report_detail_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.report.detail"]._fields)

    def test_104_clinic_report_detail_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["clinic.report.detail"]._fields)

    def test_105_clinic_report_detail_field_staff_id(self):
        self.assertIn("staff_id", self.env["clinic.report.detail"]._fields)

    def test_106_clinic_report_detail_field_treatment_id(self):
        self.assertIn("treatment_id", self.env["clinic.report.detail"]._fields)

    def test_107_clinic_report_detail_field_room_id(self):
        self.assertIn("room_id", self.env["clinic.report.detail"]._fields)

    def test_108_clinic_report_detail_field_amount(self):
        self.assertIn("amount", self.env["clinic.report.detail"]._fields)

    def test_109_clinic_report_detail_field_quantity(self):
        self.assertIn("quantity", self.env["clinic.report.detail"]._fields)

    def test_110_clinic_report_detail_field_duration_minutes(self):
        self.assertIn("duration_minutes", self.env["clinic.report.detail"]._fields)

    def test_111_clinic_report_detail_field_rating(self):
        self.assertIn("rating", self.env["clinic.report.detail"]._fields)

    def test_112_clinic_report_schedule_field_name(self):
        self.assertIn("name", self.env["clinic.report.schedule"]._fields)

    def test_113_clinic_report_schedule_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.report.schedule"]._fields)

    def test_114_clinic_report_schedule_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.report.schedule"]._fields)

    def test_115_clinic_report_schedule_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.report.schedule"]._fields)

    def test_116_clinic_report_schedule_field_cadence(self):
        self.assertIn("cadence", self.env["clinic.report.schedule"]._fields)

    def test_117_clinic_report_schedule_field_window_days(self):
        self.assertIn("window_days", self.env["clinic.report.schedule"]._fields)

    def test_118_clinic_report_schedule_field_owner_user_id(self):
        self.assertIn("owner_user_id", self.env["clinic.report.schedule"]._fields)

    def test_119_clinic_report_schedule_field_next_run_at(self):
        self.assertIn("next_run_at", self.env["clinic.report.schedule"]._fields)

    def test_120_clinic_report_schedule_field_last_run_at(self):
        self.assertIn("last_run_at", self.env["clinic.report.schedule"]._fields)

    def test_121_clinic_report_schedule_field_last_run_id(self):
        self.assertIn("last_run_id", self.env["clinic.report.schedule"]._fields)

    def test_122_clinic_report_schedule_field_state(self):
        self.assertIn("state", self.env["clinic.report.schedule"]._fields)

    def test_123_clinic_report_metric_method_action_open_run(self):
        self.assertTrue(hasattr(self.env["clinic.report.metric"], "action_open_run"))

    def test_124_clinic_report_detail_method_action_open_source(self):
        self.assertTrue(hasattr(self.env["clinic.report.detail"], "action_open_source"))

    def test_125_clinic_report_detail_method_action_open_run(self):
        self.assertTrue(hasattr(self.env["clinic.report.detail"], "action_open_run"))

    def test_126_clinic_report_schedule_method_action_run_now(self):
        self.assertTrue(hasattr(self.env["clinic.report.schedule"], "action_run_now"))

    def test_127_clinic_report_schedule_method_action_pause(self):
        self.assertTrue(hasattr(self.env["clinic.report.schedule"], "action_pause"))

    def test_128_clinic_report_schedule_method_action_resume(self):
        self.assertTrue(hasattr(self.env["clinic.report.schedule"], "action_resume"))

    def test_129_clinic_report_schedule_method_action_view_runs(self):
        self.assertTrue(hasattr(self.env["clinic.report.schedule"], "action_view_runs"))

    def test_130_clinic_report_schedule_method_cron_run_due_schedules(self):
        self.assertTrue(hasattr(self.env["clinic.report.schedule"], "_cron_run_due_schedules"))

    def test_131_company_field_clinic_reports_default_window_days(self):
        self.assertIn("clinic_reports_default_window_days", self.env["res.company"]._fields)

    def test_132_company_field_clinic_reports_default_detail_limit(self):
        self.assertIn("clinic_reports_default_detail_limit", self.env["res.company"]._fields)

    def test_133_company_field_clinic_reports_auto_finalize_scheduled(self):
        self.assertIn("clinic_reports_auto_finalize_scheduled", self.env["res.company"]._fields)

    def test_134_company_field_clinic_reports_retention_days(self):
        self.assertIn("clinic_reports_retention_days", self.env["res.company"]._fields)

    def test_135_company_field_clinic_report_run_ids(self):
        self.assertIn("clinic_report_run_ids", self.env["res.company"]._fields)

    def test_136_company_field_clinic_report_run_count(self):
        self.assertIn("clinic_report_run_count", self.env["res.company"]._fields)

    def test_137_branch_field_report_run_ids(self):
        self.assertIn("report_run_ids", self.env["clinic.branch"]._fields)

    def test_138_branch_field_report_run_count(self):
        self.assertIn("report_run_count", self.env["clinic.branch"]._fields)

    def test_139_branch_policy_exists(self):
        self.assertIn("policy_branch_scope_reports", self.env["res.company"]._fields)

    def test_140_company_action(self):
        self.assertTrue(hasattr(self.env["res.company"], "action_open_clinic_report_runs"))

    def test_141_branch_action(self):
        self.assertTrue(hasattr(self.env["clinic.branch"], "action_open_report_runs"))

    def test_142_seed_definition_count(self):
        self.assertEqual(self.env["clinic.report.definition"].search_count([]), 19)

    def test_143_definition_key_fin_revenue(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_revenue")], limit=1))

    def test_144_definition_key_fin_receivables(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_receivables")], limit=1))

    def test_145_definition_key_fin_payables(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_payables")], limit=1))

    def test_146_definition_key_fin_cashflow(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_cashflow")], limit=1))

    def test_147_definition_key_fin_accounting(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_accounting")], limit=1))

    def test_148_definition_key_fin_tax(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_tax")], limit=1))

    def test_149_definition_key_fin_insurance(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","fin_insurance")], limit=1))

    def test_150_definition_key_ops_booking(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","ops_booking")], limit=1))

    def test_151_definition_key_ops_queue(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","ops_queue")], limit=1))

    def test_152_definition_key_ops_room(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","ops_room")], limit=1))

    def test_153_definition_key_ops_inventory(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","ops_inventory")], limit=1))

    def test_154_definition_key_ops_membership(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","ops_membership")], limit=1))

    def test_155_definition_key_ops_wallet(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","ops_wallet")], limit=1))

    def test_156_definition_key_clinical_encounter(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","clinical_encounter")], limit=1))

    def test_157_definition_key_clinical_procedure(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","clinical_procedure")], limit=1))

    def test_158_definition_key_clinical_triage(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","clinical_triage")], limit=1))

    def test_159_definition_key_clinical_adverse(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","clinical_adverse")], limit=1))

    def test_160_definition_key_clinical_postcare(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","clinical_postcare")], limit=1))

    def test_161_definition_key_clinical_feedback(self):
        self.assertTrue(self.env["clinic.report.definition"].search([("report_key","=","clinical_feedback")], limit=1))

    def test_162_group_group_reports_user(self):
        self.assertTrue(self.env.ref("clinic_reports.group_reports_user"))

    def test_163_group_group_reports_analyst(self):
        self.assertTrue(self.env.ref("clinic_reports.group_reports_analyst"))

    def test_164_group_group_reports_manager(self):
        self.assertTrue(self.env.ref("clinic_reports.group_reports_manager"))

    def test_165_group_hierarchy_analyst(self):
        user = self.env.ref("clinic_reports.group_reports_user")
        analyst = self.env.ref("clinic_reports.group_reports_analyst")
        self.assertIn(user, analyst.implied_ids)

    def test_166_group_hierarchy_manager(self):
        analyst = self.env.ref("clinic_reports.group_reports_analyst")
        manager = self.env.ref("clinic_reports.group_reports_manager")
        self.assertIn(analyst, manager.implied_ids)

    def test_167_clinic_report_definition_search_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.definition"),("type","=","search")], limit=1))

    def test_168_clinic_report_definition_list_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.definition"),("type","=","list")], limit=1))

    def test_169_clinic_report_definition_form_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.definition"),("type","=","form")], limit=1))

    def test_170_clinic_report_run_search_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.run"),("type","=","search")], limit=1))

    def test_171_clinic_report_run_list_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.run"),("type","=","list")], limit=1))

    def test_172_clinic_report_run_form_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.run"),("type","=","form")], limit=1))

    def test_173_clinic_report_metric_search_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.metric"),("type","=","search")], limit=1))

    def test_174_clinic_report_metric_list_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.metric"),("type","=","list")], limit=1))

    def test_175_clinic_report_metric_form_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.metric"),("type","=","form")], limit=1))

    def test_176_clinic_report_detail_search_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.detail"),("type","=","search")], limit=1))

    def test_177_clinic_report_detail_list_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.detail"),("type","=","list")], limit=1))

    def test_178_clinic_report_detail_form_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.detail"),("type","=","form")], limit=1))

    def test_179_clinic_report_schedule_search_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.schedule"),("type","=","search")], limit=1))

    def test_180_clinic_report_schedule_list_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.schedule"),("type","=","list")], limit=1))

    def test_181_clinic_report_schedule_form_view(self):
        self.assertTrue(self.env["ir.ui.view"].search([("model","=","clinic.report.schedule"),("type","=","form")], limit=1))

    def test_182_view_view_report_metric_pivot(self):
        view=self.env.ref("clinic_reports.view_report_metric_pivot"); self.assertEqual(view.type, "pivot")

    def test_183_view_view_report_metric_graph(self):
        view=self.env.ref("clinic_reports.view_report_metric_graph"); self.assertEqual(view.type, "graph")

    def test_184_view_view_report_detail_pivot(self):
        view=self.env.ref("clinic_reports.view_report_detail_pivot"); self.assertEqual(view.type, "pivot")

    def test_185_view_view_report_detail_graph(self):
        view=self.env.ref("clinic_reports.view_report_detail_graph"); self.assertEqual(view.type, "graph")

    def test_186_service_action_report_clinic_report_run(self):
        self.assertTrue(self.env.ref("clinic_reports.action_report_clinic_report_run"))

    def test_187_service_cron_run_due_report_schedules(self):
        self.assertTrue(self.env.ref("clinic_reports.cron_run_due_report_schedules"))

    def test_188_service_action_generate_report_wizard(self):
        self.assertTrue(self.env.ref("clinic_reports.action_generate_report_wizard"))

    def test_189_service_action_reports_settings(self):
        self.assertTrue(self.env.ref("clinic_reports.action_reports_settings"))

    def test_190_search_architecture(self):
        xmlids = (
            "clinic_reports.view_report_definition_search",
            "clinic_reports.view_report_run_search",
            "clinic_reports.view_report_metric_search",
            "clinic_reports.view_report_detail_search",
            "clinic_reports.view_report_schedule_search",
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

    def test_191_no_parallel_dashboard_model_owned_by_reports(self):
        self.assertNotIn("clinic.report.dashboard", self.env.registry)

    def test_192_no_parallel_analytics_model_owned_by_reports(self):
        self.assertNotIn("clinic.report.analytics", self.env.registry)

    def test_193_no_parallel_portal_model_owned_by_reports(self):
        self.assertNotIn("clinic.report.portal", self.env.registry)

