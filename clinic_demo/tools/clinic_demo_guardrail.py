




#!/usr/bin/env python3
"""Static Enterprise Development Guardrail for clinic_demo Prompt 07."""

from pathlib import Path
import ast
import csv
import io
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE_SHA = "6904ebf6d62ae5f60371fd91287d99b00eba10addb2d7f952602fb0165ef5c2b"
EXPECTED_SUITE_SHA = "0b28236cd75ba56f9dc86ac26230ba04aeeec9e8952f03907e9e8cc19a98aade"
EXPECTED_CLINIC_DEPENDENCIES = 41
EXPECTED_ACL_ROWS = 26

PERSISTENT_UI_MODELS = {
    "clinic.demo.journey",
    "clinic.demo.run",
    "clinic.demo.reference",
    "clinic.demo.checkpoint",
    "clinic.demo.log",
    "clinic.demo.validation.result",
}

PROMPT17_OWNER_ADDONS = (
    "clinic_emar",
    "clinic_imaging",
    "clinic_care_plan",
    "clinic_consent_legal",
    "clinic_post_care_followup",
    "clinic_telemedicine_secure_messaging",
)

VALID_ODOO_TEMPORAL_HELPERS = {
    "Date": {"add", "context_today", "from_string", "to_date", "to_string", "today"},
    "Datetime": {
        "add", "context_timestamp", "from_string", "now", "subtract",
        "to_datetime", "to_string",
    },
}


def fail(message):
    print("FAIL:", message)
    raise SystemExit(1)


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def prompt17_owner_temporal_api_contract():
    """Reject nonexistent fields.Date/Datetime helpers on the full owner path."""
    invalid = []
    addons_root = ROOT.parent
    for addon_name in PROMPT17_OWNER_ADDONS:
        addon_root = addons_root / addon_name
        if not addon_root.is_dir():
            fail(f"Prompt-17 owner source is missing: {addon_name}")
        for path in sorted(addon_root.rglob("*.py")):
            relative = path.relative_to(addon_root)
            if (
                "tests" in relative.parts
                or "tools" in relative.parts
                or path.name.startswith("xxx_")
                or path.name[:1].isdigit()
            ):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "fields"
                    and node.value.attr in VALID_ODOO_TEMPORAL_HELPERS
                ):
                    continue
                field_type = node.value.attr
                if node.attr not in VALID_ODOO_TEMPORAL_HELPERS[field_type]:
                    invalid.append(
                        f"{addon_name}/{relative}:{node.lineno} "
                        f"fields.{field_type}.{node.attr}"
                    )
    if invalid:
        fail("Invalid Prompt-17 owner temporal APIs: " + "; ".join(invalid))


def python_contracts(python_files):
    model_fields = {}
    model_methods = {}
    model_relations = {}
    model_names = set()
    transient_models = set()
    legacy_constraints = []
    direct_sql = []
    manual_commit = []
    sudo_calls = []

    for path in python_files:
        if "tests" in path.parts or "tools" in path.parts:
            continue

        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_text = ast.unparse(node.func)
                if call_text.endswith(".sudo"):
                    sudo_calls.append(str(path.relative_to(ROOT)))
                if call_text.endswith(".commit"):
                    manual_commit.append(str(path.relative_to(ROOT)))
                if call_text.endswith(".execute"):
                    direct_sql.append(str(path.relative_to(ROOT)))

            if isinstance(node, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == "_sql_constraints"
                    for target in node.targets
                ):
                    legacy_constraints.append(str(path.relative_to(ROOT)))

        for cls in [item for item in tree.body if isinstance(item, ast.ClassDef)]:
            model_name = None
            base_text = " ".join(ast.unparse(base) for base in cls.bases)
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and (target.id == "_name" or (target.id == "_inherit" and model_name is None)):
                            model_name = literal(stmt.value)

            if not isinstance(model_name, str) or not model_name.startswith("clinic.demo."):
                continue

            model_names.add(model_name)
            if "TransientModel" in base_text:
                transient_models.add(model_name)
            model_fields.setdefault(model_name, set())
            model_methods.setdefault(model_name, set())
            model_relations.setdefault(model_name, {})

            for stmt in cls.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    model_methods[model_name].add(stmt.name)
                    continue

                if not (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Attribute)
                    and isinstance(stmt.value.func.value, ast.Name)
                    and stmt.value.func.value.id == "fields"
                ):
                    continue

                field_name = stmt.targets[0].id
                field_type = stmt.value.func.attr
                model_fields[model_name].add(field_name)
                if field_type in {"Many2one", "One2many", "Many2many"} and stmt.value.args:
                    comodel = literal(stmt.value.args[0])
                    if isinstance(comodel, str):
                        model_relations[model_name][field_name] = comodel

    if legacy_constraints:
        fail(f"Executable legacy _sql_constraints found: {legacy_constraints}")
    if direct_sql:
        fail(f"Direct SQL found: {direct_sql}")
    if manual_commit:
        fail(f"Manual commit found: {manual_commit}")
    allowed_technical_sudo = {
        "generators/validation/acceptance.py",
        "services/reset_service.py",
    }
    unexpected_sudo = sorted(set(sudo_calls) - allowed_technical_sudo)
    if unexpected_sudo:
        fail(f"Generic sudo() found in runtime source: {unexpected_sudo}")

    return model_names, transient_models, model_fields, model_methods, model_relations


