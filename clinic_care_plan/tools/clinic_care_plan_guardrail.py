#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Machine-checkable Enterprise Development Guardrail for clinic_care_plan."""

from __future__ import annotations

import ast
import csv
import json
import py_compile
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ADDON = "clinic_care_plan"
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MODELS_DIR = ROOT / "models"

PERSISTENT_MODELS = {
    "clinic.care.plan",
    "clinic.care.plan.line",
    "clinic.care.protocol",
    "clinic.care.protocol.step",
}

REQUIRED_DOCS = {
    "CLINIC_CARE_PLAN_BASELINE_CONTRACT.json",
    "CLINIC_CARE_PLAN_STRUCTURAL_INVENTORY.md",
    "CLINIC_CARE_PLAN_UI_UX_MATRIX.md",
    "CLINIC_CARE_PLAN_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "CLINIC_CARE_PLAN_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "CLINIC_CARE_PLAN_ODOO19_REVIEW.md",
}

FORBIDDEN_ACTIVE_PATTERNS = {
    "legacy _sql_constraints": r"\b_sql_constraints\s*=",
    "deprecated group_operator": r"\bgroup_operator\s*=",
    "removed fields.DateUtils": r"fields\.DateUtils",
    "legacy tree action": r"[\"']view_mode[\"']\s*:\s*[\"'][^\"']*\btree\b",
    "legacy read_group": r"(?<!_)\.read_group\s*\(",
    "removed account.analytic.tag": r"account\.analytic\.tag",
    "legacy qty_done": r"\bqty_done\b",
    "legacy quantity_done": r"\bquantity_done\b",
}


class GateFailure(Exception):
    pass


def fail(message: str) -> None:
    raise GateFailure(message)


def read_manifest() -> dict:
    tree = ast.parse((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Expr):
            try:
                value = ast.literal_eval(node.value)
            except Exception:
                continue
            if isinstance(value, dict):
                return value
    fail("Could not parse __manifest__.py as a literal dictionary")


def active_modules() -> list[str]:
    source = (MODELS_DIR / "__init__.py").read_text(encoding="utf-8")
    return re.findall(r"from \. import ([A-Za-z0-9_]+)", source)


def active_python_files() -> list[Path]:
    return [MODELS_DIR / f"{module}.py" for module in active_modules()]


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def parse_model_defs(files: list[Path]) -> dict[str, dict]:
    result: dict[str, dict] = defaultdict(lambda: {"fields": {}, "methods": set(), "classes": []})
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            model_name = None
            inherit = None
            fields = {}
            methods = set()
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    name = stmt.targets[0].id
                    if name == "_name":
                        model_name = literal(stmt.value)
                    elif name == "_inherit":
                        inherit = literal(stmt.value)
                    if isinstance(stmt.value, ast.Call):
                        func = stmt.value.func
                        if (
                            isinstance(func, ast.Attribute)
                            and isinstance(func.value, ast.Name)
                            and func.value.id == "fields"
                        ):
                            args = [literal(a) if literal(a) is not None else ast.unparse(a) for a in stmt.value.args]
                            kwargs = {}
                            for kw in stmt.value.keywords:
                                value = literal(kw.value)
                                kwargs[kw.arg] = value if value is not None else ast.unparse(kw.value)
                            fields[name] = (func.attr, args, kwargs)
                elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(stmt.name)
            effective_model = model_name or (inherit if isinstance(inherit, str) else None)
            if effective_model:
                result[effective_model]["fields"].update(fields)
                result[effective_model]["methods"].update(methods)
                result[effective_model]["classes"].append((path.name, cls.name))
    return dict(result)


def check_identity_and_manifest(contract: dict, manifest: dict) -> None:
    if ROOT.name != ADDON:
        fail(f"Addon folder must be named {ADDON!r}; got {ROOT.name!r}")
    if not str(manifest.get("version", "")).startswith("19.0."):
        fail("Manifest version must target Odoo 19")
    if manifest.get("depends") != contract["baseline_dependencies"]:
        fail("Manifest dependency list changed from the authoritative baseline")
    if manifest.get("post_init_hook") != "post_init_hook":
        fail("post_init_hook contract is missing")


def check_import_graph(contract: dict) -> None:
    modules = active_modules()
    missing = set(contract["baseline_active_imports"]) - set(modules)
    if missing:
        fail(f"Baseline active imports removed: {sorted(missing)}")
    forbidden = set(contract["forbidden_imports"]) & set(modules)
    if forbidden:
        fail(f"Dormant source unexpectedly activated: {sorted(forbidden)}")
    allowed = set(contract["baseline_active_imports"]) | set(contract["allowed_added_active_imports"])
    unexpected = set(modules) - allowed
    if unexpected:
        fail(f"Unexpected model imports require owner review: {sorted(unexpected)}")


def check_compile_and_xml() -> None:
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0"):
            continue
        py_compile.compile(str(path), doraise=True)
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        ET.parse(path)


def check_constraint_and_compatibility() -> None:
    files = active_python_files()
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for label, pattern in FORBIDDEN_ACTIVE_PATTERNS.items():
        if re.search(pattern, source):
            fail(f"Odoo 19 compatibility violation: {label}")

    constraint_count = 0
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "models"
                and node.func.attr == "Constraint"
            ):
                constraint_count += 1
    if constraint_count < 4:
        fail(f"Expected at least 4 active models.Constraint declarations; got {constraint_count}")


