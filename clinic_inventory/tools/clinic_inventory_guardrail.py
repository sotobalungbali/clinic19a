#!/usr/bin/env python3
"""Machine-checkable static hard gate for ClinicOne clinic_inventory.

This validator intentionally avoids importing Odoo so it can run from WSL
before a Windows Odoo runtime gate.
"""
from __future__ import annotations
from pathlib import Path
import ast
import csv
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "CLINIC_INVENTORY_BASELINE_CONTRACT.json"

BUSINESS_MODELS = {
    "clinic.treatment.product.usage",
    "clinic.treatment.product.usage.line",
    "clinic.inventory.adjustment",
    "clinic.inventory.adjustment.line",
    "clinic.patient.product.history",
    "clinic.doctor.allowed.product",
    "clinic.integration.event.log",
}
REQUIRED_DOCS = {
    "AGENTS.md",
    "docs/CLINIC_INVENTORY_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "docs/CLINIC_INVENTORY_BASELINE_CONTRACT.json",
    "docs/CLINIC_INVENTORY_STRUCTURAL_INVENTORY.md",
    "docs/CLINIC_INVENTORY_UI_UX_MATRIX.md",
    "docs/CLINIC_INVENTORY_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/CLINIC_INVENTORY_ODOO19_REVIEW.md",
}
REQUIRED_VIEW_FILES = {
    "views/treatment_product_usage_views.xml",
    "views/inventory_adjustment_views.xml",
    "views/patient_product_history_views.xml",
    "views/doctor_allowed_product_views.xml",
    "views/integration_event_log_views.xml",
    "views/core_inventory_extension_views.xml",
    "views/clinic_inventory_menus.xml",
}
FORBIDDEN_ACTIVE_PATTERNS = {
    "_sql_constraints": "legacy _sql_constraints",
    "qty_done": "removed stock.move.line qty_done",
    '"view_mode": "tree,form"': "legacy Python tree view_mode",
    '"type": "product"': "legacy Odoo product type='product'",
    'rec.type = "product"': "legacy Odoo product type='product'",
}

def result(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}: {label}" + (f" — {detail}" if detail else ""))
    return ok

def literal_manifest() -> dict:
    text = (ROOT / "__manifest__.py").read_text(encoding="utf-8")
    return ast.literal_eval(text[text.index("{"):])