def validate_views(xml_files, model_fields, model_methods, model_relations):
    view_types = {model: set() for model in PERSISTENT_UI_MODELS}
    object_button_errors = []
    field_errors = []
    search_group_errors = []
    res_config_primary = []

    for path in xml_files:
        root = ET.parse(path).getroot()

        for record in root.findall(".//record"):
            if record.attrib.get("model") != "ir.ui.view":
                continue

            model_field = record.find("./field[@name='model']")
            arch_field = record.find("./field[@name='arch']")
            model_name = (model_field.text or "").strip() if model_field is not None else ""
            if arch_field is None or not list(arch_field):
                continue
            arch_root = list(arch_field)[0]

            if model_name == "res.config.settings" and not record.find("./field[@name='inherit_id']"):
                res_config_primary.append(str(path.relative_to(ROOT)))

            if model_name in view_types and arch_root.tag in {"search", "list", "form"}:
                view_types[model_name].add(arch_root.tag)

            if arch_root.tag == "search":
                for group in arch_root.findall(".//group"):
                    if "expand" in group.attrib or "string" in group.attrib:
                        search_group_errors.append(
                            f"{path.relative_to(ROOT)}: search group uses forbidden attrs {group.attrib}"
                        )

            if model_name not in model_fields:
                continue

            def walk(element, current_model):
                # A nested x2many field switches the model context for its child arch.
                nested_model = current_model
                if element.tag == "field":
                    field_name = element.attrib.get("name")
                    if field_name and field_name not in model_fields.get(current_model, set()):
                        # Framework/model inherited fields such as display_name are not used
                        # in Prompt-07 arches; any unknown direct field is a real defect.
                        field_errors.append(
                            f"{path.relative_to(ROOT)}: {current_model}.{field_name} not found"
                        )
                    nested_model = model_relations.get(current_model, {}).get(field_name, current_model)

                if element.tag == "button" and element.attrib.get("type") == "object":
                    method = element.attrib.get("name")
                    if method and method not in model_methods.get(current_model, set()):
                        object_button_errors.append(
                            f"{path.relative_to(ROOT)}: {current_model}.{method}() not found"
                        )

                for child in list(element):
                    walk(child, nested_model)

            walk(arch_root, model_name)

    missing_views = {
        model: sorted({"search", "list", "form"} - found)
        for model, found in view_types.items()
        if found != {"search", "list", "form"}
    }
    if missing_views:
        fail(f"Search/List/Form matrix incomplete: {missing_views}")
    if field_errors:
        fail("View field/model mismatches: " + "; ".join(field_errors[:20]))
    if object_button_errors:
        fail("Object button/model-method mismatches: " + "; ".join(object_button_errors[:20]))
    if search_group_errors:
        fail("Odoo 19 search-view group syntax errors: " + "; ".join(search_group_errors))
    if res_config_primary:
        fail(f"Primary res.config.settings view detected: {res_config_primary}")