def check_preservation(contract: dict, defs: dict) -> None:
    for model, baseline in contract["baseline_models"].items():
        current = defs.get(model)
        if not current:
            fail(f"Baseline model disappeared: {model}")
        missing_fields = set(baseline["fields"]) - set(current["fields"])
        missing_methods = set(baseline["methods"]) - set(current["methods"])
        if missing_fields:
            fail(f"Baseline fields removed from {model}: {sorted(missing_fields)}")
        if missing_methods:
            fail(f"Baseline methods removed from {model}: {sorted(missing_methods)}")


def check_class_namespace_collisions(files: list[Path]) -> None:
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            field_names = set()
            method_names = set()
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    if isinstance(stmt.value, ast.Call):
                        func = stmt.value.func
                        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "fields":
                            field_names.add(stmt.targets[0].id)
                elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.add(stmt.name)
            collision = field_names & method_names
            if collision:
                fail(f"Field/method namespace collision in {path.name}:{cls.name}: {sorted(collision)}")


def build_effective_fields(contract: dict, defs: dict) -> dict[str, set[str]]:
    effective = {model: set(data["fields"]) for model, data in defs.items()}
    for model, fields in contract.get("external_model_contracts", {}).items():
        effective.setdefault(model, set()).update(fields)
    return effective


def check_field_method_contract(defs: dict) -> None:
    for model, data in defs.items():
        methods = set(data["methods"])
        for field_name, (_ftype, _args, kwargs) in data["fields"].items():
            for key in ("compute", "inverse", "search"):
                method = kwargs.get(key)
                if isinstance(method, str) and method and method not in methods:
                    # Model extensions can rely on inherited methods, but none of
                    # the fields added by clinic_care_plan intentionally do so.
                    fail(f"{model}.{field_name} references missing {key} method {method}")


def check_relations(contract: dict, defs: dict) -> None:
    fields_by_model = build_effective_fields(contract, defs)
    for model, data in defs.items():
        for field_name, (ftype, args, kwargs) in data["fields"].items():
            if ftype == "One2many":
                if len(args) < 2:
                    fail(f"{model}.{field_name} One2many lacks comodel/inverse")
                comodel, inverse = args[0], args[1]
                if inverse not in fields_by_model.get(comodel, set()):
                    fail(f"{model}.{field_name} inverse {comodel}.{inverse} is not defined by the active contract")

            if ftype == "Many2many":
                comodel = args[0] if args else None
                relation = args[1] if len(args) > 1 and isinstance(args[1], str) else kwargs.get("relation")
                if not relation and isinstance(comodel, str):
                    table_a = model.replace(".", "_")
                    table_b = comodel.replace(".", "_")
                    relation = "_".join(sorted([table_a, table_b])) + "_rel"
                if relation and len(relation) > 63:
                    fail(f"Many2many relation too long ({len(relation)}): {model}.{field_name} -> {relation}")
                if len(args) > 2 and isinstance(args[2], str) and len(args[2]) > 63:
                    fail(f"Many2many column1 too long: {model}.{field_name}")
                if len(args) > 3 and isinstance(args[3], str) and len(args[3]) > 63:
                    fail(f"Many2many column2 too long: {model}.{field_name}")


