from pathlib import Path
import ast
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class TestClinicAnalyticsSourceContracts(unittest.TestCase):

    def test_manifest_identity_and_order(self):
        tree = ast.parse((ROOT / "__manifest__.py").read_text())
        manifest = ast.literal_eval(tree.body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.1")
        self.assertIn("clinic_audit", manifest["depends"])
        self.assertIn("clinic_integration_api", manifest["depends"])
        self.assertNotIn("clinic_analytics", manifest["depends"])

    def test_no_legacy_sql_constraints(self):
        for path in ROOT.rglob("*.py"):
            if "tests" in path.parts or "tools" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        self.assertFalse(
                            isinstance(target, ast.Name)
                            and target.id == "_sql_constraints",
                            path,
                        )

    def test_fixed_source_keys_are_explicit(self):
        source = (ROOT / "models/kpi.py").read_text()
        engine = (ROOT / "models/analytics_engine.py").read_text()
        expected = [
            "revenue_total",
            "revenue_paid",
            "booking_count",
            "booking_completion_rate",
            "booking_no_show_rate",
            "unique_patients",
            "repeat_patient_rate",
            "membership_active",
            "membership_renewal_rate",
            "wallet_balance",
            "feedback_nps",
            "feedback_avg_rating",
            "quality_score",
            "incident_count",
            "critical_incident_count",
            "marketing_reach",
            "marketing_delivery_rate",
        ]
        for key in expected:
            self.assertIn(f'("{key}",', source)
            self.assertIn(f"def _metric_{key}", engine)

    def test_no_arbitrary_rpc_surface(self):
        runtime = "\n".join(
            path.read_text()
            for path in (ROOT / "models").glob("*.py")
        )
        self.assertNotIn("request.params", runtime)
        self.assertNotIn("safe_eval", runtime)
        self.assertNotIn("eval(", runtime)

    def test_branch_security_is_backend_contract(self):
        security = (
            ROOT / "security/clinic_analytics_security.xml"
        ).read_text()
        scope = (ROOT / "models/scope_mixin.py").read_text()
        self.assertIn("user.allowed_branch_ids.ids", security)
        self.assertIn("Company-wide analytics require", scope)
        self.assertIn("_ensure_scope_authorized", scope)

    def test_snapshot_line_is_immutable(self):
        source = (ROOT / "models/snapshot_line.py").read_text()
        self.assertIn("Snapshot lines can only be created", source)
        self.assertIn("snapshot lines are immutable", source)

    def test_source_drilldown_uses_sudo_only_for_technical_lineage(self):
        snapshot_line = (ROOT / "models/snapshot_line.py").read_text()
        forecast_point = (ROOT / "models/forecast_point.py").read_text()
        self.assertIn("self.sudo().source_domain_json", snapshot_line)
        self.assertIn("self.sudo().source_domain_json", forecast_point)
        self.assertNotIn('self.env[self.source_model].sudo()', snapshot_line)
        self.assertNotIn('self.env[self.source_model].sudo()', forecast_point)

    def test_forecast_point_is_immutable(self):
        source = (ROOT / "models/forecast_point.py").read_text()
        self.assertIn("Forecast points can only be created", source)
        self.assertIn("Forecast points are immutable", source)

    def test_owner_workflows_mutate_generated_children_internally(self):
        snapshot = (ROOT / "models/snapshot.py").read_text()
        forecast = (ROOT / "models/forecast.py").read_text()
        self.assertIn("rec.line_ids.sudo().with_context(", snapshot)
        self.assertIn("Line.sudo().with_context(", snapshot)
        self.assertIn("rec.point_ids.sudo().with_context(", forecast)
        self.assertEqual(forecast.count("Point.sudo().with_context("), 2)
        acl = (ROOT / "security/ir.model.access.csv").read_text()
        self.assertIn(
            "access_analytics_snapshot_line_manager,"
            "clinic.analytics.snapshot.line manager,"
            "model_clinic_analytics_snapshot_line,"
            "clinic_analytics.group_analytics_manager,1,0,0,0",
            acl,
        )
        self.assertIn(
            "access_analytics_forecast_point_manager,"
            "clinic.analytics.forecast.point manager,"
            "model_clinic_analytics_forecast_point,"
            "clinic_analytics.group_analytics_manager,1,0,0,0",
            acl,
        )

    def test_forecast_methods_are_transparent(self):
        source = (ROOT / "models/forecasting_service.py").read_text()
        for method in ("naive", "moving_average", "linear_trend"):
            self.assertIn(f'method == "{method}"', source)

    def test_retention_does_not_persist_patient_ids(self):
        source = (ROOT / "models/cohort.py").read_text()
        self.assertNotIn("patient_ids = fields.", source)
        self.assertIn("cohort_size", source)
        self.assertIn("retention_90", source)

    def test_integration_events_are_opt_in(self):
        source = (ROOT / "models/integration_service.py").read_text()
        self.assertIn(
            "clinic.analytics.publish_integration_events",
            source,
        )
        self.assertIn('"false"', source)

    def test_reports_dashboard_bridges_exist(self):
        source = (ROOT / "models/integration_bridge.py").read_text()
        self.assertIn('_inherit = "clinic.dashboard.board"', source)
        self.assertIn('_inherit = "clinic.report.definition"', source)
        self.assertIn("action_view_analytics_forecasts", source)
        self.assertIn("action_view_analytics_kpis", source)

    def test_search_views_exist_for_all_persistent_models(self):
        expected = {
            "clinic.analytics.kpi",
            "clinic.analytics.snapshot",
            "clinic.analytics.snapshot.line",
            "clinic.analytics.forecast",
            "clinic.analytics.forecast.point",
            "clinic.analytics.cohort",
            "clinic.analytics.insight",
            "clinic.analytics.schedule",
        }
        found = set()
        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()
            for record in root.findall("record"):
                if record.attrib.get("model") != "ir.ui.view":
                    continue
                model = record.find("./field[@name='model']")
                arch = record.find("./field[@name='arch']")
                if model is None or arch is None:
                    continue
                if any(
                    child.tag == "search"
                    for child in list(arch)
                ):
                    found.add((model.text or "").strip())
        self.assertTrue(expected.issubset(found), expected - found)

    def test_object_buttons_have_methods(self):
        runtime = "\n".join(
            path.read_text()
            for path in (ROOT / "models").glob("*.py")
        )
        buttons = set()
        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()
            for button in root.iter("button"):
                if button.attrib.get("type") == "object":
                    buttons.add(button.attrib.get("name"))
        for button in buttons:
            self.assertIn(f"def {button}(", runtime, button)

    def test_cron_sudo_can_execute_analytics_workers(self):
        snapshot = (ROOT / "models/snapshot.py").read_text()
        forecast = (ROOT / "models/forecast.py").read_text()
        cohort = (ROOT / "models/cohort.py").read_text()
        self.assertIn("if self.env.su:", snapshot)
        self.assertIn("if self.env.su:", forecast)
        self.assertIn("if not self.env.su and not self.env.user.has_group(", cohort)

    def test_cron_method_exists(self):
        source = (ROOT / "models/schedule.py").read_text()
        cron = (ROOT / "data/cron_data.xml").read_text()
        self.assertIn("def _cron_run_due", source)
        self.assertIn("model._cron_run_due()", cron)

    def test_settings_use_config_parameters(self):
        source = (ROOT / "models/res_config_settings.py").read_text()
        self.assertIn("config_parameter=", source)
        self.assertIn(
            "clinic.analytics.auto_generate_insights",
            source,
        )

    def test_digit_prefixed_backups_are_absent(self):
        offenders = [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and path.name[:1].isdigit()
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
