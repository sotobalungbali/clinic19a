from pathlib import Path
import ast
import csv
import re
import unittest
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def model_inventory():
    """Return direct fields/methods declared across this addon's Python files."""
    fields_by_model = {}
    methods_by_model = {}

    for path in (ROOT / "models").rglob("*.py"):
        if path.name[:1].isdigit():
            continue

        tree = ast.parse(path.read_text())

        for cls in (
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
        ):
            technical_models = []

            for statement in cls.body:
                if not isinstance(statement, ast.Assign):
                    continue

                for target in statement.targets:
                    if not isinstance(target, ast.Name):
                        continue

                    if target.id in {"_name", "_inherit"}:
                        try:
                            value = ast.literal_eval(statement.value)
                        except Exception:
                            continue

                        if isinstance(value, str):
                            technical_models.append(value)

            technical_models = list(dict.fromkeys(technical_models))

            for model_name in technical_models:
                fields_by_model.setdefault(model_name, set())
                methods_by_model.setdefault(model_name, set())

                for statement in cls.body:
                    if isinstance(
                        statement,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        methods_by_model[model_name].add(statement.name)

                    if not (
                        isinstance(statement, ast.Assign)
                        and len(statement.targets) == 1
                        and isinstance(statement.targets[0], ast.Name)
                        and isinstance(statement.value, ast.Call)
                        and isinstance(statement.value.func, ast.Attribute)
                        and isinstance(statement.value.func.value, ast.Name)
                        and statement.value.func.value.id == "fields"
                    ):
                        continue

                    fields_by_model[model_name].add(
                        statement.targets[0].id
                    )

    return fields_by_model, methods_by_model


class TestClinicTreatmentSessionSourceContracts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fields_by_model, cls.methods_by_model = model_inventory()

    def test_manifest_identity_and_dependency_direction(self):
        manifest = ast.literal_eval(
            ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value
        )
        self.assertEqual(manifest["version"], "19.0.2.0.2")

        required = {
            "clinic_base",
            "clinic_audit",
            "clinic_branch",
            "clinic_patient",
            "clinic_doctor",
            "clinic_booking",
            "clinic_inventory",
            "clinic_encounter",
            "clinic_package",
            "clinic_referral",
            "clinic_billing",
        }
        self.assertTrue(required.issubset(set(manifest["depends"])))

        forbidden_downstream = {
            "clinic_membership",
            "clinic_ar",
            "clinic_wallet",
            "clinic_finance",
            "clinic_accounting",
            "clinic_reports",
            "clinic_dashboard",
            "clinic_analytics",
        }
        self.assertFalse(
            forbidden_downstream.intersection(manifest["depends"])
        )

    def test_odoo19_create_overrides_are_multi_create_safe(self):
        offenders = []

        for path in (ROOT / "models").rglob("*.py"):
            tree = ast.parse(path.read_text())

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if node.name != "create":
                    continue

                decorators = []
                for decorator in node.decorator_list:
                    if (
                        isinstance(decorator, ast.Attribute)
                        and isinstance(decorator.value, ast.Name)
                    ):
                        decorators.append(
                            f"{decorator.value.id}.{decorator.attr}"
                        )

                # Any create() implementation that directly treats its
                # argument as a dict must use model_create_multi and iterate.
                argument_name = (
                    node.args.args[-1].arg
                    if node.args.args
                    else ""
                )
                direct_dict_calls = []

                for subnode in ast.walk(node):
                    if not (
                        isinstance(subnode, ast.Call)
                        and isinstance(subnode.func, ast.Attribute)
                        and isinstance(subnode.func.value, ast.Name)
                        and subnode.func.value.id == argument_name
                        and subnode.func.attr
                        in {
                            "get",
                            "setdefault",
                            "update",
                            "pop",
                            "items",
                            "keys",
                            "values",
                        }
                    ):
                        continue
                    direct_dict_calls.append(subnode.func.attr)

                if (
                    direct_dict_calls
                    and "api.model_create_multi" not in decorators
                ):
                    offenders.append(
                        f"{path.name}:{node.lineno}"
                    )

        self.assertEqual(offenders, [])

    def test_split_legacy_session_uses_valid_cooperative_super(self):
        source = (
            ROOT / "models/treatment_session_legacy_methods.py"
        ).read_text()

        self.assertNotIn(
            "super(ClinicTreatmentSession, self)",
            source,
        )
        self.assertIn(
            "sessions = super().create(prepared)",
            source,
        )
        self.assertIn(
            "@api.model_create_multi",
            source,
        )

        stage_source = (
            ROOT / "models/session_stage.py"
        ).read_text()
        self.assertIn(
            "@api.model_create_multi",
            stage_source,
        )
        self.assertIn(
            "stages = super().create(prepared)",
            stage_source,
        )

    def test_search_view_computed_fields_are_searchable(self):
        field_meta = {}

        for path in (ROOT / "models").rglob("*.py"):
            tree = ast.parse(path.read_text())

            for cls in (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
            ):
                model_names = []

                for statement in cls.body:
                    if not isinstance(statement, ast.Assign):
                        continue

                    for target in statement.targets:
                        if not (
                            isinstance(target, ast.Name)
                            and target.id in {"_name", "_inherit"}
                        ):
                            continue

                        try:
                            value = ast.literal_eval(statement.value)
                        except Exception:
                            continue

                        if isinstance(value, str):
                            model_names.append(value)

                for statement in cls.body:
                    if not (
                        isinstance(statement, ast.Assign)
                        and len(statement.targets) == 1
                        and isinstance(statement.targets[0], ast.Name)
                        and isinstance(statement.value, ast.Call)
                        and isinstance(statement.value.func, ast.Attribute)
                        and isinstance(statement.value.func.value, ast.Name)
                        and statement.value.func.value.id == "fields"
                    ):
                        continue

                    kwargs = {
                        keyword.arg: keyword.value
                        for keyword in statement.value.keywords
                        if keyword.arg
                    }

                    def literal(name, default=None):
                        node = kwargs.get(name)
                        if node is None:
                            return default
                        try:
                            return ast.literal_eval(node)
                        except Exception:
                            return default

                    for model_name in model_names:
                        field_meta[
                            (
                                model_name,
                                statement.targets[0].id,
                            )
                        ] = {
                            "compute": literal("compute"),
                            "store": literal("store", False),
                            "search": literal("search"),
                        }

        offenders = []

        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()

            for record in root.findall("record"):
                if record.attrib.get("model") != "ir.ui.view":
                    continue

                model_node = record.find("./field[@name='model']")
                arch_node = record.find("./field[@name='arch']")

                if (
                    model_node is None
                    or arch_node is None
                    or not list(arch_node)
                ):
                    continue

                model_name = (model_node.text or "").strip()
                arch = list(arch_node)[0]

                if arch.tag != "search":
                    continue

                for filter_node in arch.iter("filter"):
                    domain = filter_node.attrib.get("domain", "")

                    for field_name in re.findall(
                        r"\('([A-Za-z_][A-Za-z0-9_]*)'\s*,",
                        domain,
                    ):
                        meta = field_meta.get(
                            (model_name, field_name)
                        )
                        if not meta:
                            continue

                        if (
                            meta["compute"]
                            and not meta["store"]
                            and not meta["search"]
                        ):
                            offenders.append(
                                (
                                    path.name,
                                    filter_node.attrib.get("name"),
                                    model_name,
                                    field_name,
                                )
                            )

        self.assertEqual(offenders, [])

    def test_overtime_is_stored_and_indexed(self):
        source = (
            ROOT / "models/treatment_session.py"
        ).read_text()
        tree = ast.parse(source)

        field_call = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "is_overtime"
            ):
                field_call = node.value
                break

        self.assertIsNotNone(field_call)
        kwargs = {
            keyword.arg: keyword.value
            for keyword in field_call.keywords
            if keyword.arg
        }
        self.assertTrue(ast.literal_eval(kwargs["store"]))
        self.assertTrue(ast.literal_eval(kwargs["index"]))

    def test_historical_owned_models_preserved(self):
        expected = {
            "clinic.treatment.session",
            "clinic.treatment.session.line",
            "clinic.treatment.session.stage",
        }
        self.assertTrue(
            expected.issubset(set(self.fields_by_model))
        )

    def test_historical_session_fields_preserved(self):
        expected = {
            "name",
            "display_name",
            "active",
            "company_id",
            "color",
            "patient_id",
            "patient_phone",
            "patient_email",
            "clinic_doctor_id",
            "doctor_user_id",
            "treatment_id",
            "booking_id",
            "booking_state",
            "room_id",
            "start_datetime",
            "end_datetime",
            "duration_planned",
            "duration_actual",
            "is_overtime",
            "state",
            "stage_id",
            "can_edit",
            "note_internal",
            "note_public",
            "chief_complaint",
            "objective_notes",
            "assessment",
            "plan",
            "contraindication_flag",
            "cancellation_reason",
            "no_show_reason",
            "line_ids",
            "move_id",
            "attachment_count",
            "activity_count",
        }
        self.assertTrue(
            expected.issubset(
                self.fields_by_model["clinic.treatment.session"]
            )
        )

    def test_historical_session_methods_preserved(self):
        expected = {
            "_compute_display_name",
            "_compute_duration_actual",
            "_compute_is_overtime",
            "_compute_can_edit",
            "_compute_attachment_count",
            "_compute_activity_count",
            "_check_dates",
            "_check_company_consistency",
            "create",
            "write",
            "unlink",
            "_subscribe_related_partners",
            "action_confirm",
            "action_start",
            "action_done",
            "action_no_show",
            "action_cancel",
            "_sync_stage_with_state",
            "_post_done_hook",
            "action_prepare_billing",
            "action_create_invoice",
            "action_link_payment",
            "cron_send_session_reminders",
            "_send_session_reminder",
            "action_view_attachments",
            "action_view_activities",
            "action_view_patient",
            "action_view_invoice",
            "reschedule",
        }
        self.assertTrue(
            expected.issubset(
                self.methods_by_model["clinic.treatment.session"]
            )
        )

    def test_historical_line_fields_and_methods_preserved(self):
        expected_fields = {
            "session_id",
            "company_id",
            "patient_id",
            "clinic_doctor_id",
            "treatment_id",
            "sequence",
            "display_name",
            "display_type",
            "usage_type",
            "name",
            "product_id",
            "product_type",
            "product_uom_id",
            "quantity",
            "consumed_qty",
            "is_billable",
            "currency_id",
            "price_unit",
            "discount",
            "tax_ids",
            "price_subtotal",
            "price_total",
            "consumption_state",
            "date_consumed",
            "is_stock_relevant",
            "stock_move_id",
            "location_id",
            "location_dest_id",
            "note_internal",
            "package_line_id",
            "referral_id",
        }
        expected_methods = {
            "_compute_display_name",
            "_compute_is_stock_relevant",
            "_compute_amounts",
            "_check_product_required",
            "_check_consumed_not_exceed_quantity",
            "_onchange_product_id",
            "_onchange_usage_type_display_type",
            "_get_default_consumption_locations",
            "action_mark_ready",
            "action_mark_consumed",
            "action_reset_consumption",
            "prepare_billing_payload_line",
        }
        self.assertTrue(
            expected_fields.issubset(
                self.fields_by_model[
                    "clinic.treatment.session.line"
                ]
            )
        )
        self.assertTrue(
            expected_methods.issubset(
                self.methods_by_model[
                    "clinic.treatment.session.line"
                ]
            )
        )

    def test_historical_stage_fields_and_methods_preserved(self):
        expected_fields = {
            "name",
            "sequence",
            "active",
            "description",
            "color",
            "fold",
            "company_id",
            "technical_state",
            "is_default",
            "is_final",
            "legend_normal",
            "legend_done",
            "legend_blocked",
            "session_ids",
            "sessions_count",
        }
        expected_methods = {
            "_compute_sessions_count",
            "create",
            "write",
            "unlink",
            "_ensure_single_default_per_state",
            "get_default_stage",
            "action_view_sessions",
            "name_get",
            "_check_final_flag",
        }
        self.assertTrue(
            expected_fields.issubset(
                self.fields_by_model[
                    "clinic.treatment.session.stage"
                ]
            )
        )
        self.assertTrue(
            expected_methods.issubset(
                self.methods_by_model[
                    "clinic.treatment.session.stage"
                ]
            )
        )

    def test_historical_extension_contracts_preserved(self):
        checks = {
            "booking.booking": {
                "fields": {
                    "treatment_session_ids",
                    "treatment_session_count",
                    "has_treatment_sessions",
                    "auto_session_policy",
                },
                "methods": {
                    "action_generate_treatment_sessions",
                    "action_view_treatment_sessions",
                    "action_generate_and_view_treatment_sessions",
                    "_prepare_session_vals",
                },
            },
            "res.partner": {
                "fields": {
                    "treatment_session_ids",
                    "treatment_session_count",
                    "last_session_id",
                    "next_session_id",
                },
                "methods": {
                    "action_view_treatment_sessions",
                    "action_view_treatment_history",
                    "get_treatment_statistics",
                },
            },
            "hr.employee": {
                "fields": {
                    "treatment_session_ids",
                    "treatment_session_count",
                    "sessions_today_count",
                    "sessions_in_progress_count",
                },
                "methods": {
                    "action_view_treatment_sessions",
                    "action_view_today_treatment_sessions",
                    "get_treatment_statistics",
                },
            },
            "booking.room": {
                "fields": {
                    "treatment_session_ids",
                    "treatment_session_count",
                    "sessions_today_count",
                    "occupancy_state",
                },
                "methods": {
                    "is_available",
                    "get_occupancy_summary",
                    "action_view_treatment_sessions",
                },
            },
        }

        for model_name, contract in checks.items():
            self.assertTrue(
                contract["fields"].issubset(
                    self.fields_by_model[model_name]
                ),
                model_name,
            )
            self.assertTrue(
                contract["methods"].issubset(
                    self.methods_by_model[model_name]
                ),
                model_name,
            )

    def test_legacy_sql_constraints_removed(self):
        offenders = []
        for path in (ROOT / "models").rglob("*.py"):
            if path.name[:1].isdigit():
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "_sql_constraints"
                    ):
                        offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_odoo19_models_constraint_count(self):
        count = 0
        for path in (ROOT / "models").rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "models"
                    and func.attr == "Constraint"
                ):
                    count += 1
        self.assertGreaterEqual(count, 4)

    def test_booking_doctor_model_mismatch_is_repaired(self):
        source = (
            ROOT / "models/enterprise_booking.py"
        ).read_text()
        self.assertIn(
            'vals["doctor_id"] = self.doctor_id.id or False',
            source,
        )
        self.assertIn(
            'vals["clinic_doctor_id"] = employee.id or False',
            source,
        )
        self.assertIn(
            "def _get_booking_employee_doctor(",
            source,
        )

    def test_stock_consumption_requires_done_move(self):
        source = (
            ROOT / "models/enterprise_line.py"
        ).read_text()
        self.assertIn("move._action_done()", source)
        self.assertIn(
            'if move.state != "done":',
            source,
        )
        self.assertIn(
            "A completed inventory movement cannot be hidden",
            source,
        )

    def test_security_and_acl_are_loaded(self):
        manifest = ast.literal_eval(
            ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value
        )
        self.assertIn(
            "security/clinic_treatment_session_security.xml",
            manifest["data"],
        )
        self.assertIn(
            "security/ir.model.access.csv",
            manifest["data"],
        )

        with (
            ROOT / "security/ir.model.access.csv"
        ).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        model_ids = {row["model_id:id"] for row in rows}
        self.assertTrue(
            {
                "model_clinic_treatment_session",
                "model_clinic_treatment_session_line",
                "model_clinic_treatment_session_stage",
            }.issubset(model_ids)
        )

    def test_ui_matrix_search_list_form_for_all_owned_models(self):
        expected = {
            "clinic.treatment.session",
            "clinic.treatment.session.line",
            "clinic.treatment.session.stage",
        }
        found = {
            model_name: set()
            for model_name in expected
        }

        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()

            for record in root.findall("record"):
                if record.attrib.get("model") != "ir.ui.view":
                    continue

                model = record.find("./field[@name='model']")
                arch = record.find("./field[@name='arch']")
                if (
                    model is None
                    or arch is None
                    or not list(arch)
                ):
                    continue

                model_name = (model.text or "").strip()
                root_tag = list(arch)[0].tag

                if (
                    model_name in found
                    and root_tag in {"search", "list", "form"}
                ):
                    found[model_name].add(root_tag)

        for model_name in expected:
            self.assertEqual(
                found[model_name],
                {"search", "list", "form"},
                model_name,
            )

    def test_session_has_enterprise_view_types(self):
        source = (
            ROOT / "views/treatment_session_views.xml"
        ).read_text()
        for tag in (
            "<kanban",
            "<calendar",
            "<graph",
            "<pivot",
        ):
            self.assertIn(tag, source)

    def test_object_buttons_have_model_methods(self):
        mapping = {
            "clinic.treatment.session": set(),
            "clinic.treatment.session.line": set(),
            "clinic.treatment.session.stage": set(),
        }

        for path in (
            ROOT / "views"
        ).glob("*.xml"):
            root = ET.parse(path).getroot()
            for record in root.findall("record"):
                if record.attrib.get("model") != "ir.ui.view":
                    continue

                model = record.find("./field[@name='model']")
                arch = record.find("./field[@name='arch']")
                if (
                    model is None
                    or arch is None
                    or not list(arch)
                ):
                    continue

                model_name = (model.text or "").strip()
                if model_name not in mapping:
                    continue

                for button in list(arch)[0].iter("button"):
                    if button.attrib.get("type") == "object":
                        mapping[model_name].add(
                            button.attrib.get("name")
                        )

        # Inline One2many buttons belong to Session Line, not Session.
        session_view = ET.parse(
            ROOT / "views/treatment_session_views.xml"
        ).getroot()
        for button in session_view.iter("button"):
            name = button.attrib.get("name")
            if name in {
                "action_mark_ready",
                "action_mark_consumed",
                "action_open_stock_move",
            }:
                mapping["clinic.treatment.session"].discard(name)
                mapping["clinic.treatment.session.line"].add(name)

        for model_name, button_names in mapping.items():
            missing = button_names - self.methods_by_model[model_name]
            self.assertEqual(
                missing,
                set(),
                f"{model_name}: {sorted(missing)}",
            )

    def test_settings_view_extends_base(self):
        root = ET.parse(
            ROOT / "views/res_config_settings_views.xml"
        ).getroot()
        record = root.find(
            ".//record[@id='res_config_settings_view_form_treatment_session']"
        )
        self.assertIsNotNone(record)
        inherit = record.find("field[@name='inherit_id']")
        self.assertEqual(
            inherit.attrib.get("ref"),
            "base.res_config_settings_view_form",
        )

    def test_runtime_ui_bridge_is_optional_and_savepoint_isolated(self):
        source = (ROOT / "models/ui_bridge.py").read_text()
        self.assertIn("raise_if_not_found=False", source)
        self.assertIn("_get_combined_arch()", source)
        self.assertIn("with self.env.cr.savepoint():", source)

        manifest = ast.literal_eval(
            ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value
        )
        self.assertIn(
            "data/optional_ui_bridge.xml",
            manifest["data"],
        )
        self.assertGreater(
            manifest["data"].index("data/optional_ui_bridge.xml"),
            manifest["data"].index("views/treatment_session_menus.xml"),
        )

    def test_no_odoo19_string_xpath_selectors(self):
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

    def test_native_menus_do_not_use_invalid_groups_id(self):
        offenders = []
        for path in (ROOT / "views").glob("*.xml"):
            root = ET.parse(path).getroot()
            for record in root.findall(
                ".//record[@model='ir.ui.menu']"
            ):
                for field in record.findall("field"):
                    if field.attrib.get("name") == "groups_id":
                        offenders.append(
                            f"{path.name}: {record.attrib.get('id')}"
                        )
        self.assertEqual(offenders, [])

    def test_upgrade_migration_exists(self):
        migration = (
            ROOT
            / "migrations"
            / "19.0.2.0.0"
            / "pre-migrate.py"
        )
        self.assertTrue(migration.exists())
        source = migration.read_text()
        self.assertIn(
            "clinic_treatment_session.session",
            source,
        )
        self.assertIn(
            "_repair_session_numbers",
            source,
        )

    def test_no_digit_prefixed_backup_files_packaged(self):
        offenders = [
            path
            for path in ROOT.rglob("*")
            if (
                path.is_file()
                and path.name[:1].isdigit()
            )
        ]
        self.assertEqual(offenders, [])

    def test_human_friendly_model_file_size(self):
        offenders = []
        for path in (ROOT / "models").rglob("*.py"):
            if path.name[:1].isdigit():
                continue
            line_count = len(path.read_text().splitlines())
            if line_count > 900:
                offenders.append(
                    f"{path.relative_to(ROOT)}={line_count}"
                )
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