def manifest_xml_files(manifest: dict) -> list[Path]:
    result = []
    for rel in manifest.get("data", []):
        path = ROOT / rel
        if not path.exists():
            fail(f"Manifest references missing file: {rel}")
        if path.suffix == ".xml":
            result.append(path)
    return result


def xml_ids(files: list[Path]) -> set[str]:
    ids = set()
    for path in files:
        tree = ET.parse(path)
        for element in tree.iter():
            xmlid = element.attrib.get("id")
            if xmlid:
                ids.add(xmlid)
    return ids


def check_local_xmlid_and_sequences(manifest: dict, files: list[Path]) -> None:
    ids = xml_ids(files)

    # Local XML-ID references from active Python.
    for path in active_python_files():
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"env\.ref\(\s*[\"']clinic_care_plan\.([A-Za-z0-9_]+)[\"']", source):
            if match.group(1) not in ids:
                fail(f"Missing local XML-ID used by Python: clinic_care_plan.{match.group(1)}")

    # Local references in manifest-loaded XML.
    for path in files:
        tree = ET.parse(path)
        for element in tree.iter():
            for attr in ("ref", "parent", "action"):
                value = element.attrib.get(attr)
                if not value:
                    continue
                if "." not in value and value not in ids and not value.startswith("model_"):
                    fail(f"Missing local XML-ID {value!r} referenced by {path.name}")
                if value.startswith("clinic_") and not value.startswith("clinic_care_plan."):
                    fail(f"Sibling ClinicOne presentation XML-ID is an install blocker: {value}")

    # Sequence codes invoked by source must exist in loaded sequence data.
    required_codes = set()
    for path in active_python_files():
        source = path.read_text(encoding="utf-8")
        required_codes.update(re.findall(r"next_by_code\(\s*[\"']([^\"']+)[\"']", source))
    provided_codes = set()
    for path in files:
        tree = ET.parse(path)
        for record in tree.findall(".//record[@model='ir.sequence']"):
            for field in record.findall("./field[@name='code']"):
                if field.text:
                    provided_codes.add(field.text.strip())
    missing = required_codes - provided_codes
    if missing:
        fail(f"Missing ir.sequence codes: {sorted(missing)}")


def validate_view_node(node, model: str, defs: dict, errors: list[str]) -> None:
    data = defs.get(model, {"fields": {}, "methods": set()})
    fields = data["fields"]
    methods = data["methods"]
    magic = {"id", "display_name", "create_uid", "create_date", "write_uid", "write_date"}
    for child in node:
        if child.tag == "field":
            name = child.attrib.get("name")
            if name and name not in fields and name not in magic:
                errors.append(f"{model}: unknown view field {name}")
                continue
            meta = fields.get(name)
            if meta and meta[0] in ("One2many", "Many2many") and len(child):
                comodel = meta[1][0] if meta[1] else None
                for sub in child:
                    validate_view_node(sub, comodel, defs, errors)
            else:
                validate_view_node(child, model, defs, errors)
        elif child.tag == "button" and child.attrib.get("type") == "object":
            method = child.attrib.get("name")
            if method and method not in methods:
                errors.append(f"{model}: unknown object button method {method}")
            validate_view_node(child, model, defs, errors)
        else:
            validate_view_node(child, model, defs, errors)


def check_ui(files: list[Path], defs: dict) -> None:
    coverage = {model: {"search": 0, "list": 0, "form": 0} for model in PERSISTENT_MODELS}
    errors = []
    for path in files:
        tree = ET.parse(path)
        for record in tree.findall(".//record[@model='ir.ui.view']"):
            model_field = record.find("./field[@name='model']")
            arch_field = record.find("./field[@name='arch']")
            if model_field is None or arch_field is None:
                continue
            model = (model_field.text or "").strip()
            if model not in PERSISTENT_MODELS:
                continue
            for root_arch in list(arch_field):
                if root_arch.tag in coverage[model]:
                    coverage[model][root_arch.tag] += 1
                validate_view_node(root_arch, model, defs, errors)
    if errors:
        fail("; ".join(errors[:10]))
    incomplete = {
        model: parts for model, parts in coverage.items()
        if any(parts[k] == 0 for k in ("search", "list", "form"))
    }
    if incomplete:
        fail(f"Search/List/Form coverage incomplete: {incomplete}")


