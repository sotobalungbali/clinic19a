
#!/usr/bin/env python3
"""Static Enterprise Development Guardrail for ClinicOne clinic_patient.

This validator is intentionally Odoo-server independent. It is a hard static gate,
not a replacement for target-PC install/upgrade/runtime testing.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "CLINIC_PATIENT_BASELINE_CONTRACT.json"
EXPECTED_ADDON = "clinic_patient"
EXPECTED_DEPENDS = ["base", "mail", "contacts", "uom", "product", "clinic_base"]
CUSTOM_MODELS = {
    "clinic.patient.stage",
    "clinic.patient.tag",
    "clinic.patient",
    "clinic.allergen.category",
    "clinic.allergen",
    "clinic.allergy.reaction.type",
    "clinic.patient.allergy",
    "clinic.patient.allergy.reaction",
    "clinic.condition.category",
    "clinic.condition",
    "clinic.condition.code",
    "clinic.patient.condition",
    "clinic.patient.condition.episode",
    "clinic.patient.identifier.type",
    "clinic.patient.identifier",
    "clinic.patient.vital",
}
COMPANY_RULE_MODELS = {
    "clinic.patient",
    "clinic.patient.identifier",
    "clinic.patient.allergy",
    "clinic.patient.allergy.reaction",
    "clinic.patient.condition",
    "clinic.patient.condition.episode",
    "clinic.patient.vital",
}
REQUIRED_GATES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15]


class GateFailure(Exception):
    pass


def fail(message: str) -> None:
    raise GateFailure(message)


def load_manifest() -> dict:
    path = ROOT / "__manifest__.py"
    try:
        return ast.literal_eval(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Manifest cannot be parsed: {exc}")


def python_inventory() -> dict:
    """Return classes keyed by _name or inherit:<model>."""
    result = {}
    for path in sorted((ROOT / "models").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            fail(f"Python parse failed for {path.relative_to(ROOT)}: {exc}")

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            model_name = None
            inherit_name = None
            fields = set()
            methods = set()

            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id in {"_name", "_inherit"}:
                            try:
                                value = ast.literal_eval(item.value)
                            except Exception:
                                value = None
                            if target.id == "_name":
                                model_name = value
                            else:
                                inherit_name = value

                        if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                            fn = item.value.func
                            if (
                                isinstance(fn, ast.Attribute)
                                and isinstance(fn.value, ast.Name)
                                and fn.value.id == "fields"
                            ):
                                fields.add(target.id)

                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(item.name)

            if model_name or inherit_name:
                key = model_name or f"inherit:{inherit_name}"
                result[key] = {
                    "model": model_name,
                    "inherit": inherit_name,
                    "fields": fields,
                    "methods": methods,
                    "file": str(path.relative_to(ROOT)),
                }

    return result


def active_manifest_files(manifest: dict) -> list[Path]:
    paths = []
    for rel in manifest.get("data", []) + manifest.get("demo", []):
        path = ROOT / rel
        if not path.is_file():
            fail(f"Manifest references missing file: {rel}")
        if path.name.startswith("0"):
            fail(f"Backup file beginning with 0 is loaded by manifest: {rel}")
        paths.append(path)
    return paths


def parsed_xml_files(paths: list[Path]) -> list[tuple[Path, ET.Element]]:
    parsed = []
    for path in paths:
        if path.suffix.lower() != ".xml":
            continue
        try:
            parsed.append((path, ET.parse(path).getroot()))
        except ET.ParseError as exc:
            fail(f"XML parse failed for {path.relative_to(ROOT)}: {exc}")
    return parsed


def view_matrix(xml_docs: list[tuple[Path, ET.Element]]) -> dict[str, dict[str, ET.Element]]:
    matrix: dict[str, dict[str, ET.Element]] = {}
    for _path, doc in xml_docs:
        for record in doc.findall(".//record[@model='ir.ui.view']"):
            model_field = record.find("./field[@name='model']")
            arch_field = record.find("./field[@name='arch']")
            if model_field is None or arch_field is None or len(arch_field) == 0:
                continue
            model = (model_field.text or "").strip()
            arch_root = arch_field[0]
            matrix.setdefault(model, {})[arch_root.tag] = arch_root
    return matrix


def gate0_identity(manifest: dict) -> None:
    if ROOT.name != EXPECTED_ADDON:
        fail(f"Addon directory must be named {EXPECTED_ADDON!r}; found {ROOT.name!r}")
    if manifest.get("name") != "ClinicOne - Patient Management":
        fail("Manifest identity does not match ClinicOne Patient Management")
    if not str(manifest.get("version", "")).startswith("19.0."):
        fail("Manifest version is not an Odoo 19 version")


def gate1_codex_role() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = [
        "LIMITED_IMPLEMENTATION_WORKER",
        "Codex is NOT",
        "an architect",
        "a simplifier",
        "endless retry engine",
    ]
    for token in required:
        if token not in text:
            fail(f"AGENTS.md misses Codex role guardrail token: {token}")


def gate2_preservation(contract: dict, current: dict, manifest: dict) -> None:
    if manifest.get("depends", []) != EXPECTED_DEPENDS:
        fail(
            "Manifest dependency contract changed. "
            f"Expected {EXPECTED_DEPENDS!r}; found {manifest.get('depends', [])!r}"
        )

    for entity in contract["baseline_entities"]:
        key = entity["key"]
        if key not in current:
            fail(f"Baseline model/inheritance class missing: {key}")

        cur = current[key]
        missing_fields = sorted(set(entity["fields"]) - cur["fields"])
        if missing_fields:
            fail(f"{key}: baseline fields removed/renamed: {missing_fields}")

        baseline_methods = set(entity["methods"])
        # Explicit Odoo 19 API migration.
        if "_name_search" in baseline_methods:
            baseline_methods.remove("_name_search")
            if "name_search" not in cur["methods"]:
                fail(f"{key}: _name_search migration requires name_search()")

        missing_methods = sorted(baseline_methods - cur["methods"])
        if missing_methods:
            fail(f"{key}: baseline methods removed/renamed: {missing_methods}")


def gate3_enterprise_completeness(xml_docs: list[tuple[Path, ET.Element]]) -> None:
    required = [
        "security/clinic_patient_security.xml",
        "security/ir.model.access.csv",
        "data/patient_sequence.xml",
        "data/patient_stage_data.xml",
        "report/patient_card_report.xml",
        "views/patient_views.xml",
        "views/patient_identifier_views.xml",
        "views/patient_allergy_views.xml",
        "views/patient_condition_views.xml",
        "views/patient_vital_views.xml",
        "views/res_partner_views.xml",
        "views/res_users_views.xml",
        "views/clinic_patient_menus.xml",
    ]
    for rel in required:
        if not (ROOT / rel).is_file():
            fail(f"Enterprise completeness artifact missing: {rel}")

    combined = "\n".join(
        (path.read_text(encoding="utf-8") for path, _doc in xml_docs)
    )
    for token in [
        'id="seq_clinic_patient_code"',
        "<field name=\"code\">clinic_patient.seq_patient_code</field>",
        'id="action_report_patient_card"',
        'id="patient_stage_new"',
        'id="patient_stage_registered"',
    ]:
        if token not in combined:
            fail(f"Required existing-code completion XML token missing: {token}")


def gate4_inventory() -> None:
    path = ROOT / "docs" / "CLINIC_PATIENT_STRUCTURAL_INVENTORY.md"
    if not path.is_file():
        fail("Full structural inventory is missing")
    text = path.read_text(encoding="utf-8")
    for model in CUSTOM_MODELS:
        if f"`{model}`" not in text:
            fail(f"Structural inventory misses model {model}")


def gate5_human_structure() -> None:
    required = {
        "models/patient.py",
        "models/patient_identifier.py",
        "models/patient_allergy.py",
        "models/patient_condition.py",
        "models/patient_vital.py",
        "models/res_partner_inherit.py",
        "models/res_users_inherit.py",
        "views/patient_views.xml",
        "views/patient_identifier_views.xml",
        "views/patient_allergy_views.xml",
        "views/patient_condition_views.xml",
        "views/patient_vital_views.xml",
    }
    missing = sorted(rel for rel in required if not (ROOT / rel).is_file())
    if missing:
        fail(f"Human-friendly domain file structure incomplete: {missing}")


def gate6_professional_patient_form(matrix: dict[str, dict[str, ET.Element]]) -> None:
    form = matrix.get("clinic.patient", {}).get("form")
    if form is None:
        fail("clinic.patient professional form is missing")
    required_tags = ["header", "sheet", "notebook"]
    for tag in required_tags:
        if form.find(f".//{tag}") is None:
            fail(f"clinic.patient form misses <{tag}>")
    if form.find(".//field[@name='stage_id'][@widget='statusbar']") is None:
        fail("clinic.patient form misses stage statusbar")
    object_buttons = {
        b.get("name")
        for b in form.findall(".//button[@type='object']")
        if b.get("name")
    }
    for method in {
        "action_set_registered",
        "action_print_patient_card",
        "action_open_attachments",
        "action_open_contact",
        "action_set_primary",
        "action_mark_resolved",
    }:
        if method not in object_buttons:
            fail(f"clinic.patient form misses expected enterprise button: {method}")


def gate7_8_9_views(matrix: dict[str, dict[str, ET.Element]]) -> None:
    for model in sorted(CUSTOM_MODELS):
        present = matrix.get(model, {})
        for view_type in ("search", "list", "form"):
            if view_type not in present:
                fail(f"{model}: required {view_type} view missing")

        search = present["search"]
        if len(search.findall(".//field")) < 1:
            fail(f"{model}: search view is placeholder/empty")

        list_view = present["list"]
        if len(list_view.findall(".//field")) < 2:
            fail(f"{model}: list view has insufficient decision-useful columns")
        if list_view.tag == "tree" or list_view.findall(".//tree"):
            fail(f"{model}: legacy <tree> view is forbidden")


def gate10_security() -> None:
    acl_path = ROOT / "security" / "ir.model.access.csv"
    with acl_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    acl_models = set()
    for row in rows:
        group = row.get("group_id:id", "")
        if group in {"base.group_public", "base.group_portal"}:
            fail("Public/portal ACL is forbidden for clinic_patient hardening")
        model_ref = row.get("model_id:id", "")
        if model_ref.startswith("model_"):
            acl_models.add(model_ref[len("model_"):].replace("_", "."))

    # Model XML IDs are ambiguous under underscore->dot reconstruction, so
    # compare exact expected model_id:id strings instead.
    expected_model_ids = {"model_" + model.replace(".", "_") for model in CUSTOM_MODELS}
    actual_model_ids = {row.get("model_id:id", "") for row in rows}
    missing_acl = sorted(expected_model_ids - actual_model_ids)
    if missing_acl:
        fail(f"ACL coverage missing model IDs: {missing_acl}")

    rule_doc = ET.parse(ROOT / "security" / "clinic_patient_security.xml").getroot()
    rule_model_ids = set()
    for record in rule_doc.findall(".//record[@model='ir.rule']"):
        model_field = record.find("./field[@name='model_id']")
        domain_field = record.find("./field[@name='domain_force']")
        groups_field = record.find("./field[@name='groups']")
        if model_field is None or domain_field is None or groups_field is None:
            fail("Company rule is missing model/domain/groups")
        rule_model_ids.add(model_field.get("ref"))
        domain_text = domain_field.text or ""
        if "company_ids" not in domain_text:
            fail(f"Record rule {record.get('id')} does not enforce company_ids")
        if "base.group_user" not in (groups_field.get("eval") or ""):
            fail(f"Record rule {record.get('id')} is not assigned to internal users")

    expected_rule_ids = {"model_" + model.replace(".", "_") for model in COMPANY_RULE_MODELS}
    missing_rules = sorted(expected_rule_ids - rule_model_ids)
    if missing_rules:
        fail(f"Company record-rule coverage missing model IDs: {missing_rules}")


def field_method_reference_check() -> None:
    """Validate compute/inverse/search method names declared on fields."""
    for path in sorted((ROOT / "models").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
            methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
            for item in cls.body:
                if not isinstance(item, ast.Assign) or not isinstance(item.value, ast.Call):
                    continue
                fn = item.value.func
                if not (
                    isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == "fields"
                ):
                    continue
                for kw in item.value.keywords:
                    if kw.arg not in {"compute", "inverse", "search"}:
                        continue
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        method = kw.value.value
                        if method and method not in methods:
                            fail(
                                f"{path.relative_to(ROOT)}:{cls.name} field references "
                                f"missing {kw.arg} method {method}()"
                            )


def gate12_style_and_odoo19(manifest: dict, manifest_files: list[Path]) -> None:
    # Compile/parse every active addon Python source.
    for path in sorted(ROOT.rglob("*.py")):
        if path.name.startswith("0"):
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            fail(f"Python compile failed for {path.relative_to(ROOT)}: {exc}")

    for path in sorted((ROOT / "models").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        if path.name == "res_users_inherit.py" and re.search(r"\bgroups_id\b", code):
            fail("Odoo 19 res.users runtime code may not use legacy groups_id; use group_ids")
        if "_sql_constraints" in code:
            fail(f"Legacy _sql_constraints remains active in {path.relative_to(ROOT)}")
        if re.search(r"\bdef\s+_name_search\s*\(", code):
            fail(f"Legacy _name_search remains active in {path.relative_to(ROOT)}")
        if re.search(r'["\'][^"\']*\btree\b[^"\']*["\']', code):
            fail(f"Legacy tree view_mode token remains active in {path.relative_to(ROOT)}")

    for path in manifest_files:
        if path.suffix.lower() == ".xml":
            root = ET.parse(path).getroot()
            if root.findall(".//tree"):
                fail(f"Legacy <tree> element loaded from {path.relative_to(ROOT)}")
            for field in root.findall(".//field[@name='view_mode']"):
                if "tree" in (field.text or ""):
                    fail(f"Legacy tree view_mode loaded from {path.relative_to(ROOT)}")

    field_method_reference_check()


def gate13_comments(manifest: dict) -> None:
    useful_comment_files = [
        ROOT / "models" / "patient.py",
        ROOT / "security" / "clinic_patient_security.xml",
        ROOT / "data" / "patient_stage_data.xml",
        ROOT / "AGENTS.md",
    ]
    for path in useful_comment_files:
        text = path.read_text(encoding="utf-8")
        if "#" not in text and "<!--" not in text:
            fail(f"Expected useful explanatory comments in {path.relative_to(ROOT)}")

    # Do not reload the old empty scaffold view as if it were production UX.
    if "views/views.xml" in manifest.get("data", []):
        fail("Legacy scaffold views/views.xml must not be the active enterprise UI")


def gate14_retry_limit() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "Maximum focused repair attempts per blocker/root-cause class: **3**" not in text:
        fail("Codex retry limit is not explicitly 3")
    if "STOP." not in text or "MOVE_FORWARD_READY: NO" not in text:
        fail("Codex stop/blocker-report behavior is incomplete")


def gate15_matrix() -> None:
    path = ROOT / "docs" / "CLINIC_PATIENT_ENTERPRISE_COMPLETENESS_MATRIX.md"
    if not path.is_file():
        fail("Enterprise completeness matrix missing")
    text = path.read_text(encoding="utf-8")
    for gate in REQUIRED_GATES:
        token = f"| {gate} |"
        if token not in text:
            fail(f"Enterprise completeness matrix misses Hard Gate {gate}")
    if "CLINIC_PATIENT_STATIC_MOVE_FORWARD_READY: YES" not in text:
        fail("Completeness matrix does not declare static readiness")
    if "CLINIC_PATIENT_MOVE_FORWARD_READY: PENDING" not in text:
        fail("Completeness matrix must keep final runtime state pending")


def run() -> int:
    checks = []
    try:
        manifest = load_manifest()
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        current = python_inventory()
        manifest_files = active_manifest_files(manifest)
        xml_docs = parsed_xml_files(manifest_files)
        matrix = view_matrix(xml_docs)

        gates = [
            ("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT", lambda: gate0_identity(manifest)),
            ("HARD_GATE_1_CODEX_BUKAN_ARCHITECT", gate1_codex_role),
            ("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", lambda: gate2_preservation(contract, current, manifest)),
            ("HARD_GATE_3_ENTERPRISE_COMPLETENESS", lambda: gate3_enterprise_completeness(xml_docs)),
            ("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY", gate4_inventory),
            ("HARD_GATE_5_HUMAN_FRIENDLY_STRUCTURE", gate5_human_structure),
            ("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN", lambda: gate6_professional_patient_form(matrix)),
            ("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL", lambda: gate7_8_9_views(matrix)),
            ("HARD_GATE_8_SEARCH_VIEW_WAJIB", lambda: gate7_8_9_views(matrix)),
            ("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY", lambda: gate7_8_9_views(matrix)),
            ("HARD_GATE_10_SECURITY_OVER_UI", gate10_security),
            ("HARD_GATE_12_HUMAN_FRIENDLY_CODE_STYLE", lambda: gate12_style_and_odoo19(manifest, manifest_files)),
            ("HARD_GATE_13_USEFUL_COMMENTS", lambda: gate13_comments(manifest)),
            ("HARD_GATE_14_CODEX_RETRY_LIMIT", gate14_retry_limit),
            ("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX", gate15_matrix),
        ]

        print("=" * 72)
        print("CLINIC_PATIENT ENTERPRISE DEVELOPMENT HARD GATE")
        print("=" * 72)
        for name, fn in gates:
            fn()
            checks.append(name)
            print(f"PASS: {name}")

        print("-" * 72)
        print(f"PASS: {len(checks)} / {len(gates)} OWNER HARD GATES")
        print("CLINIC_PATIENT_STATIC_MOVE_FORWARD_READY: YES")
        print("RUNTIME_GATE_REQUIRED: YES")
        print("CLINIC_PATIENT_MOVE_FORWARD_READY: PENDING")
        print("=" * 72)
        return 0

    except (GateFailure, FileNotFoundError, json.JSONDecodeError) as exc:
        print("=" * 72)
        print("CLINIC_PATIENT ENTERPRISE DEVELOPMENT HARD GATE")
        print("=" * 72)
        for name in checks:
            print(f"PASS: {name}")
        print(f"FAIL: {exc}")
        print("CLINIC_PATIENT_STATIC_MOVE_FORWARD_READY: NO")
        print("MOVE_FORWARD_READY: NO")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    sys.exit(run())
