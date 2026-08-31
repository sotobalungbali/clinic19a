from pathlib import Path
import ast
import csv
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class TestClinicReferralSourceContracts(unittest.TestCase):

    def test_manifest_identity(self):
        data = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        self.assertEqual(data["version"], "19.0.2.0.6")
        self.assertIn("clinic_booking", data["depends"])
        self.assertIn("clinic_audit", data["depends"])
        self.assertNotIn("clinic_treatment_session", data["depends"])
        self.assertNotIn("clinic_membership", data["depends"])
        self.assertNotIn("clinic_analytics", data["depends"])

    def test_historical_models_preserved(self):
        source = "\n".join(
            path.read_text() for path in (ROOT / "models").glob("*.py")
        )
        for model in (
            "clinic.referral",
            "clinic.referral.program",
            "clinic.referral.source",
        ):
            self.assertIn(f'_name = "{model}"', source)

    def test_legacy_name_get_api_is_preserved(self):
        runtime = "\n".join(
            path.read_text()
            for path in (ROOT / "models").glob("*.py")
        )
        self.assertGreaterEqual(runtime.count("def name_get(self):"), 3)

    def test_legacy_sql_constraints_absent(self):
        for path in ROOT.rglob("*.py"):
            if "tests" in path.parts or "tools" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    self.assertFalse(
                        isinstance(target, ast.Name)
                        and target.id == "_sql_constraints",
                        path,
                    )

    def test_source_constraint_converted_to_odoo19(self):
        source = (ROOT / "models/referral_source.py").read_text()
        self.assertIn("models.Constraint(", source)
        self.assertIn("UNIQUE(code, company_id)", source)

    def test_real_booking_model_contract(self):
        referral = (ROOT / "models/referral.py").read_text()
        booking = (ROOT / "models/booking_bridge.py").read_text()
        self.assertNotIn('"clinic.booking"', referral)
        self.assertIn('_inherit = "booking.booking"', booking)
        self.assertIn("referral_id = fields.Many2one(", booking)

    def test_optional_patient_branch_views_are_runtime_bridges(self):
        integration = (
            ROOT / "views/referral_integration_views.xml"
        ).read_text()

        self.assertNotIn(
            'id="view_patient_form_referral"',
            integration,
        )
        self.assertNotIn(
            'id="view_branch_form_referral"',
            integration,
        )

        bridge = (ROOT / "models/ui_bridge.py").read_text()
        self.assertIn(
            "def _find_usable_form_parent(",
            bridge,
        )
        self.assertIn(
            'raise_if_not_found=False',
            bridge,
        )
        self.assertIn(
            '("mode", "=", "primary")',
            bridge,
        )
        self.assertIn(
            "def _upsert_optional_form_bridge(",
            bridge,
        )
        self.assertIn(
            "with self.env.cr.savepoint():",
            bridge,
        )
        self.assertIn(
            '"view_patient_form_referral"',
            bridge,
        )
        self.assertIn(
            '"view_branch_form_referral"',
            bridge,
        )

    def test_runtime_ui_bridge_is_loaded_on_upgrade(self):
        manifest = ast.literal_eval(
            (ROOT / "__manifest__.py").read_text()
        )
        self.assertIn(
            "data/optional_ui_bridge.xml",
            manifest["data"],
        )
        self.assertGreater(
            manifest["data"].index("data/optional_ui_bridge.xml"),
            manifest["data"].index("views/referral_menus.xml"),
        )

        xml = (
            ROOT / "data/optional_ui_bridge.xml"
        ).read_text()
        self.assertIn(
            '_ensure_optional_cross_addon_ui',
            xml,
        )

    def test_referral_root_menu_is_intrinsically_valid(self):
        root = ET.parse(
            ROOT / "views/referral_menus.xml"
        ).getroot()
        menu = root.find(
            "./menuitem[@id='menu_referral_root']"
        )
        self.assertIsNotNone(menu)
        self.assertIsNone(menu.attrib.get("parent"))
        self.assertEqual(
            menu.attrib.get("groups"),
            "clinic_referral.group_referral_user",
        )

        bridge = (ROOT / "models/ui_bridge.py").read_text()
        self.assertIn(
            "def _ensure_referral_menu_parent(",
            bridge,
        )
        self.assertIn(
            '"clinic_patient.menu_root"',
            bridge,
        )

    def test_odoo19_ir_ui_menu_does_not_use_groups_id(self):
        root = ET.parse(
            ROOT / "views/referral_menus.xml"
        ).getroot()

        offenders = []
        for record in root.findall("record"):
            if record.attrib.get("model") != "ir.ui.menu":
                continue
            for field in record.findall("field"):
                if field.attrib.get("name") == "groups_id":
                    offenders.append(record.attrib.get("id"))

        self.assertEqual(offenders, [])

    def test_odoo19_inherited_views_do_not_select_by_string(self):
        offenders = []
        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()
            for xpath in root.iter("xpath"):
                expr = xpath.attrib.get("expr", "")
                if "@string" in expr:
                    offenders.append(
                        f"{path.name}: {expr}"
                    )

        self.assertEqual(offenders, [])

        integration = (
            ROOT / "views/referral_integration_views.xml"
        ).read_text()
        self.assertIn(
            "//form//field[@name='patient_id']",
            integration,
        )

    def test_res_company_referral_settings_are_bootstrap_safe(self):
        source = (ROOT / "models/res_company.py").read_text()
        tree = ast.parse(source)

        expected = {
            "clinic_referral_default_valid_days",
            "clinic_referral_require_source",
            "clinic_referral_require_program_for_reward",
        }
        seen = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue

            field_name = node.targets[0].id
            if field_name not in expected:
                continue

            kwargs = {
                keyword.arg: keyword.value
                for keyword in node.value.keywords
                if keyword.arg
            }
            self.assertIn("compute", kwargs, field_name)
            self.assertIn("inverse", kwargs, field_name)

            if "store" in kwargs:
                self.assertFalse(
                    ast.literal_eval(kwargs["store"]),
                    field_name,
                )

            seen.add(field_name)

        self.assertEqual(seen, expected)
        self.assertIn("ir.config_parameter", source)

    def test_bootstrap_safe_company_setting_migration_exists(self):
        migration = (
            ROOT
            / "migrations"
            / "19.0.2.0.1"
            / "pre-migrate-company-settings.py"
        )
        self.assertTrue(migration.exists())
        source = migration.read_text()
        self.assertIn("information_schema.columns", source)
        self.assertIn("ir_config_parameter", source)

    def test_time_dependent_fields_are_searchable_nonstored(self):
        referral = (ROOT / "models/referral.py").read_text()
        program = (ROOT / "models/referral_program.py").read_text()
        self.assertIn('search="_search_is_expired"', referral)
        self.assertIn('search="_search_is_current"', program)
        self.assertIn('search="_search_is_future"', program)
        self.assertIn('search="_search_is_past"', program)
        self.assertNotIn("store=True,\n        search=\"_search_is_expired\"", referral)

    def test_referral_workflow_repairs_are_explicit(self):
        referral = (ROOT / "models/referral.py").read_text()
        program = (ROOT / "models/referral_program.py").read_text()
        self.assertIn(
            '"draft": {"confirmed", "converted", "cancelled", "expired"}',
            referral,
        )
        self.assertIn('"cancelled": {"draft"}', referral)
        self.assertIn('"expired": {"draft"}', referral)
        self.assertIn('"paused": {"draft", "running", "closed", "archived"}', program)

    def test_sequences_and_security_are_loaded(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        self.assertIn("data/sequence_data.xml", manifest["data"])
        self.assertIn("security/clinic_referral_security.xml", manifest["data"])
        self.assertIn("security/ir.model.access.csv", manifest["data"])
        xml = (ROOT / "data/sequence_data.xml").read_text()
        for code in (
            "clinic.referral",
            "clinic.referral.program",
            "clinic.referral.source",
        ):
            self.assertIn(code, xml)

    def test_acl_covers_owned_models(self):
        with (ROOT / "security/ir.model.access.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        model_ids = {row["model_id:id"] for row in rows}
        self.assertTrue(
            {
                "model_clinic_referral",
                "model_clinic_referral_program",
                "model_clinic_referral_source",
            }.issubset(model_ids)
        )

    def test_branch_rules_exist(self):
        source = (ROOT / "security/clinic_referral_security.xml").read_text()
        self.assertIn("user.allowed_branch_ids.ids", source)
        self.assertIn("company_ids", source)
        self.assertIn("res.groups.privilege", source)

    def test_search_list_form_exist_for_owned_models(self):
        expected = {
            "clinic.referral",
            "clinic.referral.program",
            "clinic.referral.source",
        }
        found = {model: set() for model in expected}
        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()
            for record in root.findall("record"):
                if record.attrib.get("model") != "ir.ui.view":
                    continue
                model = record.find("./field[@name='model']")
                arch = record.find("./field[@name='arch']")
                if model is None or arch is None or not list(arch):
                    continue
                name = (model.text or "").strip()
                tag = list(arch)[0].tag
                if name in found and tag in {"search", "list", "form"}:
                    found[name].add(tag)
        for model in expected:
            self.assertEqual(found[model], {"search", "list", "form"}, model)

    def test_nested_row_button_contract(self):
        referral = (
            (ROOT / "models/referral.py").read_text()
            + (ROOT / "models/referral_navigation.py").read_text()
        )
        program_view = (ROOT / "views/referral_program_views.xml").read_text()
        source_view = (ROOT / "views/referral_source_views.xml").read_text()
        self.assertIn("def action_open_self(self):", referral)
        self.assertIn('name="action_open_self"', program_view)
        self.assertIn('name="action_open_self"', source_view)

    def test_settings_view_is_extension(self):
        root = ET.parse(ROOT / "views/res_config_settings_views.xml").getroot()
        record = root.find(
            ".//record[@id='res_config_settings_view_form_referral']"
        )
        inherit = record.find("field[@name='inherit_id']")
        mode = record.find("field[@name='mode']")
        self.assertEqual(
            inherit.attrib.get("ref"),
            "base.res_config_settings_view_form",
        )
        self.assertEqual((mode.text or "").strip(), "extension")

    def test_downstream_models_are_runtime_optional(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        self.assertNotIn("clinic_treatment_session", manifest["depends"])
        self.assertNotIn("clinic_membership", manifest["depends"])
        referral = (ROOT / "models/referral.py").read_text()
        self.assertIn('optional_model(self.env, "membership.contract")', referral)
        self.assertIn('"clinic.treatment.session.line"', referral)

    def test_digit_prefixed_backups_not_packaged(self):
        offenders = [
            path for path in ROOT.rglob("*")
            if path.is_file() and path.name[:1].isdigit()
        ]
        self.assertEqual(offenders, [])

    def test_historical_effective_date_workflow_is_additive(self):
        source = (ROOT / "models/referral.py").read_text()
        self.assertIn("def action_confirm(self, effective_datetime=None):", source)
        self.assertIn("def action_convert(self, effective_datetime=None):", source)
        self.assertIn("effective_datetime=None", source)
        self.assertIn("def action_cancel(self, effective_datetime=None):", source)
        self.assertIn("def action_mark_expired(self, as_of_date=None):", source)
        self.assertIn("fields.Datetime.now()", source)
        self.assertIn("fields.Date.context_today(self)", source)

    def test_mark_converted_forwards_effective_datetime(self):
        source = (ROOT / "models/referral.py").read_text()
        self.assertIn("def mark_converted(self, source_record=None, conversion_value=0.0, effective_datetime=None):", source)
        self.assertIn("referral.action_convert(effective_datetime=effective_datetime)", source)


if __name__ == "__main__":
    unittest.main()

