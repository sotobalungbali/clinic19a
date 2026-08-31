
#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "CLINIC_DOCTOR_BASELINE_CONTRACT.json"

def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)

def pass_line(msg: str) -> None:
    print(f"PASS: {msg}")

def load_manifest():
    text = (ROOT / "__manifest__.py").read_text(encoding="utf-8")
    try:
        return ast.literal_eval(text[text.index("{"):])
    except Exception as exc:
        fail(f"manifest parse: {exc}")

def imported_modules():
    tree = ast.parse((ROOT / "models" / "__init__.py").read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            found.extend(alias.name for alias in node.names)
    return found

def model_inventory(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        name = inherit = None
        fields = {}
        methods = []
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
                            name = value
                        else:
                            inherit = value
                    if (
                        isinstance(item.value, ast.Call)
                        and isinstance(item.value.func, ast.Attribute)
                        and isinstance(item.value.func.value, ast.Name)
                        and item.value.func.value.id == "fields"
                    ):
                        fields[target.id] = item.value.func.attr
            elif isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        key = name or (f"inherit:{inherit}" if inherit else f"class:{node.name}")
        out.append((key, sorted(fields), sorted(methods)))
    return out

def count_constraints(active_paths):
    count = 0
    legacy = []
    for path in active_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_sql_constraints":
                        legacy.append(str(path.relative_to(ROOT)))
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "models"
                and node.func.attr == "Constraint"
            ):
                count += 1
    return count, legacy

def tree_view_modes(active_paths):
    hits = []
    for path in active_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, val in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant) and key.value == "view_mode"
                        and isinstance(val, ast.Constant) and isinstance(val.value, str)
                        and "tree" in val.value.split(",")
                    ):
                        hits.append((str(path.relative_to(ROOT)), node.lineno, val.value))
    return hits

def main():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    # Compile every non-backup Python file. Backup files starting with 0 are ignored.
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0"):
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            fail(f"Python compile {path.relative_to(ROOT)}: {exc}")
    pass_line("PYTHON_COMPILE")

    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        try:
            ET.parse(path)
        except Exception as exc:
            fail(f"XML parse {path.relative_to(ROOT)}: {exc}")
    pass_line("XML_PARSE")

    manifest = load_manifest()
    if manifest.get("version") != "19.0.1.0.2":
        fail(f"manifest version changed: {manifest.get('version')!r}")
    if manifest.get("depends") != contract["manifest_depends_exact"]:
        fail(f"manifest dependencies changed:\nactual={manifest.get('depends')}\nexpected={contract['manifest_depends_exact']}")
    pass_line("MANIFEST_CONTRACT")

    modules = imported_modules()
    if modules != contract["active_model_modules"]:
        fail(f"active model imports changed: actual={modules}, expected={contract['active_model_modules']}")
    pass_line("ACTIVE_IMPORT_CONTRACT")

    active_paths = [ROOT / "models" / f"{name}.py" for name in modules]
    actual_models = {}
    for path in active_paths:
        for key, fields, methods in model_inventory(path):
            actual_models[key] = {"fields": fields, "methods": methods}

    for key, expected in contract["expected_models"].items():
        if key not in actual_models:
            fail(f"model/inheritance missing: {key}")
        if actual_models[key]["fields"] != expected["fields"]:
            fail(f"field contract changed for {key}")
        if actual_models[key]["methods"] != expected["methods"]:
            fail(f"method contract changed for {key}")
    if set(actual_models) != set(contract["expected_models"]):
        fail(f"active model set changed: actual={sorted(actual_models)}, expected={sorted(contract['expected_models'])}")
    pass_line("MODEL_FIELD_METHOD_CONTRACT")

    count, legacy = count_constraints(active_paths)
    if legacy:
        fail(f"legacy _sql_constraints remain: {legacy}")
    if count != contract["expected_models_constraint_count"]:
        fail(f"models.Constraint count={count}, expected={contract['expected_models_constraint_count']}")
    pass_line("ODOO19_CONSTRAINT_CONTRACT")

    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        if re.search(r"def\s+name_search\s*\([^)]*\bargs\s*=", text):
            fail(f"legacy name_search args signature: {path.relative_to(ROOT)}")
    if tree_view_modes(active_paths):
        fail(f"legacy tree action view_mode remains: {tree_view_modes(active_paths)}")
    pass_line("ODOO19_API_STATIC_COMPATIBILITY")

    # Critical sanctioned restorations / dependency integrity.
    appt = (ROOT / "models" / "appointment.py").read_text(encoding="utf-8")
    if not re.search(r"patient_id\s*=\s*fields\.Many2one\(\s*[\"']clinic\.patient[\"']", appt, re.S):
        fail("clinic.appointment.patient_id restoration missing")
    if 'if "treatment_session_id" in rec._fields:' not in appt:
        fail("optional treatment_session_id guard missing")
    if "account" not in manifest["depends"] or "sale" not in manifest["depends"]:
        fail("required account/sale dependency correction missing")
    pass_line("CRITICAL_HARDENING_CONTRACT")

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required_markers = [
        "CODEX_ROLE: LIMITED_IMPLEMENTATION_WORKER",
        "NOT_ARCHITECT: YES",
        "NOT_SIMPLIFIER: YES",
        "NOT_UNBOUNDED_RETRY_ENGINE: YES",
        "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER: 3",
        "MOVE_FORWARD_READY: NO",
    ]
    missing = [m for m in required_markers if m not in agents]
    if missing:
        fail(f"AGENTS hard-gate markers missing: {missing}")
    pass_line("ENTERPRISE_DEVELOPMENT_GUARDRAIL")

    print("=" * 72)
    print("CLINIC_DOCTOR_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("=" * 72)

if __name__ == "__main__":
    main()