def active_model_structure() -> dict:
    rows = {}
    for path in sorted((ROOT / "models").glob("*.py")):
        if path.name.startswith("0"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            model = inherit = None
            fields = set()
            methods = set()
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id in {"_name", "_inherit"}:
                            try:
                                value = ast.literal_eval(item.value)
                            except Exception:
                                value = None
                            if target.id == "_name":
                                model = value
                            else:
                                inherit = value
                        if isinstance(item.value, ast.Call):
                            fn = item.value.func
                            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "fields":
                                fields.add(target.id)
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(item.name)
            key = model or (f"EXTEND:{inherit}" if inherit else None)
            if key:
                rows[(path.name, node.name)] = {
                    "model": model,
                    "inherit": inherit,
                    "fields": fields,
                    "methods": methods,
                }
    return rows

def view_coverage() -> dict:
    coverage = {m: set() for m in BUSINESS_MODELS}
    for path in (ROOT / "views").glob("*.xml"):
        if path.name.startswith("0"):
            continue
        tree = ET.parse(path)
        for rec in tree.findall(".//record"):
            if rec.get("model") != "ir.ui.view":
                continue
            model_field = rec.find("./field[@name='model']")
            arch_field = rec.find("./field[@name='arch']")
            if model_field is None or arch_field is None:
                continue
            model = (model_field.text or "").strip()
            if model not in coverage or len(arch_field) == 0:
                continue
            root = arch_field[0]
            if root.tag in {"search", "list", "form"}:
                coverage[model].add(root.tag)
    return coverage


def searchable_computed_field_issues() -> list[str]:
    """Detect search-view domains that target non-searchable computed fields.

    This is a source-level regression check for custom Clinic Inventory models.
    Odoo validates search-view domains during module loading, so a non-stored
    computed field used in a filter must define ``search=...`` or be stored.
    """
    model_fields: dict[str, dict[str, dict[str, object]]] = {}

    for path in sorted((ROOT / "models").glob("*.py")):
        if path.name.startswith("0"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            model_name = None
            inherit_name = None
            for item in node.body:
                if not isinstance(item, ast.Assign) or len(item.targets) != 1:
                    continue
                target = item.targets[0]
                if not isinstance(target, ast.Name) or target.id not in {"_name", "_inherit"}:
                    continue
                try:
                    value = ast.literal_eval(item.value)
                except Exception:
                    value = None
                if target.id == "_name" and isinstance(value, str):
                    model_name = value
                elif target.id == "_inherit" and isinstance(value, str):
                    inherit_name = value

            effective_model = model_name or inherit_name
            if not effective_model:
                continue

            fields_by_name = model_fields.setdefault(effective_model, {})
            for item in node.body:
                if not isinstance(item, ast.Assign) or len(item.targets) != 1:
                    continue
                target = item.targets[0]
                call = item.value
                if not isinstance(target, ast.Name) or not isinstance(call, ast.Call):
                    continue
                func = call.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "fields"
                ):
                    continue

                props = {"compute": None, "search": None, "store": None}
                for keyword in call.keywords:
                    if keyword.arg not in props:
                        continue
                    try:
                        props[keyword.arg] = ast.literal_eval(keyword.value)
                    except Exception:
                        props[keyword.arg] = "<expr>"
                fields_by_name[target.id] = props

    issues = []
    for path in sorted((ROOT / "views").glob("*.xml")):
        if path.name.startswith("0"):
            continue
        try:
            xml_root = ET.parse(path).getroot()
        except Exception:
            continue

        for rec in xml_root.findall(".//record"):
            if rec.get("model") != "ir.ui.view":
                continue
            model_node = rec.find("./field[@name='model']")
            arch_node = rec.find("./field[@name='arch']")
            if model_node is None or arch_node is None:
                continue

            model = (model_node.text or "").strip()
            if model not in model_fields:
                continue

            for filter_node in arch_node.findall(".//filter"):
                domain_text = filter_node.get("domain") or ""
                for match in __import__("re").finditer(
                    r"\('([A-Za-z_][A-Za-z0-9_\.]*)'\s*,", domain_text
                ):
                    field_name = match.group(1).split(".", 1)[0]
                    props = model_fields[model].get(field_name)
                    if not props or not props["compute"]:
                        continue
                    if props["store"] is True or props["search"]:
                        continue
                    issues.append(
                        f"{path.relative_to(ROOT)}:{model}:{field_name}:"
                        "non-stored computed field has no search method"
                    )

    return issues


def field_method_namespace_collision_issues() -> list[str]:
    """Detect Python class names used both as Odoo fields and methods.

    A later method definition shadows a field assignment in the class namespace
    before Odoo's metaclass can register the field. This can make XML views fail
    with "Field ... does not exist" even though the source appears to define it.
    """
    issues = []
    for path in sorted((ROOT / "models").glob("*.py")):
        if path.name.startswith("0"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            field_names = set()
            method_names = set()
            for item in node.body:
                if isinstance(item, ast.Assign):
                    call = item.value
                    is_odoo_field = (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "fields"
                    )
                    if is_odoo_field:
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                field_names.add(target.id)
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.add(item.name)
            for name in sorted(field_names & method_names):
                issues.append(f"{path.relative_to(ROOT)}:{node.name}:{name}")
    return issues


def xml_custom_field_contract_issues() -> list[str]:
    """Ensure custom fields referenced by our XML exist on the local extension.

    This deliberately validates only ``clinic_*`` field names. Native Odoo field
    existence remains the responsibility of the real Odoo runtime gate.
    """
    fields_by_model: dict[str, set[str]] = {}

    for path in sorted((ROOT / "models").glob("*.py")):
        if path.name.startswith("0"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            model_name = None
            inherit_name = None
            local_fields = set()
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id in {"_name", "_inherit"}:
                            try:
                                value = ast.literal_eval(item.value)
                            except Exception:
                                value = None
                            if target.id == "_name" and isinstance(value, str):
                                model_name = value
                            elif target.id == "_inherit" and isinstance(value, str):
                                inherit_name = value
                        call = item.value
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and isinstance(call.func.value, ast.Name)
                            and call.func.value.id == "fields"
                        ):
                            local_fields.add(target.id)
            effective_model = model_name or inherit_name
            if effective_model:
                fields_by_model.setdefault(effective_model, set()).update(local_fields)

    issues = []
    for path in sorted((ROOT / "views").glob("*.xml")):
        if path.name.startswith("0"):
            continue
        try:
            xml_root = ET.parse(path).getroot()
        except Exception:
            continue
        for rec in xml_root.findall(".//record"):
            if rec.get("model") != "ir.ui.view":
                continue
            model_node = rec.find("./field[@name='model']")
            arch_node = rec.find("./field[@name='arch']")
            if model_node is None or arch_node is None:
                continue
            model = (model_node.text or "").strip()
            local = fields_by_model.get(model, set())
            for field_node in arch_node.iter("field"):
                if field_node is arch_node:
                    continue
                name = field_node.get("name")
                if name and name.startswith("clinic_") and name not in local:
                    issues.append(
                        f"{path.relative_to(ROOT)}:{rec.get('id')}:{model}:{name}"
                    )
    return issues


def custom_decorator_field_contract_issues() -> list[str]:
    """Validate custom ``clinic_*`` roots used in depends/constrains decorators."""
    issues = []
    for path in sorted((ROOT / "models").glob("*.py")):
        if path.name.startswith("0"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            local_fields = set()
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                call = item.value
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "fields"
                ):
                    continue
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        local_fields.add(target.id)

            for method in node.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for deco in method.decorator_list:
                    if not (
                        isinstance(deco, ast.Call)
                        and isinstance(deco.func, ast.Attribute)
                        and isinstance(deco.func.value, ast.Name)
                        and deco.func.value.id == "api"
                        and deco.func.attr in {"depends", "constrains"}
                    ):
                        continue
                    for arg in deco.args:
                        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                            continue
                        root = arg.value.split(".", 1)[0]
                        if root.startswith("clinic_") and root not in local_fields:
                            issues.append(
                                f"{path.relative_to(ROOT)}:{node.name}:{method.name}:{deco.func.attr}:{arg.value}"
                            )
    return issues



def native_product_boundary_issues() -> list[str]:
    """Protect native Odoo product semantics from ClinicOne defaults.

    ``product.template`` is a shared Odoo model used by many official addons and
    their demo data. Clinic-specific classification must therefore be opt-in.
    A truthy default on ``usage_type`` would silently classify every new Odoo
    product as clinical and can make unrelated official modules fail during
    installation.
    """
    path = ROOT / "models" / "product_template.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    issues = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ProductTemplate":
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "usage_type" for t in item.targets):
                continue
            call = item.value
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "fields"
                and call.func.attr == "Selection"
            ):
                issues.append("product.template.usage_type is not a fields.Selection")
                continue
            default_found = False
            default_value = None
            for kw in call.keywords:
                if kw.arg == "default":
                    default_found = True
                    try:
                        default_value = ast.literal_eval(kw.value)
                    except Exception:
                        default_value = "<dynamic>"
                    break
            if default_found and default_value not in (False, None):
                issues.append(
                    f"product.template.usage_type has invasive default={default_value!r}; "
                    "Clinic classification must be opt-in"
                )
    return issues


