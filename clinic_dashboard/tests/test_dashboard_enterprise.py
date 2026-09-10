from lxml import etree

from odoo.tests.common import TransactionCase


class TestClinicDashboardEnterprise(TransactionCase):

    def test_001_model_clinic_dashboard_board(self):
        self.assertIn("clinic.dashboard.board", self.env.registry)

    def test_002_model_clinic_dashboard_widget(self):
        self.assertIn("clinic.dashboard.widget", self.env.registry)

    def test_003_model_clinic_dashboard_snapshot(self):
        self.assertIn("clinic.dashboard.snapshot", self.env.registry)

    def test_004_model_clinic_dashboard_snapshot_line(self):
        self.assertIn("clinic.dashboard.snapshot.line", self.env.registry)

    def test_005_board_field_name(self):
        self.assertIn("name", self.env["clinic.dashboard.board"]._fields)

    def test_006_board_field_code(self):
        self.assertIn("code", self.env["clinic.dashboard.board"]._fields)

    def test_007_board_field_sequence(self):
        self.assertIn("sequence", self.env["clinic.dashboard.board"]._fields)

    def test_008_board_field_dashboard_type(self):
        self.assertIn("dashboard_type", self.env["clinic.dashboard.board"]._fields)

    def test_009_board_field_description(self):
        self.assertIn("description", self.env["clinic.dashboard.board"]._fields)

    def test_010_board_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.dashboard.board"]._fields)

    def test_011_board_field_default_branch_id(self):
        self.assertIn("default_branch_id", self.env["clinic.dashboard.board"]._fields)

    def test_012_board_field_default_period(self):
        self.assertIn("default_period", self.env["clinic.dashboard.board"]._fields)

    def test_013_board_field_auto_generate_missing_reports(self):
        self.assertIn("auto_generate_missing_reports", self.env["clinic.dashboard.board"]._fields)

    def test_014_board_field_auto_refresh(self):
        self.assertIn("auto_refresh", self.env["clinic.dashboard.board"]._fields)

    def test_015_board_field_refresh_interval_hours(self):
        self.assertIn("refresh_interval_hours", self.env["clinic.dashboard.board"]._fields)

    def test_016_board_field_next_refresh_at(self):
        self.assertIn("next_refresh_at", self.env["clinic.dashboard.board"]._fields)

    def test_017_board_field_owner_user_id(self):
        self.assertIn("owner_user_id", self.env["clinic.dashboard.board"]._fields)

    def test_018_board_field_state(self):
        self.assertIn("state", self.env["clinic.dashboard.board"]._fields)

    def test_019_board_field_active(self):
        self.assertIn("active", self.env["clinic.dashboard.board"]._fields)

    def test_020_board_field_widget_ids(self):
        self.assertIn("widget_ids", self.env["clinic.dashboard.board"]._fields)

    def test_021_board_field_snapshot_ids(self):
        self.assertIn("snapshot_ids", self.env["clinic.dashboard.board"]._fields)

    def test_022_board_field_widget_count(self):
        self.assertIn("widget_count", self.env["clinic.dashboard.board"]._fields)

    def test_023_board_field_snapshot_count(self):
        self.assertIn("snapshot_count", self.env["clinic.dashboard.board"]._fields)

    def test_024_board_field_latest_snapshot_id(self):
        self.assertIn("latest_snapshot_id", self.env["clinic.dashboard.board"]._fields)

    def test_025_board_method_resolve_period(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_resolve_period"))

    def test_026_board_method_validate_runtime_scope(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_validate_runtime_scope"))

    def test_027_board_method_previous_period(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_previous_period"))

    def test_028_board_method_find_report_run(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_find_report_run"))

    def test_029_board_method_ensure_report_run(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_ensure_report_run"))

    def test_030_board_method_find_previous_metric(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_find_previous_metric"))

    def test_031_board_method_refresh_snapshot(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_refresh_snapshot"))

    def test_032_board_method_action_refresh(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_refresh"))

    def test_033_board_method_action_activate(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_activate"))

    def test_034_board_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_archive"))

    def test_035_board_method_action_reset_to_draft(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_reset_to_draft"))

    def test_036_board_method_action_open_live_dashboard(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_open_live_dashboard"))

    def test_037_board_method_action_view_widgets(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_view_widgets"))

    def test_038_board_method_action_view_snapshots(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_view_snapshots"))

    def test_039_board_method_action_view_report_runs(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "action_view_report_runs"))

    def test_040_board_method_ensure_default_boards(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_ensure_default_boards"))

    def test_041_board_method_get_dashboard_bootstrap(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "get_dashboard_bootstrap"))

    def test_042_board_method_get_dashboard_payload(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "get_dashboard_payload"))

    def test_043_board_method_payload_from_snapshot(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_payload_from_snapshot"))

    def test_044_board_method_cron_refresh_due_boards(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.board"], "_cron_refresh_due_boards"))

    def test_045_widget_field_board_id(self):
        self.assertIn("board_id", self.env["clinic.dashboard.widget"]._fields)

    def test_046_widget_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.dashboard.widget"]._fields)

    def test_047_widget_field_sequence(self):
        self.assertIn("sequence", self.env["clinic.dashboard.widget"]._fields)

    def test_048_widget_field_name(self):
        self.assertIn("name", self.env["clinic.dashboard.widget"]._fields)

    def test_049_widget_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.dashboard.widget"]._fields)

    def test_050_widget_field_report_key(self):
        self.assertIn("report_key", self.env["clinic.dashboard.widget"]._fields)

    def test_051_widget_field_metric_code(self):
        self.assertIn("metric_code", self.env["clinic.dashboard.widget"]._fields)

    def test_052_widget_field_icon(self):
        self.assertIn("icon", self.env["clinic.dashboard.widget"]._fields)

    def test_053_widget_field_display_style(self):
        self.assertIn("display_style", self.env["clinic.dashboard.widget"]._fields)

    def test_054_widget_field_column_span(self):
        self.assertIn("column_span", self.env["clinic.dashboard.widget"]._fields)

    def test_055_widget_field_direction(self):
        self.assertIn("direction", self.env["clinic.dashboard.widget"]._fields)

    def test_056_widget_field_has_target(self):
        self.assertIn("has_target", self.env["clinic.dashboard.widget"]._fields)

    def test_057_widget_field_target_value(self):
        self.assertIn("target_value", self.env["clinic.dashboard.widget"]._fields)

    def test_058_widget_field_has_warning_threshold(self):
        self.assertIn("has_warning_threshold", self.env["clinic.dashboard.widget"]._fields)

    def test_059_widget_field_warning_threshold(self):
        self.assertIn("warning_threshold", self.env["clinic.dashboard.widget"]._fields)

    def test_060_widget_field_has_critical_threshold(self):
        self.assertIn("has_critical_threshold", self.env["clinic.dashboard.widget"]._fields)

    def test_061_widget_field_critical_threshold(self):
        self.assertIn("critical_threshold", self.env["clinic.dashboard.widget"]._fields)

    def test_062_widget_field_help_text(self):
        self.assertIn("help_text", self.env["clinic.dashboard.widget"]._fields)

    def test_063_widget_field_active(self):
        self.assertIn("active", self.env["clinic.dashboard.widget"]._fields)

    def test_064_widget_method_alert_level(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.widget"], "_alert_level"))

    def test_065_widget_method_empty_dashboard_card(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.widget"], "_empty_dashboard_card"))

    def test_066_widget_method_latest_report_run(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.widget"], "_latest_report_run"))

    def test_067_widget_method_action_open_definition(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.widget"], "action_open_definition"))

    def test_068_widget_method_action_open_latest_report(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.widget"], "action_open_latest_report"))

    def test_069_widget_method_action_open_latest_metric(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.widget"], "action_open_latest_metric"))

    def test_070_snapshot_field_name(self):
        self.assertIn("name", self.env["clinic.dashboard.snapshot"]._fields)

    def test_071_snapshot_field_board_id(self):
        self.assertIn("board_id", self.env["clinic.dashboard.snapshot"]._fields)

    def test_072_snapshot_field_dashboard_type(self):
        self.assertIn("dashboard_type", self.env["clinic.dashboard.snapshot"]._fields)

    def test_073_snapshot_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.dashboard.snapshot"]._fields)

    def test_074_snapshot_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.dashboard.snapshot"]._fields)

    def test_075_snapshot_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.dashboard.snapshot"]._fields)

    def test_076_snapshot_field_date_from(self):
        self.assertIn("date_from", self.env["clinic.dashboard.snapshot"]._fields)

    def test_077_snapshot_field_date_to(self):
        self.assertIn("date_to", self.env["clinic.dashboard.snapshot"]._fields)

    def test_078_snapshot_field_state(self):
        self.assertIn("state", self.env["clinic.dashboard.snapshot"]._fields)

    def test_079_snapshot_field_generated_at(self):
        self.assertIn("generated_at", self.env["clinic.dashboard.snapshot"]._fields)

    def test_080_snapshot_field_generated_by_id(self):
        self.assertIn("generated_by_id", self.env["clinic.dashboard.snapshot"]._fields)

    def test_081_snapshot_field_error_message(self):
        self.assertIn("error_message", self.env["clinic.dashboard.snapshot"]._fields)

    def test_082_snapshot_field_line_ids(self):
        self.assertIn("line_ids", self.env["clinic.dashboard.snapshot"]._fields)

    def test_083_snapshot_field_line_count(self):
        self.assertIn("line_count", self.env["clinic.dashboard.snapshot"]._fields)

    def test_084_snapshot_field_critical_count(self):
        self.assertIn("critical_count", self.env["clinic.dashboard.snapshot"]._fields)

    def test_085_snapshot_field_warning_count(self):
        self.assertIn("warning_count", self.env["clinic.dashboard.snapshot"]._fields)

    def test_086_snapshot_field_no_data_count(self):
        self.assertIn("no_data_count", self.env["clinic.dashboard.snapshot"]._fields)

    def test_087_snapshot_field_available_count(self):
        self.assertIn("available_count", self.env["clinic.dashboard.snapshot"]._fields)

    def test_088_snapshot_field_report_run_count(self):
        self.assertIn("report_run_count", self.env["clinic.dashboard.snapshot"]._fields)

    def test_089_snapshot_method_line_vals_unsupported(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "_line_vals_unsupported"))

    def test_090_snapshot_method_line_vals_no_data(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "_line_vals_no_data"))

    def test_091_snapshot_method_line_vals_metric(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "_line_vals_metric"))

    def test_092_snapshot_method_action_open_board(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "action_open_board"))

    def test_093_snapshot_method_action_open_live_dashboard(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "action_open_live_dashboard"))

    def test_094_snapshot_method_action_view_lines(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "action_view_lines"))

    def test_095_snapshot_method_action_view_report_runs(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "action_view_report_runs"))

    def test_096_snapshot_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "action_archive"))

    def test_097_snapshot_method_cron_archive_old_snapshots(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot"], "_cron_archive_old_snapshots"))

    def test_098_line_field_snapshot_id(self):
        self.assertIn("snapshot_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_099_line_field_board_id(self):
        self.assertIn("board_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_100_line_field_widget_id(self):
        self.assertIn("widget_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_101_line_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_102_line_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_103_line_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_104_line_field_sequence(self):
        self.assertIn("sequence", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_105_line_field_name(self):
        self.assertIn("name", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_106_line_field_metric_code(self):
        self.assertIn("metric_code", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_107_line_field_metric_type(self):
        self.assertIn("metric_type", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_108_line_field_icon(self):
        self.assertIn("icon", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_109_line_field_display_style(self):
        self.assertIn("display_style", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_110_line_field_column_span(self):
        self.assertIn("column_span", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_111_line_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_112_line_field_report_run_id(self):
        self.assertIn("report_run_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_113_line_field_metric_id(self):
        self.assertIn("metric_id", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_114_line_field_value(self):
        self.assertIn("value", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_115_line_field_display_value(self):
        self.assertIn("display_value", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_116_line_field_previous_value(self):
        self.assertIn("previous_value", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_117_line_field_has_trend(self):
        self.assertIn("has_trend", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_118_line_field_trend_percent(self):
        self.assertIn("trend_percent", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_119_line_field_trend_direction(self):
        self.assertIn("trend_direction", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_120_line_field_has_target(self):
        self.assertIn("has_target", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_121_line_field_target_value(self):
        self.assertIn("target_value", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_122_line_field_target_progress(self):
        self.assertIn("target_progress", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_123_line_field_status(self):
        self.assertIn("status", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_124_line_field_status_label(self):
        self.assertIn("status_label", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_125_line_field_note(self):
        self.assertIn("note", self.env["clinic.dashboard.snapshot.line"]._fields)

    def test_126_line_method_action_open_report_run(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot.line"], "action_open_report_run"))

    def test_127_line_method_action_open_metric(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot.line"], "action_open_metric"))

    def test_128_line_method_action_open_definition(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot.line"], "action_open_definition"))

    def test_129_line_method_as_dashboard_card(self):
        self.assertTrue(hasattr(self.env["clinic.dashboard.snapshot.line"], "_as_dashboard_card"))

    def test_130_upstream_model_clinic_report_definition(self):
        self.assertIn("clinic.report.definition", self.env.registry)

    def test_131_upstream_model_clinic_report_run(self):
        self.assertIn("clinic.report.run", self.env.registry)

    def test_132_upstream_model_clinic_report_metric(self):
        self.assertIn("clinic.report.metric", self.env.registry)

    def test_133_upstream_model_clinic_report_detail(self):
        self.assertIn("clinic.report.detail", self.env.registry)

    def test_134_report_definition_field_report_key(self):
        self.assertIn("report_key", self.env["clinic.report.definition"]._fields)

    def test_135_report_definition_field_state(self):
        self.assertIn("state", self.env["clinic.report.definition"]._fields)

    def test_136_report_definition_field_allow_branch_filter(self):
        self.assertIn("allow_branch_filter", self.env["clinic.report.definition"]._fields)

    def test_137_report_definition_field_default_detail_limit(self):
        self.assertIn("default_detail_limit", self.env["clinic.report.definition"]._fields)

    def test_138_report_run_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.report.run"]._fields)

    def test_139_report_run_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.report.run"]._fields)

    def test_140_report_run_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.report.run"]._fields)

    def test_141_report_run_field_date_from(self):
        self.assertIn("date_from", self.env["clinic.report.run"]._fields)

    def test_142_report_run_field_date_to(self):
        self.assertIn("date_to", self.env["clinic.report.run"]._fields)

    def test_143_report_run_field_state(self):
        self.assertIn("state", self.env["clinic.report.run"]._fields)

    def test_144_report_run_field_generated_at(self):
        self.assertIn("generated_at", self.env["clinic.report.run"]._fields)

    def test_145_report_run_field_finalized_at(self):
        self.assertIn("finalized_at", self.env["clinic.report.run"]._fields)

    def test_146_report_run_field_metric_ids(self):
        self.assertIn("metric_ids", self.env["clinic.report.run"]._fields)

    def test_147_report_metric_field_run_id(self):
        self.assertIn("run_id", self.env["clinic.report.metric"]._fields)

    def test_148_report_metric_field_definition_id(self):
        self.assertIn("definition_id", self.env["clinic.report.metric"]._fields)

    def test_149_report_metric_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.report.metric"]._fields)

    def test_150_report_metric_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.report.metric"]._fields)

    def test_151_report_metric_field_currency_id(self):
        self.assertIn("currency_id", self.env["clinic.report.metric"]._fields)

    def test_152_report_metric_field_code(self):
        self.assertIn("code", self.env["clinic.report.metric"]._fields)

    def test_153_report_metric_field_metric_type(self):
        self.assertIn("metric_type", self.env["clinic.report.metric"]._fields)

    def test_154_report_metric_field_value(self):
        self.assertIn("value", self.env["clinic.report.metric"]._fields)

    def test_155_report_metric_field_display_value(self):
        self.assertIn("display_value", self.env["clinic.report.metric"]._fields)

    def test_156_report_metric_field_note(self):
        self.assertIn("note", self.env["clinic.report.metric"]._fields)

    def test_157_report_run_generate_method(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_generate"))

    def test_158_company_field_clinic_dashboard_default_board_id(self):
        self.assertIn("clinic_dashboard_default_board_id", self.env["res.company"]._fields)

    def test_159_company_field_clinic_dashboard_snapshot_retention_days(self):
        self.assertIn("clinic_dashboard_snapshot_retention_days", self.env["res.company"]._fields)

    def test_160_company_field_clinic_dashboard_board_ids(self):
        self.assertIn("clinic_dashboard_board_ids", self.env["res.company"]._fields)

    def test_161_company_field_clinic_dashboard_board_count(self):
        self.assertIn("clinic_dashboard_board_count", self.env["res.company"]._fields)

    def test_162_branch_field_dashboard_snapshot_ids(self):
        self.assertIn("dashboard_snapshot_ids", self.env["clinic.branch"]._fields)

    def test_163_branch_field_dashboard_snapshot_count(self):
        self.assertIn("dashboard_snapshot_count", self.env["clinic.branch"]._fields)

    def test_164_report_run_dashboard_field_dashboard_line_ids(self):
        self.assertIn("dashboard_line_ids", self.env["clinic.report.run"]._fields)

    def test_165_report_run_dashboard_field_dashboard_line_count(self):
        self.assertIn("dashboard_line_count", self.env["clinic.report.run"]._fields)

    def test_166_integration_method_res_company_action_ensure_clinic_dashboards(self):
        self.assertTrue(hasattr(self.env["res.company"], "action_ensure_clinic_dashboards"))

    def test_167_integration_method_res_company_action_open_clinic_dashboard_boards(self):
        self.assertTrue(hasattr(self.env["res.company"], "action_open_clinic_dashboard_boards"))

    def test_168_integration_method_clinic_branch_action_open_dashboard_snapshots(self):
        self.assertTrue(hasattr(self.env["clinic.branch"], "action_open_dashboard_snapshots"))

    def test_169_integration_method_clinic_report_run_action_open_dashboard_lines(self):
        self.assertTrue(hasattr(self.env["clinic.report.run"], "action_open_dashboard_lines"))

    def test_170_default_board_executive(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        board = self.env["clinic.dashboard.board"].search([
            ("company_id", "=", self.env.company.id),
            ("code", "=", "EXECUTIVE"),
        ], limit=1)
        self.assertTrue(board)
        self.assertEqual(board.state, "active")

    def test_171_default_board_financial(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        board = self.env["clinic.dashboard.board"].search([
            ("company_id", "=", self.env.company.id),
            ("code", "=", "FINANCIAL"),
        ], limit=1)
        self.assertTrue(board)
        self.assertEqual(board.state, "active")

    def test_172_default_board_operations(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        board = self.env["clinic.dashboard.board"].search([
            ("company_id", "=", self.env.company.id),
            ("code", "=", "OPERATIONS"),
        ], limit=1)
        self.assertTrue(board)
        self.assertEqual(board.state, "active")

    def test_173_default_board_clinical(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        board = self.env["clinic.dashboard.board"].search([
            ("company_id", "=", self.env.company.id),
            ("code", "=", "CLINICAL"),
        ], limit=1)
        self.assertTrue(board)
        self.assertEqual(board.state, "active")

    def test_174_default_board_room(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        board = self.env["clinic.dashboard.board"].search([
            ("company_id", "=", self.env.company.id),
            ("code", "=", "ROOM"),
        ], limit=1)
        self.assertTrue(board)
        self.assertEqual(board.state, "active")

    def test_175_default_board_experience(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        board = self.env["clinic.dashboard.board"].search([
            ("company_id", "=", self.env.company.id),
            ("code", "=", "EXPERIENCE"),
        ], limit=1)
        self.assertTrue(board)
        self.assertEqual(board.state, "active")

    def test_176_default_board_seed_is_idempotent(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        count_before = Board.search_count([("company_id", "=", self.env.company.id)])
        Board._ensure_default_boards(self.env.company)
        count_after = Board.search_count([("company_id", "=", self.env.company.id)])
        self.assertEqual(count_before, count_after)

    def test_177_default_widget_mapping_count(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        boards = Board.search([
            ("company_id", "=", self.env.company.id),
            ("code", "in", ["EXECUTIVE","FINANCIAL","OPERATIONS","CLINICAL","ROOM","EXPERIENCE"]),
        ])
        self.assertEqual(sum(len(board.widget_ids) for board in boards), 50)

    def test_178_metric_code_seed_gross_revenue(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "GROSS_REVENUE"),
            ], limit=1)
        )

    def test_179_metric_code_seed_collection_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "COLLECTION_RATE"),
            ], limit=1)
        )

    def test_180_metric_code_seed_ar_overdue_amount(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "AR_OVERDUE_AMOUNT"),
            ], limit=1)
        )

    def test_181_metric_code_seed_net_cashflow(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "NET_CASHFLOW"),
            ], limit=1)
        )

    def test_182_metric_code_seed_booking_completion_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "BOOKING_COMPLETION_RATE"),
            ], limit=1)
        )

    def test_183_metric_code_seed_queue_avg_wait(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "QUEUE_AVG_WAIT"),
            ], limit=1)
        )

    def test_184_metric_code_seed_encounter_completion_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ENCOUNTER_COMPLETION_RATE"),
            ], limit=1)
        )

    def test_185_metric_code_seed_feedback_nps(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_NPS"),
            ], limit=1)
        )

    def test_186_metric_code_seed_collected_amount(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "COLLECTED_AMOUNT"),
            ], limit=1)
        )

    def test_187_metric_code_seed_outstanding_amount(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "OUTSTANDING_AMOUNT"),
            ], limit=1)
        )

    def test_188_metric_code_seed_ap_residual(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "AP_RESIDUAL"),
            ], limit=1)
        )

    def test_189_metric_code_seed_net_ppn(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "NET_PPN"),
            ], limit=1)
        )

    def test_190_metric_code_seed_auth_approval_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "AUTH_APPROVAL_RATE"),
            ], limit=1)
        )

    def test_191_metric_code_seed_booking_count(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "BOOKING_COUNT"),
            ], limit=1)
        )

    def test_192_metric_code_seed_booking_cancel_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "BOOKING_CANCEL_RATE"),
            ], limit=1)
        )

    def test_193_metric_code_seed_queue_sla_breach_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "QUEUE_SLA_BREACH_RATE"),
            ], limit=1)
        )

    def test_194_metric_code_seed_room_avg_occupancy(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ROOM_AVG_OCCUPANCY"),
            ], limit=1)
        )

    def test_195_metric_code_seed_inventory_total_qty(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "INVENTORY_TOTAL_QTY"),
            ], limit=1)
        )

    def test_196_metric_code_seed_membership_active(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "MEMBERSHIP_ACTIVE"),
            ], limit=1)
        )

    def test_197_metric_code_seed_wallet_net(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "WALLET_NET"),
            ], limit=1)
        )

    def test_198_metric_code_seed_encounter_count(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ENCOUNTER_COUNT"),
            ], limit=1)
        )

    def test_199_metric_code_seed_procedure_completion_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "PROCEDURE_COMPLETION_RATE"),
            ], limit=1)
        )

    def test_200_metric_code_seed_triage_sla_breach_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "TRIAGE_SLA_BREACH_RATE"),
            ], limit=1)
        )

    def test_201_metric_code_seed_triage_abnormal_vitals(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "TRIAGE_ABNORMAL_VITALS"),
            ], limit=1)
        )

    def test_202_metric_code_seed_ae_serious(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "AE_SERIOUS"),
            ], limit=1)
        )

    def test_203_metric_code_seed_postcare_completion_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "POSTCARE_COMPLETION_RATE"),
            ], limit=1)
        )

    def test_204_metric_code_seed_postcare_red_flags(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "POSTCARE_RED_FLAGS"),
            ], limit=1)
        )

    def test_205_metric_code_seed_room_assignments(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ROOM_ASSIGNMENTS"),
            ], limit=1)
        )

    def test_206_metric_code_seed_rooms_used(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ROOMS_USED"),
            ], limit=1)
        )

    def test_207_metric_code_seed_room_active(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ROOM_ACTIVE"),
            ], limit=1)
        )

    def test_208_metric_code_seed_room_total_occupancy(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ROOM_TOTAL_OCCUPANCY"),
            ], limit=1)
        )

    def test_209_metric_code_seed_room_avg_service(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "ROOM_AVG_SERVICE"),
            ], limit=1)
        )

    def test_210_metric_code_seed_feedback_count(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_COUNT"),
            ], limit=1)
        )

    def test_211_metric_code_seed_feedback_avg_rating(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_AVG_RATING"),
            ], limit=1)
        )

    def test_212_metric_code_seed_feedback_promoters(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_PROMOTERS"),
            ], limit=1)
        )

    def test_213_metric_code_seed_feedback_detractors(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_DETRACTORS"),
            ], limit=1)
        )

    def test_214_metric_code_seed_feedback_complaints(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_COMPLAINTS"),
            ], limit=1)
        )

    def test_215_metric_code_seed_feedback_escalation_rate(self):
        self.env["clinic.dashboard.board"]._ensure_default_boards(self.env.company)
        self.assertTrue(
            self.env["clinic.dashboard.widget"].search([
                ("company_id", "=", self.env.company.id),
                ("metric_code", "=", "FEEDBACK_ESCALATION_RATE"),
            ], limit=1)
        )

    def test_216_group_group_dashboard_user(self):
        self.assertTrue(self.env.ref("clinic_dashboard.group_dashboard_user"))

    def test_217_group_group_dashboard_analyst(self):
        self.assertTrue(self.env.ref("clinic_dashboard.group_dashboard_analyst"))

    def test_218_group_group_dashboard_manager(self):
        self.assertTrue(self.env.ref("clinic_dashboard.group_dashboard_manager"))

    def test_219_group_analyst_implies_user(self):
        user = self.env.ref("clinic_dashboard.group_dashboard_user")
        analyst = self.env.ref("clinic_dashboard.group_dashboard_analyst")
        self.assertIn(user, analyst.implied_ids)

    def test_220_group_manager_implies_analyst(self):
        analyst = self.env.ref("clinic_dashboard.group_dashboard_analyst")
        manager = self.env.ref("clinic_dashboard.group_dashboard_manager")
        self.assertIn(analyst, manager.implied_ids)

    def test_221_dashboard_user_implies_reports_user(self):
        reports_user = self.env.ref("clinic_reports.group_reports_user")
        dashboard_user = self.env.ref("clinic_dashboard.group_dashboard_user")
        self.assertIn(reports_user, dashboard_user.implied_ids)

    def test_222_dashboard_analyst_implies_reports_analyst(self):
        reports_analyst = self.env.ref("clinic_reports.group_reports_analyst")
        dashboard_analyst = self.env.ref("clinic_dashboard.group_dashboard_analyst")
        self.assertIn(reports_analyst, dashboard_analyst.implied_ids)

    def test_223_dashboard_manager_implies_reports_manager(self):
        reports_manager = self.env.ref("clinic_reports.group_reports_manager")
        dashboard_manager = self.env.ref("clinic_dashboard.group_dashboard_manager")
        self.assertIn(reports_manager, dashboard_manager.implied_ids)

    def test_224_view_clinic_dashboard_board_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.board"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_225_view_clinic_dashboard_board_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.board"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_226_view_clinic_dashboard_board_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.board"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_227_view_clinic_dashboard_widget_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.widget"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_228_view_clinic_dashboard_widget_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.widget"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_229_view_clinic_dashboard_widget_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.widget"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_230_view_clinic_dashboard_snapshot_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.snapshot"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_231_view_clinic_dashboard_snapshot_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.snapshot"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_232_view_clinic_dashboard_snapshot_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.snapshot"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_233_view_clinic_dashboard_snapshot_line_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.snapshot.line"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_234_view_clinic_dashboard_snapshot_line_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.snapshot.line"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_235_view_clinic_dashboard_snapshot_line_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.dashboard.snapshot.line"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_236_xmlid_view_dashboard_snapshot_kanban(self):
        self.assertTrue(self.env.ref("clinic_dashboard.view_dashboard_snapshot_kanban"))

    def test_237_xmlid_view_dashboard_snapshot_line_pivot(self):
        self.assertTrue(self.env.ref("clinic_dashboard.view_dashboard_snapshot_line_pivot"))

    def test_238_xmlid_view_dashboard_snapshot_line_graph(self):
        self.assertTrue(self.env.ref("clinic_dashboard.view_dashboard_snapshot_line_graph"))

    def test_239_xmlid_action_live_dashboard(self):
        self.assertTrue(self.env.ref("clinic_dashboard.action_live_dashboard"))

    def test_240_xmlid_action_dashboard_board(self):
        self.assertTrue(self.env.ref("clinic_dashboard.action_dashboard_board"))

    def test_241_xmlid_action_dashboard_snapshot(self):
        self.assertTrue(self.env.ref("clinic_dashboard.action_dashboard_snapshot"))

    def test_242_xmlid_action_dashboard_snapshot_line(self):
        self.assertTrue(self.env.ref("clinic_dashboard.action_dashboard_snapshot_line"))

    def test_243_xmlid_action_dashboard_settings(self):
        self.assertTrue(self.env.ref("clinic_dashboard.action_dashboard_settings"))

    def test_244_xmlid_cron_refresh_due_dashboards(self):
        self.assertTrue(self.env.ref("clinic_dashboard.cron_refresh_due_dashboards"))

    def test_245_xmlid_cron_archive_dashboard_snapshots(self):
        self.assertTrue(self.env.ref("clinic_dashboard.cron_archive_dashboard_snapshots"))

    def test_246_xmlid_seq_dashboard_snapshot(self):
        self.assertTrue(self.env.ref("clinic_dashboard.seq_dashboard_snapshot"))

    def test_247_search_architecture_odoo19(self):
        xmlids = (
            "clinic_dashboard.view_dashboard_board_search",
            "clinic_dashboard.view_dashboard_widget_search",
            "clinic_dashboard.view_dashboard_snapshot_search",
            "clinic_dashboard.view_dashboard_snapshot_line_search",
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

    def test_248_period_todaysay(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        board = Board.search([("company_id", "=", self.env.company.id)], limit=1)
        start, end = board._resolve_period("today")
        self.assertTrue(start)
        self.assertTrue(end)
        self.assertLessEqual(start, end)

    def test_249_period_7days(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        board = Board.search([("company_id", "=", self.env.company.id)], limit=1)
        start, end = board._resolve_period("7d")
        self.assertTrue(start)
        self.assertTrue(end)
        self.assertLessEqual(start, end)

    def test_250_period_30days(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        board = Board.search([("company_id", "=", self.env.company.id)], limit=1)
        start, end = board._resolve_period("30d")
        self.assertTrue(start)
        self.assertTrue(end)
        self.assertLessEqual(start, end)

    def test_251_period_90days(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        board = Board.search([("company_id", "=", self.env.company.id)], limit=1)
        start, end = board._resolve_period("90d")
        self.assertTrue(start)
        self.assertTrue(end)
        self.assertLessEqual(start, end)

    def test_252_period_month(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        board = Board.search([("company_id", "=", self.env.company.id)], limit=1)
        start, end = board._resolve_period("month")
        self.assertTrue(start)
        self.assertTrue(end)
        self.assertLessEqual(start, end)

    def test_253_period_ytdays(self):
        Board = self.env["clinic.dashboard.board"]
        Board._ensure_default_boards(self.env.company)
        board = Board.search([("company_id", "=", self.env.company.id)], limit=1)
        start, end = board._resolve_period("ytd")
        self.assertTrue(start)
        self.assertTrue(end)
        self.assertLessEqual(start, end)

    def test_254_client_action_tag(self):
        action = self.env.ref("clinic_dashboard.action_live_dashboard")
        self.assertEqual(action.tag, "clinic_dashboard.main")

    def test_255_settings_field_clinic_dashboard_default_board_id(self):
        self.assertIn("clinic_dashboard_default_board_id", self.env["res.config.settings"]._fields)

    def test_256_settings_field_clinic_dashboard_snapshot_retention_days(self):
        self.assertIn("clinic_dashboard_snapshot_retention_days", self.env["res.config.settings"]._fields)