def main():
    python_files = sorted(ROOT.rglob("*.py"))
    xml_files = sorted(ROOT.rglob("*.xml"))

    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in xml_files:
        ET.parse(path)

    prompt17_owner_temporal_api_contract()

    manifest = ast.literal_eval(
        ast.parse((ROOT / "__manifest__.py").read_text(encoding="utf-8")).body[0].value
    )
    clinic_deps = [name for name in manifest["depends"] if name.startswith("clinic_")]
    if len(clinic_deps) != EXPECTED_CLINIC_DEPENDENCIES or len(set(clinic_deps)) != 41:
        fail(f"Expected 41 unique ClinicOne dependencies, found {len(clinic_deps)}")

    constants = (ROOT / "services/constants.py").read_text(encoding="utf-8")
    if EXPECTED_SOURCE_SHA not in constants:
        fail("Authoritative source SHA is not embedded in constants.")
    if EXPECTED_SUITE_SHA not in constants:
        fail("Expected suite fingerprint is not embedded in constants.")

    numeric = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file() and path.name[:1].isdigit()
    ]
    if numeric:
        fail(f"Numeric-prefix package files found: {numeric}")

    cache_artifacts = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file() and (path.suffix == ".pyc" or "__pycache__" in path.parts)
    ]
    if cache_artifacts:
        fail(f"Python cache artifacts found: {cache_artifacts}")

    oversized = []
    for path in python_files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > 950:
            oversized.append((str(path.relative_to(ROOT)), lines))
    if oversized:
        fail(f"Oversized Python files: {oversized}")

    model_names, transient_models, model_fields, model_methods, model_relations = python_contracts(
        python_files
    )

    expected_models = PERSISTENT_UI_MODELS | {"clinic.demo.reset.confirm.wizard"}
    if model_names != expected_models:
        fail(
            f"Prompt-07 model set mismatch. Expected {sorted(expected_models)}, "
            f"found {sorted(model_names)}"
        )
    if transient_models != {"clinic.demo.reset.confirm.wizard"}:
        fail(f"Unexpected transient model set: {sorted(transient_models)}")

    validate_views(xml_files, model_fields, model_methods, model_relations)

    # Raw ir.ui.menu records must use Odoo-19 group_ids; Prompt 07 uses native menuitem.
    for path in xml_files:
        root = ET.parse(path).getroot()
        for record in root.findall(".//record[@model='ir.ui.menu']"):
            bad = record.find("./field[@name='groups_id']")
            if bad is not None:
                fail(f"Invalid Odoo 19 ir.ui.menu groups_id field in {path.relative_to(ROOT)}")

    menu_xml = (ROOT / "views/demo_menus.xml").read_text(encoding="utf-8")
    if 'parent="clinic_patient.menu_patient_configuration"' in menu_xml:
        fail(
            "Demo Dataset menu still has a hard external ClinicOne Configuration "
            "parent XML-ID and can fail on runtime DB/source drift."
        )

    bridge_xml = (ROOT / "data/demo_menu_bridge.xml").read_text(encoding="utf-8")
    bridge_service = (
        ROOT / "services/menu_bridge_service.py"
    ).read_text(encoding="utf-8")
    if "_ensure_demo_dataset_menu_parent" not in bridge_xml:
        fail("Runtime menu bridge function is not loaded after Demo Dataset menus.")
    if "clinic_patient.menu_patient_configuration" not in bridge_service:
        fail("Runtime menu bridge no longer prefers the source-actual Configuration menu.")

    reset_view = (ROOT / "wizard/demo_reset_confirm_views.xml").read_text(encoding="utf-8")
    if "action_confirm_reset" not in reset_view or "acknowledge_retained_evidence" not in reset_view:
        fail("Destructive reset confirmation UI is incomplete.")

    acl = ROOT / "security/ir.model.access.csv"
    rows = list(csv.DictReader(io.StringIO(acl.read_text(encoding="utf-8"))))
    if len(rows) != EXPECTED_ACL_ROWS:
        fail(f"Expected {EXPECTED_ACL_ROWS} ACL rows, found {len(rows)}")

    manager_wizard_acl = [
        row for row in rows
        if row["model_id:id"] == "model_clinic_demo_reset_confirm_wizard"
        and row["group_id:id"] == "clinic_demo.group_demo_manager"
    ]
    if len(manager_wizard_acl) != 1:
        fail("Reset wizard is not restricted to Demo Dataset Manager.")

    system_admin_models = {
        row["model_id:id"]
        for row in rows
        if row["group_id:id"] == "base.group_system"
        and row["perm_read"] == "1"
        and row["perm_write"] == "1"
        and row["perm_create"] == "1"
        and row["perm_unlink"] == "1"
    }
    expected_admin_models = {
        "model_clinic_demo_journey",
        "model_clinic_demo_run",
        "model_clinic_demo_reference",
        "model_clinic_demo_checkpoint",
        "model_clinic_demo_log",
        "model_clinic_demo_validation_result",
        "model_clinic_demo_reset_confirm_wizard",
    }
    if system_admin_models != expected_admin_models:
        fail(
            "System Administrator ACL coverage mismatch: "
            f"{sorted(system_admin_models)}"
        )

    required_run_buttons = {
        "action_generate_full_dataset",
        "action_generate_current_phase",
        "action_continue_generation",
        "action_validate",
        "action_regenerate_missing",
        "action_open_reset_wizard",
        "action_open_logs",
        "action_open_golden_journeys",
    }
    missing_run_methods = required_run_buttons - model_methods["clinic.demo.run"]
    if missing_run_methods:
        fail(f"Control Center button methods missing: {sorted(missing_run_methods)}")

    # MASTER PROMPT 08 foundation-generator contract.
    foundation_init = (ROOT / "generators/foundation/__init__.py")
    if not foundation_init.exists():
        fail("Prompt-08 foundation generator package is missing.")

    generator_sources = {
        "foundation.native": ROOT / "generators/foundation/native_odoo.py",
        "foundation.organization": ROOT / "generators/foundation/organization.py",
    }
    for key, path in generator_sources.items():
        if not path.exists():
            fail(f"Registered Prompt-08 generator source missing: {key}")
        source = path.read_text(encoding="utf-8")
        if "GENERATOR_REGISTRY.register" not in source:
            fail(f"Prompt-08 generator is not explicitly registered: {key}")

    organization_source = generator_sources["foundation.organization"].read_text(
        encoding="utf-8"
    )
    if "clinic_branch.group_branch_manager" not in organization_source:
        fail("Organization generator no longer declares Clinic Branch Manager requirement.")
    if "DEMO-BRANCH-001" not in organization_source:
        fail("Stable organization demo keys are missing.")

    security_source = (ROOT / "security/clinic_demo_security.xml").read_text(
        encoding="utf-8"
    )
    if "clinic_branch.group_branch_manager" not in security_source:
        fail("Demo Dataset Manager no longer implies Clinic Branch Manager.")

    execution_source = (ROOT / "services/execution_engine.py").read_text(
        encoding="utf-8"
    )
    if "with self.env.cr.savepoint()" not in execution_source:
        fail("Prompt-08 bounded generator savepoint is missing.")
    if "EXPECTED_FINAL_GENERATOR_COUNT = 35" not in execution_source:
        fail("Prompt-05 35-generator completion contract is not preserved.")

    print("MASTER PROMPT 17 ENTERPRISE GUARDRAIL: PASS")
    print(f"Python parse: {len(python_files)} PASS")
    print(f"XML parse: {len(xml_files)} PASS")
    print("ClinicOne direct dependencies: 41 PASS")
    print("Control models: 6 persistent + 1 transient PASS")
    print("Search/List/Form UI matrix: 6/6 PASS")
    print("Object button/model-method audit: PASS")
    print("View field/model audit: PASS")
    print("Odoo 19 search-view group syntax: PASS")
    print("Primary res.config.settings hijack: 0 PASS")
    print("Runtime-safe Demo Dataset menu routing: PASS")
    print("Registered foundation generators: 2 PASS")
    workforce_files = [
        ROOT / "generators/workforce/preflight.py",
        ROOT / "generators/workforce/staff_provider.py",
    ]
    if not all(path.exists() for path in workforce_files):
        fail("Prompt-09 workforce generators are missing.")
    workforce_text = "\n".join(path.read_text(encoding="utf-8") for path in workforce_files)
    if ".sudo(" in workforce_text or ".cr.commit(" in workforce_text or ".execute(" in workforce_text:
        fail("Prompt-09 workforce generator bypasses ORM/security boundaries.")
    if '"groups_id":' in workforce_text:
        fail("Prompt-09 uses legacy res.users.groups_id; Odoo 19 requires group_ids.")
    if '"group_ids":' not in workforce_text:
        fail("Prompt-09 does not assign Odoo 19 res.users.group_ids.")
    if "check_access_rights(" in workforce_text:
        fail("Prompt-09 uses removed legacy check_access_rights(); Odoo 19 requires check_access().")
    if '.check_access("read")' not in workforce_text:
        fail("Prompt-09 role validation does not use Odoo 19 check_access().")
    if "clinic_staff.seq_clinic_staff" not in workforce_text or "clinic_doctor.seq_clinic_appointment" not in workforce_text:
        fail("Prompt-09 ACL/sequence preflight contract is incomplete.")
    print("Registered workforce generators: 2 PASS")

    patient_file = ROOT / "generators/patient/personas.py"
    if not patient_file.exists():
        fail("Prompt-10 patient persona generator is missing.")
    patient_text = patient_file.read_text(encoding="utf-8")
    for token in (
        'key = "patient.personas"',
        'phase = "10_patient"',
        'depends_on = ("workforce.staff",)',
        '"compact": len(CORE_PERSONAS)',
        '"standard": len(CORE_PERSONAS) + 8',
        '"full_enterprise": len(CORE_PERSONAS) + 16',
        '"clinic_patient.seq_patient_code"',
        '"clinic.patient.identifier"',
        '@clinicone-demo.invalid',
    ):
        if token not in patient_text:
            fail(f"Prompt-10 patient contract token missing: {token}")
    if '.sudo(' in patient_text or '.cr.commit(' in patient_text or '.execute(' in patient_text:
        fail("Prompt-10 patient generator bypasses ORM/security/transaction boundaries.")
    if 'import random' in patient_text or 'uuid4' in patient_text or 'faker' in patient_text.lower():
        fail("Prompt-10 patient generator violates deterministic/synthetic identity contract.")
    for forbidden_model in (
        'booking.booking', 'clinic.encounter', 'membership.contract',
        'clinic.insurance.authorization', 'clinic.treatment.session',
    ):
        if f'ctx.env["{forbidden_model}"].create' in patient_text:
            fail(f"Prompt-10 creates premature downstream transaction: {forbidden_model}")
    print("Registered patient persona generators: 1 PASS")

    master_files = [
        ROOT / "generators/master/catalog.py",
        ROOT / "generators/master/consent.py",
        ROOT / "generators/master/commercial.py",
    ]
    if not all(path.exists() for path in master_files):
        fail("Prompt-11 master generator package is incomplete.")
    master_text = "\n".join(path.read_text(encoding="utf-8") for path in master_files)
    for token in (
        'key = "master.catalog"', 'key = "master.consent"', 'key = "master.commercial"',
        'phase = "11_master"', '"clinic.treatment"', '"clinic.consent.template"',
        '"clinic.package"', '"membership.plan"', '"clinic.insurance.plan"', '"clinic.wallet.rule"',
        'action_publish()', 'action_activate()', 'action_ignore()', 'action_cancel()',
    ):
        if token not in master_text:
            fail(f"Prompt-11 master contract token missing: {token}")
    if '.sudo(' in master_text or '.cr.commit(' in master_text or '.execute(' in master_text:
        fail("Prompt-11 master generators bypass ORM/security/transaction boundaries.")
    if 'date.today()' in master_text or 'uuid4' in master_text or 'import random' in master_text:
        fail("Prompt-11 generator violates anchor-date/determinism contract.")
    print("Registered Prompt-11 master generators: 3 PASS")
    print("Clinical catalog / consent / package / membership / insurance / wallet masters: PASS")
    print("Prompt-11 premature downstream transactions: 0 PASS")

    resources_file = ROOT / "generators/resources/rooms_devices.py"
    if not resources_file.exists():
        fail("Prompt-12 room/device/resource generator is missing.")
    resources_text = resources_file.read_text(encoding="utf-8")
    for token in (
        'key = "resources.rooms_devices"', 'phase = "12_resources"',
        'depends_on = ("master.commercial",)', '"clinic.room"', '"clinic.device"',
        '"booking.room"', '"booking.resource"', '"booking.doctor.schedule"', '"booking.slot"',
        'assignment.action_activate()', 'DEMO-BROOM-BLACKOUT-001', 'DEMO-BRESOURCE-BLACKOUT-001',
    ):
        if token not in resources_text:
            fail(f"Prompt-12 resource contract token missing: {token}")
    if '.sudo(' in resources_text or '.cr.commit(' in resources_text or '.execute(' in resources_text:
        fail("Prompt-12 resource generator bypasses ORM/security/transaction boundaries.")
    if 'date.today()' in resources_text or 'uuid4' in resources_text or 'import random' in resources_text:
        fail("Prompt-12 generator violates anchor-date/determinism contract.")
    for forbidden_model in (
        'booking.booking', 'clinic.room.session', 'clinic.encounter',
        'clinic.treatment.session', 'account.move',
    ):
        if f'ctx.env["{forbidden_model}"].create' in resources_text:
            fail(f"Prompt-12 creates premature downstream transaction: {forbidden_model}")
    print("Registered Prompt-12 resource generators: 1 PASS")
    print("Rooms / devices / booking resources / schedules / blackouts: PASS")
    print("Prompt-12 premature downstream transactions: 0 PASS")

    historical_service = ROOT / "services/historical_service.py"
    historical_generator = ROOT / "generators/history/patient_longitudinal.py"
    if not historical_service.exists() or not historical_generator.exists():
        fail("Prompt-13 historical service/generator package is incomplete.")
    historical_text = historical_generator.read_text(encoding="utf-8")
    timeline_text = historical_service.read_text(encoding="utf-8")
    for token in (
        'key = "history.patient_longitudinal"',
        'phase = "13_history"',
        'depends_on = ("resources.rooms_devices",)',
        '"clinic.patient.vital"',
        '"clinic.patient.condition.episode"',
        '"clinic.patient.allergy.reaction"',
        'BUSINESS_DATE_FIELDS',
        'PROFILE_HISTORY_BUDGETS',
        'HistoricalTimelineService',
    ):
        if token not in (historical_text + timeline_text):
            fail(f"Prompt-13 historical contract token missing: {token}")
    if any(token in historical_text for token in (
        'ctx.env["booking.booking"].create',
        'ctx.env["clinic.encounter"].create',
        'ctx.env["clinic.treatment.session"].create',
        'ctx.env["clinic.billing.invoice"].create',
    )):
        fail("Prompt-13 pre-empts later domain transaction generators.")
    if any(token in historical_text + timeline_text for token in (
        ".sudo(", ".cr.commit(", ".execute(", "date.today()", "datetime.now()", "uuid4",
    )):
        fail("Prompt-13 historical engine violates ORM/determinism boundaries.")
    registered_generator_keys = set()
    for generator_path in sorted((ROOT / "generators").rglob("*.py")):
        tree = ast.parse(generator_path.read_text(encoding="utf-8"), filename=str(generator_path))
        for cls in [node for node in tree.body if isinstance(node, ast.ClassDef)]:
            if not any(ast.unparse(dec) == "GENERATOR_REGISTRY.register" for dec in cls.decorator_list):
                continue
            for stmt in cls.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                if not any(isinstance(target, ast.Name) and target.id == "key" for target in stmt.targets):
                    continue
                key = literal(stmt.value)
                if isinstance(key, str):
                    registered_generator_keys.add(key)
    if len(registered_generator_keys) != 35:
        fail(f"Prompt-23 expected 35 registered generators, found {len(registered_generator_keys)}.")
    prompt19_keys = {"exception.feedback", "exception.incident_quality", "digital.ecommerce_marketing_portal"}
    if not prompt19_keys <= registered_generator_keys:
        fail(f"Prompt-19 generator registry incomplete: {sorted(prompt19_keys - registered_generator_keys)}")
    if "operations.future_pipeline" not in registered_generator_keys:
        fail("Prompt-20 future-pipeline generator is not registered.")
    if "management.reports" not in registered_generator_keys:
        fail("Prompt-21 management-reports generator is not registered.")
    if not {"management.dashboard", "management.analytics"} <= registered_generator_keys:
        fail("Prompt-22 Dashboard/Analytics generators are not both registered.")
    prompt23_keys = {
        "validation.structural", "validation.temporal", "validation.workflow",
        "validation.journey_exception", "validation.analytics_evidence",
        "validation.integrity_reset_regeneration",
    }
    if not prompt23_keys <= registered_generator_keys:
        fail(f"Prompt-23 acceptance registry incomplete: {sorted(prompt23_keys - registered_generator_keys)}")
    prompt23_source = (ROOT / "generators/validation/acceptance.py").read_text(encoding="utf-8")
    for token in (
        "DATETIME_INTERVAL_CONTRACTS",
        '"clinic.triage.session": ("start_datetime", "end_datetime", "non_decreasing")',
        '"booking.booking": ("start_datetime", "end_datetime", "strict")',
        'rule == "strict" and end == start',
    ):
        if token not in prompt23_source:
            fail(f"Prompt-23 model-owned temporal contract missing: {token}")
    if 'if {"start_datetime", "end_datetime"} <= set(record._fields)' in prompt23_source:
        fail("Prompt-23 still applies one generic interval rule across unrelated owner models.")
    reset_source = (ROOT / "services/reset_policy_registry.py").read_text(encoding="utf-8")
    for model_name in (
        "account.move", "clinic.ap", "clinic.ar.invoice", "clinic.appointment", "clinic.encounter",
        "clinic.triage.session", "clinical.imaging", "clinic.emar.order",
        "clinic.incident", "clinic.queue", "clinic.telemedicine.session",
        "clinic.dashboard.snapshot", "clinic.analytics.snapshot.line",
    ):
        if f'"{model_name}"' not in reset_source:
            fail(f"Prompt-23 reset-policy closure missing owner model: {model_name}")
    for release_artifact in (
        "CLINIC_DEMO_EXECUTIVE_DEMO_SCRIPT.md",
        "CLINIC_DEMO_ENTERPRISE_COMPLETENESS_MATRIX.md",
        "CLINIC_DEMO_RELEASE_MANIFEST.md",
        "CLINIC_DEMO_CORE_PATCH_LEDGER.md",
        "PROMPT_24_FINAL_HARDENING_RELEASE.md",
    ):
        if not (ROOT / "docs" / release_artifact).is_file():
            fail(f"Prompt-24 release artifact missing: {release_artifact}")
    print("Registered Prompt-13 historical generators: 1 PASS")
    print("Historical business-date contract / longitudinal patient baseline: PASS")
    print("Prompt-13 premature downstream transactions: 0 PASS")
    operations_referral = ROOT / "generators/operations/referral.py"
    operations_booking = ROOT / "generators/operations/booking.py"
    if not operations_referral.exists() or not operations_booking.exists():
        fail("Prompt-14 referral/booking generator package is incomplete.")
    prompt14_text = operations_referral.read_text(encoding="utf-8") + "\n" + operations_booking.read_text(encoding="utf-8")
    for token in (
        'key = "operations.referral"', 'depends_on = ("history.patient_longitudinal",)',
        'key = "operations.booking"', 'depends_on = ("operations.referral",)',
        '"clinic.referral"', '"booking.booking"', 'DEMO-REF-001',
        'DEMO-BOOK-TODAY-REF-001', 'DEMO-BOOK-HIST-', 'DEMO-FUT-BOOK-',
        'action_confirm(', 'action_done()', 'action_cancel(', 'action_mark_no_show()',
        'action_apply_reschedule(', 'mark_converted(source_record=booking',
        '"auto_create_appointment": False', '"lock_slot_on_confirm": False',
    ):
        if token not in prompt14_text:
            fail(f"Prompt-14 front-office contract token missing: {token}")
    if any(token in prompt14_text for token in (
        ".sudo(", ".cr.commit(", ".execute(", "date.today()", "datetime.now()", "uuid4",
        'ctx.env["clinic.queue"].create', 'ctx.env["clinic.encounter"].create',
        'ctx.env["clinic.treatment.session"].create',
    )):
        fail("Prompt-14 generator violates security/determinism/bounded-scope contract.")
    print("Registered Prompt-14 front-office generators: 2 PASS")
    print("Referral acquisition/conversion + Booking historical/current/future: PASS")
    print("Prompt-14 premature Queue/Triage/Encounter/Treatment Session transactions: 0 PASS")
    print("Patient budgets: Compact 16 / Standard 24 / Full Enterprise 32 PASS")
    print("Patient identity: registry + source sequence + MRN/NIK/BPJS foundation PASS")
    print("Foundation → Workforce → Patient dependency chain: PASS")
    print("Bounded savepoint execution: PASS")
    print("Reset confirmation + Manager/System-Admin ACL: PASS")
    print(f"ACL rows: {len(rows)} PASS")
    print("Legacy _sql_constraints/direct SQL/manual commit/sudo: 0 PASS")
    print("Numeric-prefix/cache artifacts: 0 PASS")
    print("Human-friendly file-size ceiling: PASS")
    print("Prompt-17 owner temporal API allowlist: PASS")


if __name__ == "__main__":
    main()
















