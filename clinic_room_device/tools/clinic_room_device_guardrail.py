#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
CONTRACT_PATH = ROOT / "docs/CLINIC_ROOM_DEVICE_BASELINE_CONTRACT.json"

PERSISTENT_MODELS = {
    "clinic.room",
    "clinic.room.type",
    "clinic.device",
    "clinic.device.category",
    "clinic.room.device.assignment",
    "clinic.room.availability",
    "clinic.device.movement",
    "clinic.room.session",
}
COMMON_ORM_FIELDS = {
    "id", "display_name", "create_date", "create_uid", "write_date", "write_uid",
    "message_ids", "message_follower_ids", "message_partner_ids",
    "message_attachment_count", "activity_ids", "activity_state", "activity_user_id",
    "activity_type_id", "activity_date_deadline", "__last_update",
}
FIELD_TYPES = {
    "Char", "Text", "Html", "Integer", "Float", "Boolean", "Date", "Datetime",
    "Selection", "Many2one", "One2many", "Many2many", "Image", "Binary",
    "Monetary", "Reference",
}
REQUIRED_DOCS = {
    "AGENTS.md",
    "docs/CLINIC_ROOM_DEVICE_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "docs/CLINIC_ROOM_DEVICE_BASELINE_CONTRACT.json",
    "docs/CLINIC_ROOM_DEVICE_STRUCTURAL_INVENTORY.md",
    "docs/CLINIC_ROOM_DEVICE_UI_UX_MATRIX.md",
    "docs/CLINIC_ROOM_DEVICE_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/CLINIC_ROOM_DEVICE_ODOO19_REVIEW.md",
}
REQUIRED_VIEW_FILES = {
    "views/room_views.xml",
    "views/device_views.xml",
    "views/assignment_views.xml",
    "views/availability_views.xml",
    "views/movement_views.xml",
    "views/room_session_views.xml",
    "views/clinic_room_device_menus.xml",
}


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def attr_name(node):
    if isinstance(node, ast.Attribute):
        base = attr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def is_field_call(node):
    return (
        isinstance(node, ast.Call)
        and attr_name(node.func).startswith("fields.")
        and attr_name(node.func).split(".")[-1] in FIELD_TYPES
    )


def parse_classes(paths):
    rows = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            model = None
            inherit = None
            fields = {}
            methods = set()
            constraints = 0
            for item in cls.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id == "_name":
                            model = literal(item.value)
                        elif target.id == "_inherit":
                            inherit = literal(item.value)
                        if is_field_call(item.value):
                            typ = attr_name(item.value.func).split(".")[-1]
                            meta = {
                                "type": typ,
                                "compute": None,
                                "inverse": None,
                                "search": None,
                                "store": None,
                                "comodel": None,
                                "inverse_name": None,
                            }
                            if item.value.args and typ in {"Many2one", "One2many", "Many2many"}:
                                meta["comodel"] = literal(item.value.args[0])
                            if typ == "One2many" and len(item.value.args) > 1:
                                meta["inverse_name"] = literal(item.value.args[1])
                            for kw in item.value.keywords:
                                if kw.arg in meta:
                                    meta[kw.arg] = literal(kw.value)
                                elif kw.arg == "comodel_name":
                                    meta["comodel"] = literal(kw.value)
                                elif kw.arg == "inverse_name":
                                    meta["inverse_name"] = literal(kw.value)
                            fields[target.id] = meta
                        if isinstance(item.value, ast.Call) and attr_name(item.value.func) == "models.Constraint":
                            constraints += 1
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(item.name)
            if model or inherit:
                rows.append({
                    "file": str(path.relative_to(ROOT)),
                    "class": cls.name,
                    "model": model,
                    "inherit": inherit,
                    "fields": fields,
                    "methods": methods,
                    "constraints": constraints,
                })
    return rows


def model_of(row):
    if isinstance(row["model"], str):
        return row["model"]
    if isinstance(row["inherit"], str):
        return row["inherit"]
    return None


def registry(rows):
    result = {}
    for row in rows:
        model = model_of(row)
        if not model:
            continue
        bucket = result.setdefault(model, {"fields": {}, "methods": set(), "rows": []})
        bucket["fields"].update(row["fields"])
        bucket["methods"].update(row["methods"])
        bucket["rows"].append(row)
    return result


def load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_manifest():
    return ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))


def active_paths(contract):
    return [ROOT / "models" / f"{name}.py" for name in contract["active_model_imports"]]


