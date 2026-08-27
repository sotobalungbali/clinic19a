
#!/usr/bin/env python3
"""Machine-checkable Enterprise Development Guardrail for clinic_triage_vitals."""

from __future__ import annotations

import ast
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "CLINIC_TRIAGE_VITALS_BASELINE_CONTRACT.json"
EXPECTED_ADDON = "clinic_triage_vitals"
EXPECTED_MODELS = {
    "clinic.triage.level",
    "clinic.triage.tag",
    "clinic.triage.session",
    "clinic.vitals.intake",
}
EXPECTED_VIEW_TYPES = {"search", "list", "form"}
EXPECTED_ACTIVE_IMPORTS = {
    "triage_level",
    "triage_tag",
    "triage_session",
    "vitals_intake",
    "patient_link",
}
MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3

results: list[tuple[str, bool, str]] = []


def gate(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def parse_manifest():
    return ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))


def parse_models():
    """Return local field/method metadata for active model files."""
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    active_files = [ROOT / contract["baseline_models"][m]["source_file"] for m in contract["baseline_models"]]
    models = {}
    for path in active_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            model_name = None
            inherit = None
            fields = {}
            methods = {}
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id == "_name":
                            model_name = literal(stmt.value)
                        elif target.id == "_inherit":
                            inherit = literal(stmt.value)
                        elif isinstance(stmt.value, ast.Call):
                            func = stmt.value.func
                            if (
                                isinstance(func, ast.Attribute)
                                and isinstance(func.value, ast.Name)
                                and func.value.id == "fields"
                            ):
                                args = [literal(arg) for arg in stmt.value.args]
                                kwargs = {kw.arg: ast.unparse(kw.value) for kw in stmt.value.keywords}
                                fields[target.id] = {
                                    "type": func.attr,
                                    "comodel": args[0] if args and isinstance(args[0], str) else None,
                                    "inverse": args[1] if len(args) > 1 and isinstance(args[1], str) else None,
                                    "kwargs": kwargs,
                                }
                elif isinstance(stmt, ast.FunctionDef):
                    methods[stmt.name] = {
                        "decorators": [ast.unparse(d) for d in stmt.decorator_list],
                        "args": [a.arg for a in stmt.args.args],
                    }
            effective = model_name or (inherit if isinstance(inherit, str) else None)
            if effective:
                models[effective] = {
                    "file": path,
                    "fields": fields,
                    "methods": methods,
                    "class_name": cls.name,
                }
    return models


def model_view_contract(models):
    """Validate fields/buttons in custom view records, including nested x2many lists."""
    errors = []
    magic_fields = {"id", "display_name", "create_date", "write_date", "create_uid", "write_uid"}

    def field_meta(model, field_name):
        if field_name in magic_fields:
            return {"type": "magic", "comodel": None}
        return models.get(model, {}).get("fields", {}).get(field_name)

    def walk(elem, model, location):
        for child in list(elem):
            if child.tag == "field":
                name = child.get("name")
                meta = field_meta(model, name) if name else None
                if name and not meta:
                    errors.append(f"{location}: missing field {model}.{name}")
                    child_model = model
                else:
                    child_model = (meta or {}).get("comodel") or model
                for sub in list(child):
                    if sub.tag in {"list", "form", "kanban"}:
                        walk(sub, child_model, f"{location}/{name}/{sub.tag}")
                    else:
                        walk(sub, child_model, f"{location}/{name}/{sub.tag}")
                continue
            if child.tag == "button" and child.get("type") == "object":
                method = child.get("name")
                if method and method not in models.get(model, {}).get("methods", {}):
                    errors.append(f"{location}: missing button method {model}.{method}")
            walk(child, model, f"{location}/{child.tag}")

    files = [
        ROOT / "views" / "triage_level_views.xml",
        ROOT / "views" / "triage_tag_views.xml",
        ROOT / "views" / "triage_session_views.xml",
        ROOT / "views" / "vitals_intake_views.xml",
        ROOT / "views" / "patient_triage_views.xml",
    ]
    for path in files:
        root = ET.parse(path).getroot()
        for record in root.findall(".//record[@model='ir.ui.view']"):
            model_el = record.find("field[@name='model']")
            arch_el = record.find("field[@name='arch']")
            model = model_el.text.strip() if model_el is not None and model_el.text else None
            if model not in models or arch_el is None:
                continue
            for arch in list(arch_el):
                walk(arch, model, f"{path.name}:{record.get('id')}")
    return errors


