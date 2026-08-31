
#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ADDON_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ADDON_ROOT / "docs" / "CLINIC_STAFF_BASELINE_CONTRACT.json"


def fail(msg: str, failures: list[str]) -> None:
    failures.append(msg)


def is_backup_path(rel: Path) -> bool:
    return any(part.startswith("0") for part in rel.parts)


def runtime_source_files() -> list[str]:
    result = []
    for fp in sorted(ADDON_ROOT.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(ADDON_ROOT)
        if is_backup_path(rel):
            continue
        if rel.parts[0] in {"docs", "tools"} or rel.name == "AGENTS.md":
            continue
        result.append(str(rel).replace("\\", "/"))
    return result


def source_models() -> dict:
    result = {}
    for fp in sorted((ADDON_ROOT / "models").glob("*.py")):
        if fp.name.startswith("0"):
            continue
        tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
        rel = str(fp.relative_to(ADDON_ROOT)).replace("\\", "/")
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            model_name = None
            fields = set()
            methods = set()
            constraints = set()
            for item in cls.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "_name":
                            try:
                                model_name = ast.literal_eval(item.value)
                            except Exception:
                                pass
                    if isinstance(item.value, ast.Call):
                        func = item.value.func
                        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                            if func.value.id == "fields":
                                fields.update(
                                    target.id for target in item.targets
                                    if isinstance(target, ast.Name)
                                )
                            elif func.value.id == "models" and func.attr == "Constraint":
                                constraints.update(
                                    target.id for target in item.targets
                                    if isinstance(target, ast.Name)
                                )
                elif isinstance(item, ast.FunctionDef):
                    methods.add(item.name)
            if model_name:
                result[model_name] = {
                    "file": rel,
                    "class": cls.name,
                    "fields": sorted(fields),
                    "methods": sorted(methods),
                    "constraints": sorted(constraints),
                }
    return result


def validate_field_method_refs(failures: list[str]) -> None:
    for fp in sorted((ADDON_ROOT / "models").glob("*.py")):
        if fp.name.startswith("0"):
            continue
        tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
            for item in cls.body:
                if not (isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)):
                    continue
                func = item.value.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "fields"
                ):
                    continue
                for kw in item.value.keywords:
                    if kw.arg not in {"compute", "inverse", "search"}:
                        continue
                    if not (isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)):
                        continue
                    method = kw.value.value
                    if method.startswith("_") and method not in methods:
                        fail(
                            f"{fp.relative_to(ADDON_ROOT)}:{item.lineno}: "
                            f"{kw.arg} references missing method {method} in {cls.name}",
                            failures,
                        )


def main() -> int:
    failures: list[str] = []
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    # Python syntax
    for fp in sorted(ADDON_ROOT.rglob("*.py")):
        rel = fp.relative_to(ADDON_ROOT)
        if is_backup_path(rel):
            continue
        try:
            compile(fp.read_text(encoding="utf-8"), str(fp), "exec")
        except Exception as exc:
            fail(f"Python compile failed: {rel}: {exc}", failures)

    # XML syntax
    for fp in sorted(ADDON_ROOT.rglob("*.xml")):
        rel = fp.relative_to(ADDON_ROOT)
        if is_backup_path(rel):
            continue
        try:
            ET.parse(fp)
        except Exception as exc:
            fail(f"XML parse failed: {rel}: {exc}", failures)

    # Manifest contract
    try:
        manifest = ast.literal_eval((ADDON_ROOT / "__manifest__.py").read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Manifest parse failed: {exc}", failures)
        manifest = {}

    for key in ("version", "depends", "data", "demo"):
        expected = contract["manifest"][key]
        actual = manifest.get(key)
        if actual != expected:
            fail(f"Manifest {key} drift: expected {expected!r}, got {actual!r}", failures)

    # Exact active runtime file contract
    actual_files = runtime_source_files()
    if actual_files != contract["source_files"]:
        missing = sorted(set(contract["source_files"]) - set(actual_files))
        added = sorted(set(actual_files) - set(contract["source_files"]))
        fail(f"Runtime source file drift. Missing={missing}; Added={added}", failures)

    # Exact source model/field/method/constraint contract
    try:
        actual_models = source_models()
    except Exception as exc:
        fail(f"Model inventory failed: {exc}", failures)
        actual_models = {}

    if actual_models != contract["models"]:
        expected_names = set(contract["models"])
        actual_names = set(actual_models)
        if expected_names != actual_names:
            fail(
                f"Model set drift. Missing={sorted(expected_names-actual_names)}; "
                f"Added={sorted(actual_names-expected_names)}",
                failures,
            )
        for name in sorted(expected_names & actual_names):
            if actual_models[name] != contract["models"][name]:
                fail(f"Model contract drift: {name}", failures)

    # Odoo 19 hard patterns
    patterns = {
        "legacy _sql_constraints": re.compile(r"_sql_constraints\s*="),
        "legacy name_search args parameter": re.compile(r"def\s+name_search\s*\([^)]*\bargs\s*="),
        "legacy tree action view_mode": re.compile(r'"view_mode"\s*:\s*["\'][^"\']*\btree\b'),
    }
    for fp in sorted(ADDON_ROOT.rglob("*.py")):
        rel = fp.relative_to(ADDON_ROOT)
        if is_backup_path(rel):
            continue
        content = fp.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            if pattern.search(content):
                fail(f"{label} found in {rel}", failures)

    validate_field_method_refs(failures)

    print("=" * 64)
    print("CLINIC_STAFF ENTERPRISE DEVELOPMENT GUARDRAIL")
    print("=" * 64)
    if failures:
        print("GUARDRAIL: FAIL")
        for item in failures:
            print(f"- {item}")
        print("CLINIC_STAFF_MOVE_FORWARD_READY: NO")
        return 1

    print("PYTHON_COMPILE: PASS")
    print("XML_PARSE: PASS")
    print("MANIFEST_CONTRACT: PASS")
    print("SOURCE_FILE_CONTRACT: PASS")
    print("MODEL_FIELD_METHOD_CONTRACT: PASS")
    print("ODOO19_STATIC_COMPATIBILITY: PASS")
    print("GUARDRAIL: PASS")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_STAFF_STATIC_MOVE_FORWARD_READY: YES")
    return 0


if __name__ == "__main__":
    sys.exit(main())