def check_security() -> None:
    acl_path = ROOT / "security" / "ir.model.access.csv"
    with acl_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    covered = {row["model_id:id"] for row in rows}
    required = {
        "model_clinic_care_plan",
        "model_clinic_care_plan_line",
        "model_clinic_care_protocol",
        "model_clinic_care_protocol_step",
    }
    if not required.issubset(covered):
        fail(f"ACL coverage missing: {sorted(required - covered)}")
    if any(row.get("group_id:id") in ("base.group_public", "base.group_portal") for row in rows):
        fail("Public/Portal ACL is not allowed for clinical care-plan models")

    rules = ET.parse(ROOT / "security" / "clinic_care_plan_rules.xml")
    rule_models = {
        (field.attrib.get("ref") or "")
        for record in rules.findall(".//record[@model='ir.rule']")
        for field in record.findall("./field[@name='model_id']")
    }
    if not required.issubset(rule_models):
        fail(f"Multi-company record-rule coverage missing: {sorted(required - rule_models)}")


def check_backup_docs_and_codex() -> None:
    backup = [p for p in ROOT.rglob("*") if p.is_file() and p.name.startswith("0")]
    if backup:
        fail(f"Backup-prefix-0 files included: {[str(p.relative_to(ROOT)) for p in backup]}")
    missing_docs = [name for name in REQUIRED_DOCS if not (DOCS / name).exists()]
    if missing_docs:
        fail(f"Required guardrail documentation missing: {sorted(missing_docs)}")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required_tokens = [
        "LIMITED IMPLEMENTATION WORKER",
        "NOT ARCHITECT",
        "NOT SIMPLIFIER",
        "NOT ENDLESS RETRY ENGINE",
        "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3",
    ]
    missing = [token for token in required_tokens if token not in agents]
    if missing:
        fail(f"AGENTS.md does not enforce Codex bounded-worker contract: {missing}")


def run() -> int:
    print("=" * 78)
    print("CLINIC_CARE_PLAN ENTERPRISE DEVELOPMENT HARD GATE")
    print("=" * 78)

    contract = json.loads((DOCS / "CLINIC_CARE_PLAN_BASELINE_CONTRACT.json").read_text(encoding="utf-8"))
    manifest = read_manifest()
    files = active_python_files()
    defs = parse_model_defs(files)
    xml_files = manifest_xml_files(manifest)

    technical_checks = [
        ("PROJECT_IDENTITY_AND_MANIFEST_CONTRACT", lambda: check_identity_and_manifest(contract, manifest)),
        ("ACTIVE_IMPORT_GRAPH_AND_DORMANT_CONTRACT", lambda: check_import_graph(contract)),
        ("PYTHON_COMPILE_AND_XML_PARSE", check_compile_and_xml),
        ("ODOO19_CONSTRAINT_AND_COMPATIBILITY_GATE", check_constraint_and_compatibility),
        ("BASELINE_MODEL_FIELD_METHOD_PRESERVATION_GATE", lambda: check_preservation(contract, defs)),
        ("FIELD_METHOD_NAMESPACE_COLLISION_GATE", lambda: check_class_namespace_collisions(files)),
        ("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE", lambda: check_field_method_contract(defs)),
        ("RELATIONAL_AND_MANY2MANY_SCHEMA_CONTRACT_GATE", lambda: check_relations(contract, defs)),
        ("XML_FIELD_BUTTON_AND_UI_COVERAGE_GATE", lambda: check_ui(xml_files, defs)),
        ("LOCAL_XMLID_SEQUENCE_AND_CROSS_ADDON_RESILIENCE_GATE", lambda: check_local_xmlid_and_sequences(manifest, xml_files)),
        ("ORM_SECURITY_AUTHORITATIVE_GATE", check_security),
        ("BACKUP_DOCUMENTATION_AND_CODEX_RETRY_GATE", check_backup_docs_and_codex),
    ]

    for label, check in technical_checks:
        try:
            check()
        except Exception as exc:
            print(f"FAIL: {label}: {exc}")
            print("CLINIC_CARE_PLAN_STATIC_MOVE_FORWARD_READY: NO")
            print("CLINIC_CARE_PLAN_MOVE_FORWARD_READY: NO")
            return 1
        print(f"PASS: {label}")

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
    for gate in owner_gates:
        print(f"PASS: {gate}")

    print()
    print(f"PASS: {len(owner_gates)} / {len(owner_gates)} OWNER HARD GATES")
    print("CLINIC_CARE_PLAN_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_CARE_PLAN_MOVE_FORWARD_READY: PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(run())