def preservation_issues(contract):
    paths = [ROOT / rel for rel in contract["structural_inventory"] if (ROOT / rel).exists()]
    actual_rows = parse_classes(paths)
    by_key = {(r["file"], r["class"]): r for r in actual_rows}
    issues = []
    for rel, expected_rows in contract["structural_inventory"].items():
        for expected in expected_rows:
            actual = by_key.get((rel, expected["class"]))
            if not actual:
                issues.append(f"{rel}:{expected['class']}:missing-class")
                continue
            for field in expected.get("fields", []):
                if field not in actual["fields"]:
                    issues.append(f"{rel}:{expected['class']}:missing-field:{field}")
            for method in expected.get("methods", []):
                if method not in actual["methods"]:
                    issues.append(f"{rel}:{expected['class']}:missing-method:{method}")
    return issues


def namespace_collision_issues(paths):
    issues = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            field_names = set()
            method_names = set()
            for item in cls.body:
                if isinstance(item, ast.Assign) and is_field_call(item.value):
                    field_names.update(t.id for t in item.targets if isinstance(t, ast.Name))
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.add(item.name)
            for name in sorted(field_names & method_names):
                issues.append(f"{path.relative_to(ROOT)}:{cls.name}:{name}")
    return issues


def callable_issues(reg):
    issues = []
    for model, bucket in reg.items():
        for fname, meta in bucket["fields"].items():
            for key in ("compute", "inverse", "search"):
                value = meta.get(key)
                if isinstance(value, str) and value and value not in bucket["methods"]:
                    issues.append(f"{model}:{fname}:{key}:{value}")
    return issues


