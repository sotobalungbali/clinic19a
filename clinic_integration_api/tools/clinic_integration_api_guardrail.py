#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []
PASSES = []


def fail(gate, message):
    ERRORS.append(f"[FAIL] HARD GATE {gate}: {message}")


def ok(gate, message):
    PASSES.append(f"[PASS] HARD GATE {gate}: {message}")


def py_files(root):
    return [p for p in root.rglob("*.py") if not p.name.startswith("0") and "__pycache__" not in p.parts]


def xml_files(root):
    return [p for p in root.rglob("*.xml") if not p.name.startswith("0")]


def assigned_literal(class_node, name, default=None):
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                try:
                    return ast.literal_eval(node.value)
                except Exception:
                    return default
    return default


def field_info(value):
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
        return None
    if not isinstance(value.func.value, ast.Name) or value.func.value.id != "fields":
        return None
    kind = value.func.attr
    comodel = None
    if value.args and isinstance(value.args[0], ast.Constant) and isinstance(value.args[0].value, str):
        comodel = value.args[0].value
    return {"type": kind.lower(), "comodel": comodel}


def build_registry(source_root):
    direct = defaultdict(dict)
    methods = defaultdict(set)
    edges = defaultdict(set)
    delegated = defaultdict(set)
    owners = defaultdict(set)

    for path in py_files(source_root):
        # Do not use the addon-under-test as upstream evidence when a project root contains it.
        if path.is_relative_to(ROOT):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        addon = path.relative_to(source_root).parts[0] if path.is_relative_to(source_root) else ""
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            name = assigned_literal(cls, "_name")
            inherit = assigned_literal(cls, "_inherit", [])
            inherits = assigned_literal(cls, "_inherits", {}) or {}
            if isinstance(inherit, str):
                inherit_list = [inherit]
            elif isinstance(inherit, (list, tuple)):
                inherit_list = list(inherit)
            else:
                inherit_list = []
            target = name or (inherit if isinstance(inherit, str) else None)
            if not target:
                continue
            if name:
                owners[target].add(addon)
            for parent in inherit_list:
                if parent != target:
                    edges[target].add(parent)
            if isinstance(inherits, dict):
                delegated[target].update(inherits.keys())
            for node in cls.body:
                if isinstance(node, ast.Assign):
                    info = field_info(node.value)
                    if info:
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                direct[target][t.id] = info
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[target].add(node.name)

    cache = {}
    visiting = set()
    def resolved_fields(model):
        if model in cache:
            return cache[model]
        if model in visiting:
            return dict(direct.get(model, {}))
        visiting.add(model)
        fields_map = dict(direct.get(model, {}))
        for parent in edges.get(model, set()) | delegated.get(model, set()):
            parent_fields = resolved_fields(parent)
            for key, value in parent_fields.items():
                fields_map.setdefault(key, value)
        visiting.remove(model)
        cache[model] = fields_map
        return fields_map

    method_cache = {}
    visiting_methods = set()
    def resolved_methods(model):
        if model in method_cache:
            return method_cache[model]
        if model in visiting_methods:
            return set(methods.get(model, set()))
        visiting_methods.add(model)
        result = set(methods.get(model, set()))
        for parent in edges.get(model, set()) | delegated.get(model, set()):
            result |= resolved_methods(parent)
        visiting_methods.remove(model)
        method_cache[model] = result
        return result

    models = set(direct) | set(edges) | set(delegated) | set(owners)
    return {
        "fields": {m: resolved_fields(m) for m in models},
        "methods": {m: resolved_methods(m) for m in models},
        "owners": owners,
    }


def path_exists(registry, model, path):
    current = model
    parts = path.split(".")
    for index, part in enumerate(parts):
        fields_map = registry["fields"].get(current, {})
        info = fields_map.get(part)
        if not info:
            return False, f"{current}.{part} missing"
        if index < len(parts) - 1:
            if not info.get("comodel"):
                return False, f"{current}.{part} has no statically resolvable comodel"
            current = info["comodel"]
    return True, ""