def env_model_proxy_isinstance_issues() -> list[str]:
    """Reject ``isinstance(record, self.env["model"])`` anti-patterns.

    ``self.env["stock.location"]`` and similar expressions return Odoo model
    recordsets/proxies, not Python classes. Passing such a value as argument #2
    to ``isinstance`` raises TypeError at runtime.
    """
    issues = []

    for path in sorted((ROOT / "models").glob("*.py")):
        if path.name.startswith("0"):
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            proxy_names = set()
            for node in ast.walk(function):
                if not isinstance(node, ast.Assign):
                    continue
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    continue

                value = node.value
                if not (
                    isinstance(value, ast.Subscript)
                    and isinstance(value.value, ast.Attribute)
                    and isinstance(value.value.value, ast.Name)
                    and value.value.value.id == "self"
                    and value.value.attr == "env"
                ):
                    continue

                proxy_names.add(node.targets[0].id)

            for node in ast.walk(function):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "isinstance"
                    and len(node.args) >= 2
                ):
                    continue

                second = node.args[1]
                if isinstance(second, ast.Name) and second.id in proxy_names:
                    issues.append(
                        f"{path.relative_to(ROOT)}:{function.name}:{node.lineno}:"
                        f"isinstance second arg {second.id} is an env model proxy"
                    )

    return issues