def decorator_dependency_issues(paths, reg):
    issues = []
    parsed = parse_classes(paths)
    by_key = {(r["file"], r["class"]): r for r in parsed}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            row = by_key.get((str(path.relative_to(ROOT)), cls.name))
            model = model_of(row) if row else None
            local_fields = set(reg.get(model, {}).get("fields", {}))
            for fn in [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for dec in fn.decorator_list:
                    if not (isinstance(dec, ast.Call) and attr_name(dec.func) in {"api.depends", "api.constrains"}):
                        continue
                    for arg in dec.args:
                        value = literal(arg)
                        if isinstance(value, str):
                            root = value.split(".", 1)[0]
                            if root and root not in local_fields:
                                issues.append(f"{path.relative_to(ROOT)}:{cls.name}:{fn.name}:{root}")
    return issues


def relation_issues(reg):
    issues = []
    for model in PERSISTENT_MODELS:
        for fname, meta in reg.get(model, {}).get("fields", {}).items():
            if meta.get("type") != "One2many":
                continue
            comodel = meta.get("comodel")
            inverse = meta.get("inverse_name")
            if comodel in PERSISTENT_MODELS and inverse:
                if inverse not in reg.get(comodel, {}).get("fields", {}):
                    issues.append(f"{model}:{fname}->{comodel}.{inverse}:missing")
    return issues


def view_records(paths):
    rows = []
    for path in paths:
        xml_root = ET.parse(path).getroot()
        for rec in xml_root.iter("record"):
            if rec.get("model") != "ir.ui.view":
                continue
            model = None
            arch = None
            for field in rec.findall("field"):
                if field.get("name") == "model":
                    model = (field.text or "").strip()
                elif field.get("name") == "arch" and list(field):
                    arch = list(field)[0]
            if model and arch is not None:
                rows.append((path, rec.get("id") or "<view>", model, arch))
    return rows


def validate_arch_node(node, model, reg, path, view_id, issues):
    fields = reg.get(model, {}).get("fields", {})
    methods = reg.get(model, {}).get("methods", set())
    for child in list(node):
        if child.tag == "field":
            name = child.get("name")
            meta = fields.get(name)
            if name and name not in fields and name not in COMMON_ORM_FIELDS:
                issues.append(f"{path.relative_to(ROOT)}:{view_id}:{model}:missing-field:{name}")
            nested_model = meta.get("comodel") if meta and meta.get("type") in {"One2many", "Many2many"} else None
            for grand in list(child):
                if grand.tag in {"list", "form", "kanban"} and nested_model in reg:
                    validate_arch_node(grand, nested_model, reg, path, view_id, issues)
        elif child.tag == "button" and child.get("type") == "object":
            name = child.get("name")
            if name and name not in methods:
                issues.append(f"{path.relative_to(ROOT)}:{view_id}:{model}:missing-method:{name}")
        else:
            validate_arch_node(child, model, reg, path, view_id, issues)


def view_contract_issues(paths, reg):
    issues = []
    for path, view_id, model, arch in view_records(paths):
        if model in PERSISTENT_MODELS:
            validate_arch_node(arch, model, reg, path, view_id, issues)
    return issues


def searchability_issues(paths, reg):
    issues = []
    field_re = re.compile(r"\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*,")
    for path, view_id, model, arch in view_records(paths):
        if model not in PERSISTENT_MODELS or arch.tag != "search":
            continue
        fields = reg[model]["fields"]
        for node in arch.iter("filter"):
            for match in field_re.finditer(node.get("domain") or ""):
                fname = match.group(1)
                meta = fields.get(fname)
                if meta and meta.get("compute") and meta.get("store") is not True and not meta.get("search"):
                    issues.append(f"{path.relative_to(ROOT)}:{view_id}:{model}:{fname}")
    return issues


def coverage(paths):
    result = defaultdict(set)
    for _path, _view_id, model, arch in view_records(paths):
        if model in PERSISTENT_MODELS and arch.tag in {"search", "list", "form", "kanban", "calendar"}:
            result[model].add(arch.tag)
    return result


def acl_models(path):
    result = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ref = row.get("model_id:id") or ""
            if ref.startswith("model_"):
                result.add(ref[len("model_"):].replace("_", "."))
    return result


def rule_models(path):
    result = set()
    xml_root = ET.parse(path).getroot()
    for rec in xml_root.iter("record"):
        if rec.get("model") != "ir.rule":
            continue
        for field in rec.findall("field"):
            if field.get("name") == "model_id":
                ref = field.get("ref") or ""
                if ref.startswith("model_"):
                    result.add(ref[len("model_"):].replace("_", "."))
    return result


def local_xmlid_issues(manifest, active_model_paths):
    ids = set()
    loaded = []
    for rel in manifest.get("data", []) + manifest.get("demo", []):
        path = ROOT / rel
        if path.suffix == ".xml" and path.exists():
            loaded.append(path)
            ids.update(node.get("id") for node in ET.parse(path).getroot().iter() if node.get("id"))
    issues = []
    for path in loaded:
        for node in ET.parse(path).getroot().iter():
            raw_ref = node.get("ref") or ""
            if raw_ref.startswith("clinic_room_device.") and raw_ref.split(".", 1)[1] not in ids:
                issues.append(f"{path.relative_to(ROOT)}:missing-ref:{raw_ref}")
            action = node.get("action") or ""
            if action.startswith("clinic_room_device.") and action.split(".", 1)[1] not in ids:
                issues.append(f"{path.relative_to(ROOT)}:missing-action:{action}")
            elif action and "." not in action and not action.isdigit() and action not in ids:
                issues.append(f"{path.relative_to(ROOT)}:missing-local-action:{action}")
    ref_re = re.compile(r'env\.ref\(\s*["\']clinic_room_device\.([A-Za-z0-9_]+)["\']')
    for path in active_model_paths:
        for xmlid in ref_re.findall(path.read_text(encoding="utf-8")):
            if xmlid not in ids:
                issues.append(f"{path.relative_to(ROOT)}:missing-env-ref:{xmlid}")
    return sorted(set(issues))


def main():
    contract = load_contract()
    manifest = load_manifest()
    active = active_paths(contract)
    rows = parse_classes(active)
    reg = registry(rows)
    loaded_view_paths = [
        ROOT / rel for rel in manifest.get("data", [])
        if rel.startswith("views/") and (ROOT / rel).exists()
    ]
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    add(
        "HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
        ROOT.name == "clinic_room_device"
        and contract.get("project") == "ClinicOne"
        and contract.get("addon") == "clinic_room_device",
        f"folder={ROOT.name}",
    )

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    add(
        "HARD_GATE_1_CODEX_BUKAN_ARCHITECT",
        "LIMITED IMPLEMENTATION WORKER" in agents
        and "Maximum focused repair attempts per blocker/root-cause class: 3" in agents
        and "After the third failure STOP" in agents,
        "bounded worker / max 3",
    )

    add(
        "MANIFEST_DEPENDENCY_PRESERVATION",
        manifest.get("depends") == contract["manifest_dependencies"],
        "dependencies exactly baseline",
    )

    init_tree = ast.parse((ROOT / "models/__init__.py").read_text(encoding="utf-8"))
    imported = []
    for node in init_tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            imported.extend(alias.name for alias in node.names)
    add("ACTIVE_IMPORT_GRAPH_PRESERVATION", imported == contract["active_model_imports"], str(imported))
    add("DORMANT_INHERIT_PACKAGE_PRESERVED", "inherit" not in imported and (ROOT / "models/inherit").exists(), "inherit stays dormant")

    missing_baseline_files = [rel for rel in contract["baseline_nonbackup_files"] if not (ROOT / rel).exists()]
    add("BASELINE_SOURCE_FILE_PRESERVATION", not missing_baseline_files, str(missing_baseline_files[:5]))

    preservation = preservation_issues(contract)
    add("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", not preservation, str(preservation[:8]))

    compile_errors = []
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0") or "__pycache__" in path.parts:
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            compile_errors.append(f"{path.relative_to(ROOT)}:{exc}")
    add("PYTHON_COMPILE", not compile_errors, str(compile_errors[:3]))

    xml_errors = []
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        try:
            ET.parse(path)
        except Exception as exc:
            xml_errors.append(f"{path.relative_to(ROOT)}:{exc}")
    add("XML_PARSE", not xml_errors, str(xml_errors[:3]))

    all_model_paths = [p for p in (ROOT / "models").rglob("*.py") if not p.name.startswith("0")]
    legacy_constraints = [str(p.relative_to(ROOT)) for p in all_model_paths if "_sql_constraints" in p.read_text(encoding="utf-8")]
    constraint_count = sum(r["constraints"] for r in parse_classes(all_model_paths))
    add(
        "ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE",
        not legacy_constraints and constraint_count >= 18,
        f"legacy={legacy_constraints}, models.Constraint={constraint_count}",
    )

    all_text = "\n".join(p.read_text(encoding="utf-8") for p in all_model_paths)
    compatibility = []
    if re.search(r"def\s+name_search\s*\([^)]*\bargs\s*=", all_text):
        compatibility.append("legacy-name-search-args")
    if re.search(r"view_mode[^\n]*[\"']tree", all_text):
        compatibility.append("legacy-tree-view-mode")
    room_type_source = (ROOT / "models/room_type.py").read_text(encoding="utf-8")
    device_category_source = (ROOT / "models/device_category.py").read_text(encoding="utf-8")
    if 'allowed = {"service", "consu", "product"}' in room_type_source or '["product", "consu", "service"]' in room_type_source:
        compatibility.append("legacy-product-type-room-type")
    if '["consu", "product", "service"]' in device_category_source:
        compatibility.append("legacy-product-type-device-category")
    if re.search(r"domain\s*=\s*\[\(\s*[\"']supplier_rank[\"']", device_category_source):
        compatibility.append("supplier-rank-account-hard-coupling")
    device_source = (ROOT / "models/device.py").read_text(encoding="utf-8")
    if '"team_id"' in device_source or '"default_team_id"' in device_source:
        compatibility.append("legacy-maintenance-team-field")
    add("ODOO19_STATIC_COMPATIBILITY", not compatibility, str(compatibility))

    collisions = namespace_collision_issues(all_model_paths)
    add("FIELD_METHOD_NAMESPACE_COLLISION_GATE", not collisions, str(collisions))

    callables = callable_issues(reg)
    add("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE", not callables, str(callables[:8]))

    decorators = decorator_dependency_issues(active, reg)
    add("CUSTOM_DECORATOR_FIELD_CONTRACT_GATE", not decorators, str(decorators[:8]))

    relations = relation_issues(reg)
    add("RELATIONAL_MODEL_INVERSE_CONTRACT_GATE", not relations, str(relations[:8]))

    view_issues = view_contract_issues(loaded_view_paths, reg)
    add("XML_MODEL_FIELD_BUTTON_CONTRACT_GATE", not view_issues, str(view_issues[:10]))

    architecture_issues = []
    for path, view_id, _model, arch in view_records(loaded_view_paths):
        if arch.tag == "tree" or any(node.tag == "tree" for node in arch.iter()):
            architecture_issues.append(f"{path.relative_to(ROOT)}:{view_id}:legacy-tree")
        if arch.tag == "search":
            for group in arch.findall(".//group"):
                if "expand" in group.attrib:
                    architecture_issues.append(f"{path.relative_to(ROOT)}:{view_id}:group-expand")
    add("ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE", not architecture_issues, str(architecture_issues))

    searchability = searchability_issues(loaded_view_paths, reg)
    add("ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE", not searchability, str(searchability))

    cov = coverage(loaded_view_paths)
    missing_coverage = {
        model: sorted({"search", "list", "form"} - cov.get(model, set()))
        for model in sorted(PERSISTENT_MODELS)
        if {"search", "list", "form"} - cov.get(model, set())
    }
    add("HARD_GATE_8_SEARCH_VIEW_WAJIB", all("search" in cov.get(m, set()) for m in PERSISTENT_MODELS), str(missing_coverage))
    add("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY", all("list" in cov.get(m, set()) for m in PERSISTENT_MODELS), str(missing_coverage))
    add(
        "HARD_GATE_6_PROFESSIONAL_FORM_DESIGN",
        all("form" in cov.get(m, set()) for m in PERSISTENT_MODELS)
        and any('widget="statusbar"' in p.read_text(encoding="utf-8") for p in loaded_view_paths)
        and any("oe_button_box" in p.read_text(encoding="utf-8") for p in loaded_view_paths),
        str(missing_coverage),
    )
    add("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL", (ROOT / "docs/CLINIC_ROOM_DEVICE_UI_UX_MATRIX.md").exists() and not missing_coverage, str(missing_coverage))

    acl = acl_models(ROOT / "security/ir.model.access.csv")
    rules = rule_models(ROOT / "security/clinic_room_device_rules.xml")
    add(
        "HARD_GATE_10_SECURITY_OVER_UI",
        PERSISTENT_MODELS <= acl and PERSISTENT_MODELS <= rules,
        f"acl_missing={sorted(PERSISTENT_MODELS-acl)}, rule_missing={sorted(PERSISTENT_MODELS-rules)}",
    )

    xmlids = local_xmlid_issues(manifest, active)
    add("LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE", not xmlids, str(xmlids[:10]))

    missing_manifest_files = [
        rel for key in ("data", "demo") for rel in manifest.get(key, [])
        if not (ROOT / rel).exists()
    ]
    add("MANIFEST_FILE_REFERENCE_CONTRACT_GATE", not missing_manifest_files, str(missing_manifest_files))

    sequence_ids = {
        node.get("id") for node in ET.parse(ROOT / "data/clinic_room_device_sequence.xml").getroot().iter("record")
    }
    required_sequences = {"seq_clinic_device", "seq_clinic_room_device_assignment", "seq_clinic_device_movement", "seq_room_session"}
    add("EXISTING_SEQUENCE_CONTRACT_GATE", required_sequences <= sequence_ids, str(sorted(required_sequences-sequence_ids)))

    backup_loaded = [
        rel for key in ("data", "demo") for rel in manifest.get(key, [])
        if Path(rel).name.startswith("0")
    ]
    add("BACKUP_FILE_EXCLUSION_GATE", not backup_loaded, str(backup_loaded))

    missing_docs = [rel for rel in sorted(REQUIRED_DOCS | REQUIRED_VIEW_FILES) if not (ROOT / rel).exists()]
    add("HARD_GATE_3_ENTERPRISE_COMPLETENESS", not missing_docs and not missing_coverage, str(missing_docs))
    add("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY", (ROOT / "docs/CLINIC_ROOM_DEVICE_STRUCTURAL_INVENTORY.md").exists(), "inventory")
    add("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE", len([p for p in loaded_view_paths if p.name.endswith("_views.xml")]) >= 6, "split domain views")
    add("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY", (ROOT / "docs/CLINIC_ROOM_DEVICE_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md").exists(), "guardrail")

    comment_text = (ROOT / "models/device_category.py").read_text(encoding="utf-8") + (ROOT / "models/device.py").read_text(encoding="utf-8")
    add("HARD_GATE_13_USEFUL_COMMENTS", "dependency guard" in comment_text.lower() and "Odoo 19 maintenance.request" in comment_text, "compatibility comments")
    add("HARD_GATE_14_CODEX_RETRY_LIMIT", "Maximum focused repair attempts per blocker/root-cause class: 3" in agents and "After the third failure STOP" in agents, "3-attempt stop")
    add("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX", (ROOT / "docs/CLINIC_ROOM_DEVICE_ENTERPRISE_COMPLETENESS_MATRIX.md").exists(), "matrix")

    owner_gate_names = {
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
    }

    print("=" * 78)
    print("CLINIC_ROOM_DEVICE ENTERPRISE DEVELOPMENT HARD GATE")
    print("=" * 78)
    failed = []
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
        if not ok:
            print(f"      {detail}")
            failed.append(name)
    owner_pass = sum(1 for name, ok, _ in checks if name in owner_gate_names and ok)
    print("-" * 78)
    print(f"OWNER_HARD_GATES_PASS: {owner_pass} / 15")
    if failed:
        print("CLINIC_ROOM_DEVICE_STATIC_MOVE_FORWARD_READY: NO")
        print(f"FAILED_GATES: {failed}")
        return 1
    print("CLINIC_ROOM_DEVICE_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_ROOM_DEVICE_MOVE_FORWARD_READY: PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
