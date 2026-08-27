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
EXPECTED_SOURCE_SHA = "4f1c986c7e1bec0848bec6659315ba239288f8f0cc37959bcf0dd47f1ef7b214"
EXPECTED_SUITE_SHA = "8b16194ce2de3736aa2a91cfad6569dcb0f174eff1b3d9ac2e86961a198fc8ed"
EXPECTED_CLINIC_DEPENDENCIES = 41
EXPECTED_ACL_ROWS = 22

PERSISTENT_UI_MODELS = {
    "clinic.demo.run",
    "clinic.demo.reference",
    "clinic.demo.checkpoint",
    "clinic.demo.log",
    "clinic.demo.validation.result",
}


def fail(message):
    print("FAIL:", message)
    raise SystemExit(1)


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


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
                        if isinstance(target, ast.Name) and target.id == "_name":
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
    if sudo_calls:
        fail(f"Generic sudo() found in runtime source: {sudo_calls}")

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

    print("MASTER PROMPT 08 ENTERPRISE GUARDRAIL: PASS")
    print(f"Python parse: {len(python_files)} PASS")
    print(f"XML parse: {len(xml_files)} PASS")
    print("ClinicOne direct dependencies: 41 PASS")
    print("Control models: 5 persistent + 1 transient PASS")
    print("Search/List/Form UI matrix: 5/5 PASS")
    print("Object button/model-method audit: PASS")
    print("View field/model audit: PASS")
    print("Odoo 19 search-view group syntax: PASS")
    print("Primary res.config.settings hijack: 0 PASS")
    print("Runtime-safe Demo Dataset menu routing: PASS")
    print("Registered foundation generators: 2 PASS")
    print("Foundation generator dependency chain: PASS")
    print("Bounded savepoint execution: PASS")
    print("Reset confirmation + Manager/System-Admin ACL: PASS")
    print(f"ACL rows: {len(rows)} PASS")
    print("Legacy _sql_constraints/direct SQL/manual commit/sudo: 0 PASS")
    print("Numeric-prefix/cache artifacts: 0 PASS")
    print("Human-friendly file-size ceiling: PASS")


if __name__ == "__main__":
    main()
