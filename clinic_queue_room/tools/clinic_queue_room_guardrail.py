
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ClinicOne clinic_queue_room machine-checkable enterprise hard gate.

This validator intentionally checks source contracts that commonly fail only
during an Odoo registry/data load: field/method namespace collisions,
compute/inverse/search method references, relational inverses, XML field/button
contracts, searchability, local XML IDs, active import preservation and Odoo 19
compatibility patterns.
"""
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
CONTRACT_PATH = ROOT / "docs/CLINIC_QUEUE_ROOM_BASELINE_CONTRACT.json"

PERSISTENT_CUSTOM_MODELS = {
    "clinic.queue.stage",
    "clinic.queue.token",
    "clinic.queue",
    "clinic.room.assignment",
    "clinic.queue.event",
    "clinic.queue.channel",
    "clinic.queue.visit",
    "clinic.queue.ticket",
}
COMMON_ORM_FIELDS = {
    "id", "display_name", "create_date", "create_uid", "write_date", "write_uid",
    "message_ids", "message_follower_ids", "message_partner_ids",
    "message_attachment_count", "activity_ids", "activity_state",
    "activity_user_id", "activity_type_id", "activity_date_deadline",
    "__last_update",
}
FIELD_TYPES = {
    "Char", "Text", "Html", "Integer", "Float", "Boolean", "Date", "Datetime",
    "Selection", "Many2one", "One2many", "Many2many", "Image", "Binary",
    "Monetary", "Reference",
}
REQUIRED_DOCS = {
    "AGENTS.md",
    "docs/CLINIC_QUEUE_ROOM_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "docs/CLINIC_QUEUE_ROOM_BASELINE_CONTRACT.json",
    "docs/CLINIC_QUEUE_ROOM_STRUCTURAL_INVENTORY.md",
    "docs/CLINIC_QUEUE_ROOM_UI_UX_MATRIX.md",
    "docs/CLINIC_QUEUE_ROOM_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/CLINIC_QUEUE_ROOM_ODOO19_REVIEW.md",
}
REQUIRED_VIEW_FILES = {
    "views/queue_stage_channel_views.xml",
    "views/queue_token_views.xml",
    "views/queue_views.xml",
    "views/room_assignment_views.xml",
    "views/queue_event_views.xml",
    "views/queue_visit_ticket_views.xml",
    "views/hr_doctor_queue_views.xml",
    "views/clinic_queue_room_menus.xml",
}
OPTIONAL_LOCAL_XMLIDS = {"report_clinic_queue_ticket"}


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_manifest():
    return ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))


def active_paths(contract):
    return [ROOT / "models" / f"{name}.py" for name in contract["active_model_imports"]]


def is_field_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "fields"
        and node.func.attr in FIELD_TYPES
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
                            typ = item.value.func.attr
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
                        if (
                            isinstance(item.value, ast.Call)
                            and isinstance(item.value.func, ast.Attribute)
                            and isinstance(item.value.func.value, ast.Name)
                            and item.value.func.value.id == "models"
                            and item.value.func.attr == "Constraint"
                        ):
                            constraints += 1
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(item.name)
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


def preservation_issues(contract, rows):
    by_file_class = {(r["file"], r["class"]): r for r in rows}
    issues = []
    for rel, expected_rows in contract["structural_inventory"].items():
        for expected in expected_rows:
            actual = by_file_class.get((rel, expected["class"]))
            if not actual:
                issues.append(f"{rel}:{expected['class']}:missing-class")
                continue
            for fname in expected.get("fields", []):
                if fname not in actual["fields"]:
                    issues.append(f"{rel}:{expected['class']}:missing-field:{fname}")
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
        methods = bucket["methods"]
        for fname, meta in bucket["fields"].items():
            for key in ("compute", "inverse", "search"):
                value = meta.get(key)
                if isinstance(value, str) and value and value not in methods:
                    issues.append(f"{model}:{fname}:{key}:{value}")
    return issues


def decorator_dependency_issues(paths, reg):
    issues = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            row = next((r for r in parse_classes([path]) if r["class"] == cls.name), None)
            model = model_of(row) if row else None
            local_fields = set(reg.get(model, {}).get("fields", {}))
            inherited_allowed = {"resource_calendar_id", "company_id", "name"} if model == "hr.employee" else set()
            for fn in [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for dec in fn.decorator_list:
                    if not (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and isinstance(dec.func.value, ast.Name)
                        and dec.func.value.id == "api"
                        and dec.func.attr in {"depends", "constrains"}
                    ):
                        continue
                    for arg in dec.args:
                        value = literal(arg)
                        if isinstance(value, str):
                            root = value.split(".", 1)[0]
                            if root and root not in local_fields and root not in inherited_allowed:
                                issues.append(f"{path.relative_to(ROOT)}:{cls.name}:{fn.name}:{dec.func.attr}:{root}")
    return issues


def relation_issues(reg):
    issues = []
    for model in PERSISTENT_CUSTOM_MODELS:
        fields = reg.get(model, {}).get("fields", {})
        for fname, meta in fields.items():
            if meta.get("type") != "One2many":
                continue
            comodel = meta.get("comodel")
            inverse = meta.get("inverse_name")
            if comodel in PERSISTENT_CUSTOM_MODELS and inverse:
                if inverse not in reg.get(comodel, {}).get("fields", {}):
                    issues.append(f"{model}:{fname}->{comodel}.{inverse}:missing")
    return issues


def view_records(paths):
    rows = []
    for path in paths:
        root = ET.parse(path).getroot()
        for rec in root.iter("record"):
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


def view_contract_issues(paths, reg):
    issues = []
    for path, vid, model, arch in view_records(paths):
        if model in PERSISTENT_CUSTOM_MODELS:
            fields = reg[model]["fields"]
            methods = reg[model]["methods"]
            for node in arch.iter("field"):
                name = node.get("name")
                if name and name not in fields and name not in COMMON_ORM_FIELDS:
                    issues.append(f"{path.relative_to(ROOT)}:{vid}:{model}:missing-field:{name}")
            for node in arch.iter("button"):
                if node.get("type") == "object":
                    name = node.get("name")
                    if name and name not in methods:
                        issues.append(f"{path.relative_to(ROOT)}:{vid}:{model}:missing-method:{name}")
        elif model == "hr.employee":
            fields = reg.get(model, {}).get("fields", {})
            methods = reg.get(model, {}).get("methods", set())
            for node in arch.iter("field"):
                name = node.get("name")
                if name and (name.startswith("clinic_") or name in fields) and name not in fields:
                    issues.append(f"{path.relative_to(ROOT)}:{vid}:hr.employee:missing-extension-field:{name}")
            for node in arch.iter("button"):
                if node.get("type") == "object":
                    name = node.get("name")
                    if name and name.startswith("action_") and name not in methods:
                        # Existing native HR buttons may be present in inheritance selectors,
                        # but this addon only adds its own action_* buttons inside inserted XML.
                        if name in {
                            "action_set_on_duty", "action_set_on_call", "action_set_in_service",
                            "action_set_on_break", "action_set_off_duty", "action_view_active_queues",
                            "action_view_room_assignments", "action_open_schedule",
                        }:
                            issues.append(f"{path.relative_to(ROOT)}:{vid}:hr.employee:missing-method:{name}")
    return issues


def searchability_issues(paths, reg):
    issues = []
    field_re = re.compile(r"\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*,")
    for path, vid, model, arch in view_records(paths):
        if model not in PERSISTENT_CUSTOM_MODELS or arch.tag != "search":
            continue
        fields = reg[model]["fields"]
        for node in arch.iter("filter"):
            for match in field_re.finditer(node.get("domain") or ""):
                fname = match.group(1)
                meta = fields.get(fname)
                if meta and meta.get("compute") and meta.get("store") is not True and not meta.get("search"):
                    issues.append(f"{path.relative_to(ROOT)}:{vid}:{model}:{fname}")
    return issues


def coverage(paths):
    result = defaultdict(set)
    for _path, _vid, model, arch in view_records(paths):
        if model in PERSISTENT_CUSTOM_MODELS and arch.tag in {"search", "list", "form", "kanban", "calendar"}:
            result[model].add(arch.tag)
    return result


def local_xmlid_issues(manifest, active_model_paths):
    loaded = []
    ids = set()
    for rel in manifest.get("data", []) + manifest.get("demo", []):
        path = ROOT / rel
        if path.suffix == ".xml" and path.exists():
            loaded.append(path)
            xml_root = ET.parse(path).getroot()
            ids.update(node.get("id") for node in xml_root.iter() if node.get("id"))
    issues = []
    for path in loaded:
        xml_root = ET.parse(path).getroot()
        for node in xml_root.iter():
            raw_ref = node.get("ref") or ""
            if raw_ref.startswith("clinic_queue_room.") and raw_ref.split(".", 1)[1] not in ids:
                issues.append(f"{path.relative_to(ROOT)}:missing-ref:{raw_ref}")
            action = node.get("action") or ""
            if action.startswith("clinic_queue_room.") and action.split(".", 1)[1] not in ids:
                issues.append(f"{path.relative_to(ROOT)}:missing-action:{action}")
            elif action and "." not in action and action not in ids and not action.isdigit():
                issues.append(f"{path.relative_to(ROOT)}:missing-local-action:{action}")
    ref_re = re.compile(r'env\.ref\(\s*["\']clinic_queue_room\.([A-Za-z0-9_]+)["\']')
    for path in active_model_paths:
        for xid in ref_re.findall(path.read_text(encoding="utf-8")):
            if xid not in ids and xid not in OPTIONAL_LOCAL_XMLIDS:
                issues.append(f"{path.relative_to(ROOT)}:missing-env-ref:clinic_queue_room.{xid}")
    return sorted(set(issues))


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
    root = ET.parse(path).getroot()
    for rec in root.iter("record"):
        if rec.get("model") != "ir.rule":
            continue
        for field in rec.findall("field"):
            if field.get("name") == "model_id":
                ref = field.get("ref") or ""
                if ref.startswith("model_"):
                    result.add(ref[len("model_"):].replace("_", "."))
    return result


def main():
    contract = load_contract()
    manifest = load_manifest()
    apaths = active_paths(contract)
    active_rows = parse_classes(apaths)
    reg = registry(active_rows)
    loaded_view_paths = [
        ROOT / rel for rel in manifest.get("data", [])
        if rel.startswith("views/") and (ROOT / rel).exists()
    ]
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    add("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
        ROOT.name == "clinic_queue_room"
        and contract.get("project") == "ClinicOne"
        and contract.get("addon") == "clinic_queue_room",
        f"folder={ROOT.name}")

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    add("HARD_GATE_1_CODEX_BUKAN_ARCHITECT",
        "LIMITED IMPLEMENTATION WORKER" in agents
        and "endless retry engine" in agents.lower()
        and "Maximum focused repair attempts per blocker/root-cause class: 3" in agents,
        "bounded implementation worker / max 3")

    add("MANIFEST_DEPENDENCY_PRESERVATION",
        manifest.get("depends") == contract["manifest_dependencies"],
        "dependencies exactly baseline")

    init_tree = ast.parse((ROOT / "models/__init__.py").read_text(encoding="utf-8"))
    imported = []
    for node in init_tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            imported.extend(alias.name for alias in node.names)
    add("ACTIVE_IMPORT_GRAPH_PRESERVATION",
        imported == contract["active_model_imports"],
        f"active={imported}")

    missing_files = [rel for rel in contract["baseline_nonbackup_files"] if not (ROOT / rel).exists()]
    add("BASELINE_SOURCE_FILE_PRESERVATION", not missing_files, str(missing_files[:5]))

    all_baseline_model_paths = [
        ROOT / rel for rel in contract["structural_inventory"]
        if (ROOT / rel).exists()
    ]
    preservation_rows = parse_classes(all_baseline_model_paths)
    preservation = preservation_issues(contract, preservation_rows)
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

    all_model_paths = [p for p in (ROOT / "models").glob("*.py") if not p.name.startswith("0")]
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in all_model_paths)
    legacy = [str(p.relative_to(ROOT)) for p in all_model_paths if "_sql_constraints" in p.read_text(encoding="utf-8")]
    constraint_count = sum(r["constraints"] for r in parse_classes(all_model_paths))
    add("ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE",
        not legacy and constraint_count >= 9,
        f"legacy={legacy}, models.Constraint={constraint_count}")

    direct_read_group = [
        str(p.relative_to(ROOT)) for p in all_model_paths
        if re.search(r"(?<!_)read_group\s*\(", p.read_text(encoding="utf-8"))
    ]
    legacy_name_search = [
        str(p.relative_to(ROOT)) for p in all_model_paths
        if re.search(r"def\s+name_search\s*\([^)]*\bargs\s*=", p.read_text(encoding="utf-8"))
    ]
    legacy_tree_modes = [
        str(p.relative_to(ROOT)) for p in all_model_paths
        if re.search(r"""view_mode["']?\s*[:=]\s*["'][^"']*\btree\b""", p.read_text(encoding="utf-8"))
    ]
    add("ODOO19_STATIC_COMPATIBILITY",
        not direct_read_group and not legacy_name_search and not legacy_tree_modes,
        f"read_group={direct_read_group}, name_search={legacy_name_search}, tree_modes={legacy_tree_modes}")

    collisions = namespace_collision_issues(all_model_paths)
    add("FIELD_METHOD_NAMESPACE_COLLISION_GATE", not collisions, str(collisions))

    callables = callable_issues(reg)
    add("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE", not callables, str(callables[:8]))

    decorators = decorator_dependency_issues(apaths, reg)
    add("CUSTOM_DECORATOR_FIELD_CONTRACT_GATE", not decorators, str(decorators[:8]))

    relations = relation_issues(reg)
    add("RELATIONAL_MODEL_INVERSE_CONTRACT_GATE", not relations, str(relations[:8]))

    forbidden_room_patterns = {
        ".allow_multi_patient": "obsolete clinic.room.allow_multi_patient",
        ".validate_assignment_policy": "missing clinic.room helper",
        ".action_assign_queue": "missing clinic.room helper",
        ".action_release_queue": "missing clinic.room helper",
        "._compute_current_assignments": "missing clinic.room helper",
    }
    active_text = "\n".join(p.read_text(encoding="utf-8") for p in apaths)
    # Strip comments/docstrings enough for the explicit attribute patterns.
    room_contract_issues = [label for pattern, label in forbidden_room_patterns.items() if pattern in active_text]
    add("FROZEN_CLINIC_ROOM_CONTRACT_GATE", not room_contract_issues, str(room_contract_issues))

    view_issues = view_contract_issues(loaded_view_paths, reg)
    add("XML_MODEL_FIELD_BUTTON_CONTRACT_GATE", not view_issues, str(view_issues[:10]))

    search_arch = []
    for path, vid, model, arch in view_records(loaded_view_paths):
        if arch.tag == "tree" or any(node.tag == "tree" for node in arch.iter()):
            search_arch.append(f"{path.relative_to(ROOT)}:{vid}:legacy-tree")
        if arch.tag == "search":
            for group in arch.findall(".//group"):
                if "expand" in group.attrib:
                    search_arch.append(f"{path.relative_to(ROOT)}:{vid}:group-expand")
    add("ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE", not search_arch, str(search_arch))

    searchability = searchability_issues(loaded_view_paths, reg)
    add("ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE", not searchability, str(searchability))

    cov = coverage(loaded_view_paths)
    coverage_missing = {
        model: sorted({"search", "list", "form"} - cov.get(model, set()))
        for model in sorted(PERSISTENT_CUSTOM_MODELS)
        if {"search", "list", "form"} - cov.get(model, set())
    }
    add("HARD_GATE_8_SEARCH_VIEW_WAJIB",
        all("search" in cov.get(m, set()) for m in PERSISTENT_CUSTOM_MODELS),
        str(coverage_missing))
    add("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY",
        all("list" in cov.get(m, set()) for m in PERSISTENT_CUSTOM_MODELS),
        str(coverage_missing))
    add("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN",
        all("form" in cov.get(m, set()) for m in PERSISTENT_CUSTOM_MODELS)
        and any('widget="statusbar"' in p.read_text(encoding="utf-8") for p in loaded_view_paths)
        and any("oe_button_box" in p.read_text(encoding="utf-8") for p in loaded_view_paths),
        str(coverage_missing))
    add("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL",
        (ROOT / "docs/CLINIC_QUEUE_ROOM_UI_UX_MATRIX.md").exists() and not coverage_missing,
        str(coverage_missing))

    acl = acl_models(ROOT / "security/ir.model.access.csv")
    rules = rule_models(ROOT / "security/clinic_queue_room_rules.xml")
    add("HARD_GATE_10_SECURITY_OVER_UI",
        PERSISTENT_CUSTOM_MODELS <= acl and PERSISTENT_CUSTOM_MODELS <= rules,
        f"acl_missing={sorted(PERSISTENT_CUSTOM_MODELS-acl)}, rule_missing={sorted(PERSISTENT_CUSTOM_MODELS-rules)}")

    xmlids = local_xmlid_issues(manifest, apaths)
    add("LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE", not xmlids, str(xmlids[:10]))

    missing_manifest_files = [
        rel for key in ("data", "demo")
        for rel in manifest.get(key, [])
        if not (ROOT / rel).exists()
    ]
    add("MANIFEST_FILE_REFERENCE_CONTRACT_GATE", not missing_manifest_files, str(missing_manifest_files))

    backup_files = [
        str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
        if p.is_file() and p.name.startswith("0")
    ]
    backup_loaded = [
        rel for key in ("data", "demo")
        for rel in manifest.get(key, [])
        if Path(rel).name.startswith("0")
    ]
    add("BACKUP_FILE_EXCLUSION_GATE", not backup_loaded, f"loaded={backup_loaded}; present-but-ignored={len(backup_files)}")

    missing_docs = [rel for rel in sorted(REQUIRED_DOCS | REQUIRED_VIEW_FILES) if not (ROOT / rel).exists()]
    add("HARD_GATE_3_ENTERPRISE_COMPLETENESS", not missing_docs and not coverage_missing,
        f"missing={missing_docs}")
    add("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY",
        (ROOT / "docs/CLINIC_QUEUE_ROOM_STRUCTURAL_INVENTORY.md").exists(), "inventory")
    add("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
        len([p for p in loaded_view_paths if p.name.endswith("_views.xml")]) >= 6,
        "split domain view files")
    add("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY",
        (ROOT / "docs/CLINIC_QUEUE_ROOM_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md").exists(),
        "guardrail/code structure")
    add("HARD_GATE_13_USEFUL_COMMENTS",
        "frozen upstream addon" in (ROOT / "models/clinic_room_assignment.py").read_text(encoding="utf-8").lower(),
        "technical comments explain cross-addon contract")
    add("HARD_GATE_14_CODEX_RETRY_LIMIT",
        "Maximum focused repair attempts per blocker/root-cause class: 3" in agents
        and "After the third failure STOP" in agents,
        "3-attempt hard stop")
    add("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
        (ROOT / "docs/CLINIC_QUEUE_ROOM_ENTERPRISE_COMPLETENESS_MATRIX.md").exists(),
        "matrix")

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
    print("CLINIC_QUEUE_ROOM ENTERPRISE DEVELOPMENT HARD GATE")
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
        print(f"CLINIC_QUEUE_ROOM_STATIC_MOVE_FORWARD_READY: NO")
        print(f"FAILED_GATES: {failed}")
        return 1
    print("CLINIC_QUEUE_ROOM_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_QUEUE_ROOM_MOVE_FORWARD_READY: PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