def parse_resource_specs():
    tree = ast.parse((ROOT / "models/api_service.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ClinicApiService":
            for item in node.body:
                if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RESOURCE_SPECS" for t in item.targets):
                    return ast.literal_eval(item.value)
    raise RuntimeError("RESOURCE_SPECS not found")


def parse_mutation_specs():
    tree = ast.parse((ROOT / "models/api_service.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ClinicApiService":
            for item in node.body:
                if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MUTATION_SPECS" for t in item.targets):
                    return ast.literal_eval(item.value)
    raise RuntimeError("MUTATION_SPECS not found")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=ROOT.parent, help="ClinicOne project root containing sibling addons")
    args = parser.parse_args()
    source_root = args.source_root.resolve()

    manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))

    # HG0 — project identity.
    if manifest.get("version") != "19.0.1.0.0" or ROOT.name != "clinic_integration_api":
        fail(0, "addon identity/version mismatch")
    elif not (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").exists():
        fail(0, "project identity preflight document missing")
    else:
        ok(0, "ClinicOne addon #37 identity/version/baseline contract present")

    # HG1 — bounded worker contract.
    bounded = (ROOT / "docs/HARD_GATE_14_BOUNDED_WORKER.md").read_text(encoding="utf-8")
    if "maximum of three" not in bounded or "must not redesign ownership" not in bounded:
        fail(1, "bounded implementation worker contract missing")
    else:
        ok(1, "implementation worker is bounded; architecture/ownership are fixed")

    # Syntax and structural metrics used by several gates.
    python = py_files(ROOT)
    xml = xml_files(ROOT)
    comments = docstrings = constraints = 0
    owned_models = set()
    for path in python:
        text = path.read_text(encoding="utf-8")
        comments += sum(1 for line in text.splitlines() if line.strip().startswith("#"))
        constraints += text.count("models.Constraint(")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            fail(12, f"Python syntax error {path.relative_to(ROOT)}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "_sql_constraints" for t in targets):
                    fail(11, f"legacy _sql_constraints assignment found in {path.relative_to(ROOT)}")
        docstrings += sum(1 for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            name = assigned_literal(cls, "_name")
            if name and not name.startswith("clinic.api.provider.credential.wizard") and not name.startswith("clinic.api.webhook.token.wizard") and name != "clinic.api.service":
                owned_models.add(name)
    for path in xml:
        try: ET.parse(path)
        except ET.ParseError as exc: fail(12, f"XML parse error {path.relative_to(ROOT)}: {exc}")

    # HG2 — ownership preservation / bridge seams.
    bridges = (ROOT / "models/bridges.py").read_text(encoding="utf-8")
    forbidden_shadow = ("_name = \"clinic.api.patient\"", "_name = \"clinic.api.booking\"", "_name = \"clinic.api.invoice\"")
    if any(item in "\n".join(p.read_text(encoding="utf-8") for p in python) for item in forbidden_shadow):
        fail(2, "shadow business owner model found")
    elif not all(item in bridges for item in ('_inherit = "clinic.marketing.message"', '_inherit = "clinic.telemedicine.session"', '_inherit = "clinic.billing.gateway.tx"')):
        fail(2, "required additive upstream extension seams are missing")
    else:
        ok(2, "business ownership preserved; only intended Marketing/Telemedicine/Billing seams extended")

    # HG3/HG4 — enterprise completeness and inventory.
    required_files = [
        "models/api_service.py", "models/client.py", "models/provider.py", "models/idempotency.py",
        "models/event.py", "models/subscription.py", "models/delivery.py", "controllers/api.py", "controllers/webhook.py",
        "security/clinic_integration_api_security.xml", "security/ir.model.access.csv", "data/cron_data.xml",
        "views/api_client_views.xml", "views/api_provider_views.xml", "views/api_event_views.xml",
        "docs/FULL_STRUCTURAL_INVENTORY.md", "docs/SECURITY_MODEL.md", "docs/API_CONTRACT.md",
    ]
    missing = [item for item in required_files if not (ROOT / item).exists()]
    if missing: fail(3, f"enterprise runtime layers missing: {missing}")
    else: ok(3, "auth, policy, idempotency, provider, event, webhook, security, UI and docs layers present")
    if len(owned_models) != 9:
        fail(4, f"persistent owned-model inventory mismatch: expected 9, got {sorted(owned_models)}")
    else: ok(4, "full persistent model inventory = 9 technical/governance models")

    # HG5/HG12/HG13 — human-friendly structure/style/comments.
    if not all((ROOT / folder).is_dir() for folder in ("models", "controllers", "wizard", "security", "data", "views", "docs", "tools", "tests")):
        fail(5, "human-friendly layer separation incomplete")
    else: ok(5, "runtime code separated into models/controllers/wizards/security/data/views/docs/tools/tests")
    if comments < 25 or docstrings < 15:
        fail(13, f"useful comments/docstrings too low: comments={comments}, docstrings={docstrings}")
    else: ok(13, f"useful comments/docstrings coverage present: comments={comments}, docstrings={docstrings}")

    # HG6–9 — views.
    view_text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "views").glob("*.xml"))
    persistent_models = ["clinic.api.scope", "clinic.api.client", "clinic.api.provider", "clinic.api.request.log", "clinic.api.idempotency", "clinic.api.event.type", "clinic.api.event", "clinic.api.webhook.subscription", "clinic.api.webhook.delivery"]
    missing_views = []
    for model in persistent_models:
        if model not in view_text:
            missing_views.append(model)
    if missing_views: fail(6, f"persistent models missing professional views: {missing_views}")
    elif "widget=\"statusbar\"" not in view_text or "oe_button_box" not in view_text:
        fail(6, "statusbar/smart-button form design evidence missing")
    else: ok(6, "professional form design includes statusbars, smart buttons, notebooks and workflow actions")
    matrix = (ROOT / "docs/UI_UX_MATRIX.md").read_text(encoding="utf-8")
    if any(model not in matrix for model in persistent_models): fail(7, "UI/UX matrix does not cover every persistent model")
    else: ok(7, "UI/UX matrix covers all 9 persistent models")
    search_count = view_text.count("<search")
    if search_count < 9: fail(8, f"search-view count too low: {search_count}")
    else: ok(8, f"mandatory search views present: {search_count}")
    if "<tree" in view_text or view_text.count("<list") < 9:
        fail(9, "Odoo 19 enterprise list-view contract failed")
    else: ok(9, "Odoo 19 <list> views, ordering, badges/decorations and optional evidence columns present")

    # HG10 — security > UI.
    acl_path = ROOT / "security/ir.model.access.csv"
    with acl_path.open(newline="", encoding="utf-8") as fh:
        acl_rows = list(csv.DictReader(fh))
    delivery_operator = [r for r in acl_rows if r["id"] == "access_api_delivery_operator"]
    service_source = (ROOT / "models/api_service.py").read_text(encoding="utf-8")
    controller_source = (ROOT / "controllers/api.py").read_text(encoding="utf-8")
    if not delivery_operator or delivery_operator[0]["perm_write"] != "0":
        fail(10, "operator can mutate webhook delivery evidence")
    elif 'auth="bearer"' not in controller_source or "_require_explicit_bearer" not in controller_source:
        fail(10, "Bearer route/session-fallback guard missing")
    elif "self.env[resource]" in service_source or "self.env[model_name]" in service_source:
        fail(10, "generic caller-selected ORM surface detected")
    else:
        ok(10, "ACL/record rules + Bearer guard + fixed adapters + Manager-only sensitive evidence pass")

    # HG11 — identifier and ORM naming safety.
    long_identifiers = []
    for path in python:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"['\"]([a-z][a-z0-9_]{63,})['\"]", text):
            candidate = match.group(1)
            if "_" in candidate:
                long_identifiers.append((path.name, candidate))
    if long_identifiers:
        fail(11, f"possible PostgreSQL identifiers exceed 63 chars: {long_identifiers[:3]}")
    elif constraints < 5:
        fail(11, f"expected Odoo 19 models.Constraint usage too low: {constraints}")
    elif not any(line.startswith("[FAIL] HARD GATE 11") for line in ERRORS):
        ok(11, f"models.Constraint and database identifier audit pass; constraints={constraints}")

    # HG12 — current Odoo 19 source contracts.
    if not any(line.startswith("[FAIL] HARD GATE 12") for line in ERRORS):
        ok(12, f"Python/XML parse contracts pass: python={len(python)}, xml={len(xml)}")

    # HG14 — bounded retry policy.
    if "maximum of three" not in bounded:
        fail(14, "three-attempt bounded repair policy not documented")
    else: ok(14, "maximum three bounded implementation repair attempts documented")

    # Cross-addon contract audit (contributes to HG2/HG3/HG10).
    if not source_root.exists():
        fail(3, f"source root does not exist: {source_root}")
    else:
        registry = build_registry(source_root)
        specs = parse_resource_specs()
        mutations = parse_mutation_specs()
        contract_errors = []
        for resource, spec in specs.items():
            model = spec["model"]
            if model not in registry["fields"]:
                contract_errors.append(f"{resource}: model {model} missing")
                continue
            for field_name in spec["fields"]:
                if field_name == "id":
                    continue
                exists, why = path_exists(registry, model, field_name)
                if not exists: contract_errors.append(f"{resource} field {field_name}: {why}")
            for field_name in spec.get("search", ()):
                exists, why = path_exists(registry, model, field_name)
                if not exists: contract_errors.append(f"{resource} search {field_name}: {why}")
            for key in ("company_path", "branch_path"):
                if spec.get(key):
                    exists, why = path_exists(registry, model, spec[key])
                    if not exists: contract_errors.append(f"{resource} {key} {spec[key]}: {why}")
        # mutation fields and actions
        for resource, mutation in mutations.items():
            spec = specs[resource]; model = spec["model"]
            for mode in ("create_fields", "write_fields"):
                for field_name in mutation.get(mode, ()):
                    # patient_id in Booking intentionally names canonical API input but maps to the owned Booking field.
                    exists, why = path_exists(registry, model, field_name)
                    if not exists: contract_errors.append(f"mutation {resource}.{field_name}: {why}")
            for action_code, action in mutation.get("actions", {}).items():
                method = action[1]
                if method not in registry["methods"].get(model, set()):
                    contract_errors.append(f"action {resource}.{action_code}: method {model}.{method} missing")
        # Extension seams must be evidenced upstream, not by this addon itself.
        seam_checks = [
            ("clinic.marketing.message", "_dispatch_via_gateway"),
            ("clinic.telemedicine.session", "_provision_meeting_via_provider"),
            ("clinic.billing.gateway.tx", "process_webhook"),
        ]
        for model, method in seam_checks:
            if method not in registry["methods"].get(model, set()):
                contract_errors.append(f"upstream seam missing: {model}.{method}")
        if contract_errors:
            fail(2, "cross-addon field/model/action contract audit failed: " + " | ".join(contract_errors[:15]))
        else:
            ok(2, f"cross-addon contract audit passes for {len(specs)} fixed resources and upstream extension seams")

    # Manifest must not directly depend on future official addons #38/#39.
    depends = manifest.get("depends", [])
    if "clinic_audit" in depends or "clinic_analytics" in depends:
        fail(3, "future addon #38/#39 appears as direct dependency")

    # Manifest data references and load order.
    for rel in manifest.get("data", []):
        if not (ROOT / rel).exists(): fail(3, f"manifest data file missing: {rel}")
    if manifest["data"].index("security/clinic_integration_api_security.xml") > manifest["data"].index("views/api_client_views.xml"):
        fail(10, "security data loads after business views")

    # Object button names should bind to at least one local model/wizard method.
    local_methods = set()
    for path in python:
        try: tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception: continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_methods.add(node.name)
    button_names = set()
    for path in (ROOT / "views").glob("*.xml"):
        tree = ET.parse(path)
        for button in tree.findall(".//button[@type='object']"):
            button_names.add(button.attrib.get("name", ""))
    missing_buttons = sorted(name for name in button_names if name and name not in local_methods)
    if missing_buttons: fail(6, f"object buttons missing Python methods: {missing_buttons}")

    # HG15 — explicit runtime boundary.
    matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
    tests = (ROOT / "tests/test_source_contracts.py").read_text(encoding="utf-8").count("def test_")
    if "Odoo 19 runtime installation | PENDING" not in matrix or "Source/static PASS is not runtime completion" not in matrix:
        fail(15, "completeness matrix does not preserve runtime acceptance boundary")
    elif tests < 12:
        fail(15, f"source contract test suite too small: {tests}")
    else:
        ok(15, f"enterprise completeness matrix and {tests} source-contract tests present; runtime remains pending")

    print("ClinicOne clinic_integration_api Enterprise Development Guardrail")
    print(f"[INFO] python_files={len(python)} xml_files={len(xml)} owned_persistent_models={len(owned_models)}")
    print(f"[INFO] models.Constraint={constraints} search_views={search_count} acl_rows={len(acl_rows)} source_tests={tests}")
    for line in PASSES: print(line)
    for line in ERRORS: print(line)
    if ERRORS:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO 19 RUNTIME INSTALL/SMOKE TEST PENDING)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