def main() -> int:
    failures = 0
    checks = []

    checks.append(("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
                   ROOT.name == "clinic_inventory",
                   f"folder={ROOT.name}"))

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    manifest = literal_manifest()

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    checks.append(("HARD_GATE_1_CODEX_BUKAN_ARCHITECT",
                   "LIMITED IMPLEMENTATION WORKER" in agents and "NOT:" in agents,
                   "AGENTS.md role contract"))

    # Baseline dependencies are architecture and must remain unchanged.
    checks.append(("MANIFEST_DEPENDENCY_PRESERVATION",
                   manifest.get("depends") == contract["baseline_dependencies"],
                   "dependencies must match baseline exactly"))

    missing_files = [p for p in contract["baseline_source_files"] if not (ROOT / p).exists()]
    checks.append(("BASELINE_SOURCE_FILE_PRESERVATION", not missing_files,
                   f"missing={missing_files[:5]}"))

    current = active_model_structure()
    missing_struct = []
    for row in contract["baseline_structure"]:
        key = (Path(row["file"]).name, row["class"])
        now = current.get(key)
        if not now:
            missing_struct.append(f"{key}:class")
            continue
        for field in row["fields"]:
            if field not in now["fields"]:
                missing_struct.append(f"{key}:field:{field}")
        for method in row["methods"]:
            if method not in now["methods"]:
                missing_struct.append(f"{key}:method:{method}")
    checks.append(("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", not missing_struct,
                   f"missing={missing_struct[:8]}"))

    # Compile Python and parse XML.
    compile_errors = []
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0") or "__pycache__" in path.parts:
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            compile_errors.append(f"{path.relative_to(ROOT)}:{exc}")
    checks.append(("PYTHON_COMPILE", not compile_errors, str(compile_errors[:3])))

    xml_errors = []
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        try:
            ET.parse(path)
        except Exception as exc:
            xml_errors.append(f"{path.relative_to(ROOT)}:{exc}")
    checks.append(("XML_PARSE", not xml_errors, str(xml_errors[:3])))

    # Runtime-regression gate (2026-08-13): a class attribute cannot be both an
    # Odoo field and a Python method. The later method shadows the field before
    # model construction and makes views report a missing field.
    namespace_collision_errors = field_method_namespace_collision_issues()
    checks.append(("FIELD_METHOD_NAMESPACE_COLLISION_GATE", not namespace_collision_errors,
                   f"collisions={namespace_collision_errors}"))

    # Cross-check ClinicOne-owned field names used by XML views against the
    # actual Python extension for the view model.
    xml_custom_field_errors = xml_custom_field_contract_issues()
    checks.append(("XML_CUSTOM_FIELD_MODEL_CONTRACT_GATE", not xml_custom_field_errors,
                   f"missing={xml_custom_field_errors[:8]}"))

    # Cross-check custom roots in api.depends/api.constrains so a typo cannot
    # survive static validation and fail later during Odoo registry setup.
    decorator_field_errors = custom_decorator_field_contract_issues()
    checks.append(("CUSTOM_DECORATOR_FIELD_CONTRACT_GATE", not decorator_field_errors,
                   f"missing={decorator_field_errors[:8]}"))


    # Runtime-regression gate (2026-08-21): Odoo env model lookups return
    # recordsets/proxies, not Python classes. They are invalid as isinstance()
    # argument #2 and caused the stock_delivery demo activation crash.
    env_proxy_isinstance_errors = env_model_proxy_isinstance_issues()
    checks.append((
        "ODOO_ENV_MODEL_PROXY_ISINSTANCE_GATE",
        not env_proxy_isinstance_errors,
        f"invalid={env_proxy_isinstance_errors}",
    ))

    # Runtime-regression gate (2026-08-19): ClinicOne extends the shared Odoo
    # product model and must not classify every native product as clinical.
    product_boundary_errors = native_product_boundary_issues()
    checks.append(("ODOO_NATIVE_PRODUCT_BOUNDARY_GATE", not product_boundary_errors,
                   f"invalid={product_boundary_errors}"))

    source_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "models").glob("*.py")
        if not p.name.startswith("0")
    )
    compatibility_errors = [label for pattern, label in FORBIDDEN_ACTIVE_PATTERNS.items() if pattern in source_text]
    checks.append(("ODOO19_STATIC_COMPATIBILITY", not compatibility_errors,
                   f"forbidden={compatibility_errors}"))

    # Runtime-regression gate (2026-08-12, repair attempt #2):
    # Odoo 19 validates search-view architecture when ir.ui.view is loaded.
    # Legacy search-group presentation attributes such as expand="0" must not
    # be reintroduced. Group-by filters themselves remain preserved.
    search_arch_errors = []
    for path in (ROOT / "views").glob("*.xml"):
        if path.name.startswith("0"):
            continue
        try:
            xml_root = ET.parse(path).getroot()
        except Exception:
            continue
        for search_node in xml_root.findall(".//search"):
            for group_node in search_node.findall(".//group"):
                forbidden_attrs = sorted(set(group_node.attrib) & {"expand"})
                if forbidden_attrs:
                    search_arch_errors.append(
                        f"{path.relative_to(ROOT)}:search/group:{','.join(forbidden_attrs)}"
                    )
    checks.append(("ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE", not search_arch_errors,
                   f"invalid={search_arch_errors}"))

    # Runtime-regression gate (2026-08-12): optional fallback fields must never
    # be hard-coded in api.depends/api.constrains. Odoo resolves decorator
    # dependencies while building the registry, before helper fallbacks can run.
    optional_dependency_errors = []
    for path in (ROOT / "models").glob("*.py"):
        if path.name.startswith("0"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute):
                    continue
                if not isinstance(deco.func.value, ast.Name) or deco.func.value.id != "api":
                    continue
                if deco.func.attr not in {"depends", "constrains"}:
                    continue
                for arg in deco.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        dependency_parts = arg.value.split(".")
                        if "life_date" in dependency_parts:
                            optional_dependency_errors.append(
                                f"{path.relative_to(ROOT)}:{node.name}:{deco.func.attr}:{arg.value}"
                            )
    checks.append(("OPTIONAL_FIELD_DECORATOR_DEPENDENCY_GATE", not optional_dependency_errors,
                   f"invalid={optional_dependency_errors}"))

    # Runtime-regression gate (2026-08-12, repair attempt #3):
    # Search views may only filter on stored fields or computed fields that
    # define an explicit search method.
    searchability_errors = searchable_computed_field_issues()
    checks.append(("ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE", not searchability_errors,
                   f"invalid={searchability_errors}"))

    # Guard against accidental activation of user backup files.
    manifest_text = (ROOT / "__manifest__.py").read_text(encoding="utf-8")
    backup_loaded = any(Path(item).name.startswith("0") for item in manifest.get("data", []) + manifest.get("demo", []))
    checks.append(("BACKUP_FILE_EXCLUSION", not backup_loaded and 'from . import 0' not in source_text,
                   "filenames beginning with 0 must stay excluded"))

    required_missing = [p for p in REQUIRED_DOCS | REQUIRED_VIEW_FILES if not (ROOT / p).exists()]
    checks.append(("HARD_GATE_3_ENTERPRISE_COMPLETENESS", not required_missing,
                   f"missing={required_missing}"))
    checks.append(("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY",
                   (ROOT / "docs/CLINIC_INVENTORY_STRUCTURAL_INVENTORY.md").exists(), "inventory document"))
    checks.append(("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
                   len(list((ROOT / "views").glob("*_views.xml"))) >= 5, "UI split by business surface"))
    checks.append(("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN",
                   'widget="statusbar"' in "\n".join(p.read_text() for p in (ROOT/"views").glob("*.xml"))
                   and 'oe_button_box' in "\n".join(p.read_text() for p in (ROOT/"views").glob("*.xml")),
                   "statusbar + smart/action surfaces"))

    coverage = view_coverage()
    expected = {"search", "list", "form"}
    ux_missing = {m: sorted(expected - got) for m, got in coverage.items() if expected - got}
    checks.append(("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL",
                   (ROOT / "docs/CLINIC_INVENTORY_UI_UX_MATRIX.md").exists() and not ux_missing,
                   f"coverage_missing={ux_missing}"))
    checks.append(("HARD_GATE_8_SEARCH_VIEW_WAJIB",
                   all("search" in got for got in coverage.values()), "7/7 user-facing persistent models"))
    checks.append(("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY",
                   all("list" in got for got in coverage.values()), "7/7 user-facing persistent models"))

    # ACL coverage and security: no portal/public grant.
    acl_path = ROOT / "security/ir.model.access.csv"
    acl_text = acl_path.read_text(encoding="utf-8") if acl_path.exists() else ""
    acl_ok = all("model_" + m.replace(".", "_") in acl_text for m in BUSINESS_MODELS)
    no_public_portal = "base.group_public" not in acl_text and "base.group_portal" not in acl_text
    rules_text = (ROOT / "security/clinic_inventory_rules.xml").read_text(encoding="utf-8")
    rule_ok = all(m.replace(".", "_") in rules_text for m in BUSINESS_MODELS)
    checks.append(("HARD_GATE_10_SECURITY_OVER_UI", acl_ok and no_public_portal and rule_ok,
                   "ACL + company rules; no public/portal grant"))

    checks.append(("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY",
                   (ROOT / "AGENTS.md").exists() and len(list((ROOT / "views").glob("*.xml"))) >= 6,
                   "bounded files and named sections"))
    checks.append(("HARD_GATE_13_USEFUL_COMMENTS",
                   "business" in source_text.lower() or "clinic" in source_text.lower(),
                   "existing/new comments document intent"))
    checks.append(("HARD_GATE_14_CODEX_RETRY_LIMIT",
                   contract.get("max_focused_repair_attempts_per_blocker") == 3
                   and "Maximum focused repair attempts per blocker/root-cause class: **3**" in agents,
                   "3-attempt hard stop"))
    checks.append(("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
                   (ROOT / "docs/CLINIC_INVENTORY_ENTERPRISE_COMPLETENESS_MATRIX.md").exists(),
                   "separate enterprise matrix"))

    for label, ok, detail in checks:
        if not result(label, ok, detail):
            failures += 1

    owner_gate_labels = [x[0] for x in checks if x[0].startswith("HARD_GATE_")]
    owner_pass = sum(1 for label, ok, _ in checks if label.startswith("HARD_GATE_") and ok)
    print("-" * 78)
    print(f"OWNER_HARD_GATES_PASS: {owner_pass} / 15")
    if failures:
        print("CLINIC_INVENTORY_STATIC_MOVE_FORWARD_READY: NO")
        return 1
    print("CLINIC_INVENTORY_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_INVENTORY_MOVE_FORWARD_READY: PENDING")
    return 0

if __name__ == "__main__":
    sys.exit(main())