def main():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    # HARD GATE 0
    gate(
        "HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
        ROOT.name == EXPECTED_ADDON and contract.get("project") == "ClinicOne" and contract.get("addon") == EXPECTED_ADDON,
        f"root={ROOT}",
    )

    # HARD GATE 1 / 14 policy artifacts
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    role_ok = all(
        token in agents
        for token in [
            "LIMITED IMPLEMENTATION WORKER",
            "NOT ARCHITECT",
            "NOT SIMPLIFIER",
            "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3",
        ]
    )
    gate("HARD_GATE_1_CODEX_BUKAN_ARCHITECT", role_ok)
    gate("HARD_GATE_14_CODEX_RETRY_LIMIT", role_ok and MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER == 3)

    # Manifest + active import preservation.
    manifest = parse_manifest()
    gate(
        "MANIFEST_DEPENDENCY_PRESERVATION",
        manifest.get("depends") == contract["original_manifest_dependencies"],
        "manifest dependencies must remain exactly baseline",
    )
    init_text = (ROOT / "models" / "__init__.py").read_text(encoding="utf-8")
    imports = set(re.findall(r"^\s*from\s+\.\s+import\s+([a-zA-Z0-9_]+)", init_text, re.M))
    gate(
        "ACTIVE_IMPORT_GRAPH_PRESERVATION",
        imports == EXPECTED_ACTIVE_IMPORTS and not re.search(r"^\s*from\s+\.\s+import\s+encounter_link", init_text, re.M),
        f"imports={sorted(imports)}",
    )

    # Source/field/method preservation.
    models = parse_models()
    missing = []
    for model, baseline in contract["baseline_models"].items():
        current = models.get(model)
        if not current:
            missing.append(f"model {model}")
            continue
        missing_fields = set(baseline["fields"]) - set(current["fields"])
        missing_methods = set(baseline["methods"]) - set(current["methods"])
        if missing_fields:
            missing.append(f"{model} fields {sorted(missing_fields)}")
        if missing_methods:
            missing.append(f"{model} methods {sorted(missing_methods)}")
    gate("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", not missing, "; ".join(missing))

    # Python compile + XML parse.
    py_errors = []
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0") or "__pycache__" in path.parts:
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            py_errors.append(f"{path.relative_to(ROOT)}: {exc}")
    gate("PYTHON_COMPILE", not py_errors, "; ".join(py_errors))

    xml_errors = []
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        try:
            ET.parse(path)
        except Exception as exc:
            xml_errors.append(f"{path.relative_to(ROOT)}: {exc}")
    gate("XML_PARSE", not xml_errors, "; ".join(xml_errors))

    # Odoo 19 constraint migration.
    py_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "models").rglob("*.py")
        if not p.name.startswith("0")
    )
    constraint_count = py_text.count("models.Constraint(")
    gate(
        "ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE",
        "_sql_constraints" not in py_text and constraint_count >= contract["legacy_sql_constraints_expected_to_migrate"],
        f"models.Constraint={constraint_count}",
    )

    # Odoo 19 static API patterns on active source.
    active_text = "\n".join(
        (ROOT / data["source_file"]).read_text(encoding="utf-8")
        for data in contract["baseline_models"].values()
    )
    forbidden = {
        "legacy name_search args": re.search(r"def\s+name_search\([^)]*\bargs\s*=", active_text),
        "legacy read_group": re.search(r"(?<!_)\\.read_group\(", active_text),
        "deprecated check_access_rights": "check_access_rights(" in active_text,
        "tree view tag": "<tree" in "\n".join(p.read_text(encoding="utf-8") for p in ROOT.rglob("*.xml")),
    }
    gate(
        "ODOO19_STATIC_COMPATIBILITY_GATE",
        not any(bool(v) for v in forbidden.values()),
        ", ".join(k for k, v in forbidden.items() if v),
    )

    # Field/method collision and compute/inverse/search method contracts.
    collisions = []
    missing_compute_methods = []
    decorator_errors = []
    for model, meta in models.items():
        fields = set(meta["fields"])
        methods = set(meta["methods"])
        for name in fields & methods:
            collisions.append(f"{model}.{name}")
        for fname, field in meta["fields"].items():
            for keyword in ("compute", "inverse", "search"):
                raw = field["kwargs"].get(keyword)
                if not raw:
                    continue
                method = raw.strip("'\"")
                if method.startswith("_") and method not in methods:
                    missing_compute_methods.append(f"{model}.{fname} -> {keyword}={method}")
        inherited_roots = {"company_id"} if model == "clinic.patient" else set()
        valid_roots = fields | inherited_roots
        for method_name, method in meta["methods"].items():
            for decorator in method["decorators"]:
                if decorator.startswith("api.depends(") or decorator.startswith("api.constrains(") or decorator.startswith("api.onchange("):
                    for field_expr in re.findall(r"['\"]([a-zA-Z0-9_.]+)['\"]", decorator):
                        root = field_expr.split(".", 1)[0]
                        if root not in valid_roots:
                            decorator_errors.append(f"{model}.{method_name}: {field_expr}")
    gate("FIELD_METHOD_NAMESPACE_COLLISION_GATE", not collisions, ", ".join(collisions))
    gate("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE", not missing_compute_methods, ", ".join(missing_compute_methods))
    gate("CUSTOM_DECORATOR_FIELD_CONTRACT_GATE", not decorator_errors, ", ".join(decorator_errors))

    # Relational inverse contract for local x2many relationships.
    relation_errors = []
    for model, meta in models.items():
        for fname, field in meta["fields"].items():
            if field["type"] != "One2many":
                continue
            comodel, inverse = field["comodel"], field["inverse"]
            if comodel in models and inverse not in models[comodel]["fields"]:
                relation_errors.append(f"{model}.{fname} -> {comodel}.{inverse}")
    gate("RELATIONAL_MODEL_INVERSE_CONTRACT_GATE", not relation_errors, ", ".join(relation_errors))

    # XML field/button contract.
    view_errors = model_view_contract(models)
    gate("XML_MODEL_FIELD_BUTTON_CONTRACT_GATE", not view_errors, "; ".join(view_errors))

    # Searchable computed-field contract for domains used in custom search views.
    search_errors = []
    for view_file in [
        "triage_level_views.xml",
        "triage_tag_views.xml",
        "triage_session_views.xml",
        "vitals_intake_views.xml",
    ]:
        path = ROOT / "views" / view_file
        root = ET.parse(path).getroot()
        for record in root.findall(".//record[@model='ir.ui.view']"):
            model_el = record.find("field[@name='model']")
            arch_el = record.find("field[@name='arch']")
            model = model_el.text.strip() if model_el is not None and model_el.text else None
            if model not in models or arch_el is None:
                continue
            for filt in arch_el.findall(".//filter[@domain]"):
                for field_name in re.findall(r"\('([a-zA-Z0-9_]+)'\s*,", filt.get("domain", "")):
                    field = models[model]["fields"].get(field_name)
                    if not field:
                        continue
                    kwargs = field["kwargs"]
                    computed = "compute" in kwargs
                    stored = kwargs.get("store") == "True"
                    searchable = "search" in kwargs
                    if computed and not stored and not searchable:
                        search_errors.append(f"{model}.{field_name} in filter {filt.get('name')}")
    gate("ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE", not search_errors, ", ".join(search_errors))

    # View coverage + professional UI features.
    coverage = defaultdict(set)
    view_records = []
    for path in ROOT.glob("views/*.xml"):
        root = ET.parse(path).getroot()
        for record in root.findall(".//record[@model='ir.ui.view']"):
            model_el = record.find("field[@name='model']")
            arch_el = record.find("field[@name='arch']")
            if model_el is None or arch_el is None or not model_el.text:
                continue
            model = model_el.text.strip()
            for arch in list(arch_el):
                if arch.tag in EXPECTED_VIEW_TYPES:
                    coverage[model].add(arch.tag)
            view_records.append(record.get("id"))
    ui_missing = {
        model: sorted(EXPECTED_VIEW_TYPES - coverage.get(model, set()))
        for model in EXPECTED_MODELS
        if EXPECTED_VIEW_TYPES - coverage.get(model, set())
    }
    gate("HARD_GATE_8_SEARCH_VIEW_WAJIB", all("search" in coverage.get(m, set()) for m in EXPECTED_MODELS))
    gate("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY", all("list" in coverage.get(m, set()) for m in EXPECTED_MODELS))
    form_text = (ROOT / "views" / "triage_session_views.xml").read_text(encoding="utf-8")
    patient_view_text = (ROOT / "views" / "patient_triage_views.xml").read_text(encoding="utf-8")
    professional_form = (
        'widget="statusbar"' in form_text
        and 'name="action_start"' in form_text
        and 'name="action_complete"' in form_text
        and 'name="action_create_invoice"' in form_text
        and 'class="oe_stat_button"' in form_text
        and 'name="action_new_triage_session"' in patient_view_text
    )
    gate("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN", not ui_missing and professional_form, str(ui_missing))
    gate("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL", (ROOT / "docs" / "CLINIC_TRIAGE_VITALS_UI_UX_MATRIX.md").exists())

    # Security coverage.
    acl_models = set()
    with (ROOT / "security" / "ir.model.access.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ref = row["model_id:id"]
            if ref.startswith("model_"):
                acl_models.add(ref.removeprefix("model_").replace("_", "."))
            if row["group_id:id"] in {"base.group_public", "base.group_portal"}:
                gate("NO_PUBLIC_PORTAL_ACL", False, row["id"])
    expected_acl_refs = {f"model_{m.replace('.', '_')}" for m in EXPECTED_MODELS}
    acl_text = (ROOT / "security" / "ir.model.access.csv").read_text(encoding="utf-8")
    acl_ok = all(ref in acl_text for ref in expected_acl_refs)
    rules_text = (ROOT / "security" / "clinic_triage_vitals_rules.xml").read_text(encoding="utf-8")
    rule_ok = all(ref in rules_text for ref in expected_acl_refs)
    gate("HARD_GATE_10_SECURITY_OVER_UI", acl_ok and rule_ok and "base.group_public" not in acl_text and "base.group_portal" not in acl_text)

    # Manifest files / backup exclusion.
    missing_manifest_files = [
        rel for rel in manifest.get("data", []) + manifest.get("demo", [])
        if not (ROOT / rel).exists()
    ]
    gate("MANIFEST_FILE_REFERENCE_CONTRACT_GATE", not missing_manifest_files, ", ".join(missing_manifest_files))
    backup_files = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.name.startswith("0")]
    gate("BACKUP_FILE_EXCLUSION_GATE", not backup_files, ", ".join(backup_files))

    # Cross-addon patient-form resilience.
    #
    # A dependency can be installed in the database without being upgraded to
    # the exact source revision present on disk. Therefore a declarative
    # inherit_id pointing at clinic_patient.view_clinic_patient_form is not a
    # safe installation contract. The patient integration must be installed
    # defensively from post_init_hook instead.
    hooks_path = ROOT / "hooks.py"
    hooks_text = hooks_path.read_text(encoding="utf-8") if hooks_path.exists() else ""
    root_init_text = (ROOT / "__init__.py").read_text(encoding="utf-8")
    patient_template_loaded = "views/patient_triage_views.xml" in manifest.get("data", [])
    hook_contract_ok = all(
        [
            manifest.get("post_init_hook") == "_post_init_hook",
            not patient_template_loaded,
            hooks_path.exists(),
            "from .hooks import _post_init_hook" in root_init_text,
            "EXPECTED_PATIENT_FORM_XMLID = \"clinic_patient.view_clinic_patient_form\"" in hooks_text,
            '("model", "=", "clinic.patient")' in hooks_text,
            '("type", "=", "form")' in hooks_text,
            '("mode", "=", "primary")' in hooks_text,
            "raise_if_not_found=False" in hooks_text,
            "env.cr.savepoint()" in hooks_text,
        ]
    )
    gate(
        "CROSS_ADDON_PATIENT_VIEW_RUNTIME_RESILIENCE_GATE",
        hook_contract_ok,
        "patient form inheritance must be optional/post-init and not a manifest data blocker",
    )

    # Cross-addon XML-ID installation blocker gate.
    #
    # ClinicOne sibling addons can be installed from an older source revision.
    # Manifest-loaded XML therefore must not hard-reference presentation XML-IDs
    # owned by sibling ClinicOne addons.  Core Odoo IDs (for example base groups)
    # remain valid hard dependencies.
    sibling_ref_errors = []
    for rel in manifest.get("data", []):
        path = ROOT / rel
        if path.suffix != ".xml" or not path.exists():
            continue
        xml_text = path.read_text(encoding="utf-8")
        for xmlid in re.findall(
            r'(?:ref|parent|action|groups)="([^"]+)"',
            xml_text,
        ):
            for token in re.split(r"[, ]+", xmlid):
                token = token.strip()
                if (
                    token.startswith("clinic_")
                    and "." in token
                    and not token.startswith("clinic_triage_vitals.")
                ):
                    sibling_ref_errors.append(f"{rel}: {token}")

    menu_text = (ROOT / "views" / "clinic_triage_vitals_menus.xml").read_text(encoding="utf-8")
    menu_hook_ok = all(
        [
            'parent="clinic_patient.menu_root"' not in menu_text,
            'EXPECTED_PATIENT_MENU_XMLID = "clinic_patient.menu_root"' in hooks_text,
            'TRIAGE_ROOT_MENU_XMLID = "clinic_triage_vitals.menu_clinic_triage_root"' in hooks_text,
            "_ensure_triage_menu_parent(env)" in hooks_text,
            '_find_patient_root_menu(env)' in hooks_text,
        ]
    )
    gate(
        "CROSS_ADDON_XMLID_INSTALLATION_BLOCKER_GATE",
        not sibling_ref_errors and menu_hook_ok,
        "; ".join(sibling_ref_errors),
    )

    # Local XML ID and sequence contracts.
    xmlids = set()
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        root = ET.parse(path).getroot()
        for elem in root.iter():
            if elem.get("id"):
                xmlids.add(elem.get("id"))
    ref_errors = []
    for model, meta in models.items():
        source = meta["file"].read_text(encoding="utf-8")
        for local_id in re.findall(r'env\.ref\(["\']clinic_triage_vitals\.([a-zA-Z0-9_]+)["\']', source):
            if local_id not in xmlids:
                ref_errors.append(local_id)
    sequence_text = (ROOT / "data" / "triage_sequence.xml").read_text(encoding="utf-8")
    sequence_ok = "<field name=\"code\">clinic.triage.session</field>" in sequence_text
    gate("LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE", not ref_errors and sequence_ok, ", ".join(ref_errors))

    # Structural/documentation/code-style gates.
    gate("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY", (ROOT / "docs" / "CLINIC_TRIAGE_VITALS_STRUCTURAL_INVENTORY.md").exists())
    gate(
        "HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
        all((ROOT / "views" / f).exists() for f in [
            "triage_level_views.xml",
            "triage_tag_views.xml",
            "triage_session_views.xml",
            "vitals_intake_views.xml",
            "patient_triage_views.xml",
            "clinic_triage_vitals_menus.xml",
        ]),
    )
    gate("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY", not py_errors and not collisions)
    gate(
        "HARD_GATE_13_USEFUL_COMMENTS",
        "Odoo 19" in agents and (ROOT / "docs" / "CLINIC_TRIAGE_VITALS_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md").exists(),
    )
    gate(
        "HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
        (ROOT / "docs" / "CLINIC_TRIAGE_VITALS_ENTERPRISE_COMPLETENESS_MATRIX.md").exists(),
    )

    # Enterprise completeness is a composition of concrete underlying gates.
    supporting_names = {
        "PYTHON_COMPILE",
        "XML_PARSE",
        "ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE",
        "ODOO19_STATIC_COMPATIBILITY_GATE",
        "FIELD_METHOD_NAMESPACE_COLLISION_GATE",
        "FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE",
        "CUSTOM_DECORATOR_FIELD_CONTRACT_GATE",
        "RELATIONAL_MODEL_INVERSE_CONTRACT_GATE",
        "XML_MODEL_FIELD_BUTTON_CONTRACT_GATE",
        "ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE",
        "HARD_GATE_6_PROFESSIONAL_FORM_DESIGN",
        "HARD_GATE_8_SEARCH_VIEW_WAJIB",
        "HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY",
        "HARD_GATE_10_SECURITY_OVER_UI",
        "MANIFEST_FILE_REFERENCE_CONTRACT_GATE",
        "LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE",
        "CROSS_ADDON_PATIENT_VIEW_RUNTIME_RESILIENCE_GATE",
        "CROSS_ADDON_XMLID_INSTALLATION_BLOCKER_GATE",
        "BACKUP_FILE_EXCLUSION_GATE",
    }
    supporting_ok = all(ok for name, ok, _ in results if name in supporting_names)
    gate("HARD_GATE_3_ENTERPRISE_COMPLETENESS", supporting_ok)

    owner_gates = [
        "HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
        "HARD_GATE_1_CODEX_BUKAN_ARCHITECT",
        "HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION",
        "HARD_GATE_3_ENTERPRISE_COMPLETENESS",
        "HARD_GATE_4_FULL_STRUCTURAL_INVENTORY",
        "HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
        "HARD_GATE_6_PROFESSIONAL_FORM_DESIGN",
        "HARD_GATE_7_UI_UX_MATRIX_PER_MODEL",
        "HARD_GATE_8_SEARCH_VIEW_WAJIB",
        "HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY",
        "HARD_GATE_10_SECURITY_OVER_UI",
        "HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY",
        "HARD_GATE_13_USEFUL_COMMENTS",
        "HARD_GATE_14_CODEX_RETRY_LIMIT",
        "HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
    ]

    print("=" * 78)
    print("CLINIC_TRIAGE_VITALS ENTERPRISE DEVELOPMENT HARD GATE")
    print("=" * 78)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f" — {detail}" if detail and not ok else ""))

    result_map = {name: ok for name, ok, _ in results}
    owner_pass = sum(bool(result_map.get(name)) for name in owner_gates)
    print("-" * 78)
    print(f"OWNER_HARD_GATES_PASS: {owner_pass} / {len(owner_gates)}")

    overall = owner_pass == len(owner_gates) and all(ok for _, ok, _ in results)
    print()
    print(f"CLINIC_TRIAGE_VITALS_STATIC_MOVE_FORWARD_READY: {'YES' if overall else 'NO'}")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_TRIAGE_VITALS_MOVE_FORWARD_READY: PENDING")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
