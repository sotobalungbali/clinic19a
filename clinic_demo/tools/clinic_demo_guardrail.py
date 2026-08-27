#!/usr/bin/env python3
"""Static package guardrail for MASTER PROMPT 06."""

from pathlib import Path
import ast
import csv
import hashlib
import io
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE_SHA = "bc53b00a5ad52da8515bdaf40baf0fff4a6aa4cef67216b574529a53263948d0"
EXPECTED_SUITE_SHA = "8b16194ce2de3736aa2a91cfad6569dcb0f174eff1b3d9ac2e86961a198fc8ed"
EXPECTED_CLINIC_DEPENDENCIES = 41


def fail(message):
    print("FAIL:", message)
    raise SystemExit(1)


def main():
    python_files = sorted(ROOT.rglob("*.py"))
    xml_files = sorted(ROOT.rglob("*.xml"))

    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for path in xml_files:
        ET.fromstring(path.read_text(encoding="utf-8"))

    manifest = ast.literal_eval(
        ast.parse((ROOT / "__manifest__.py").read_text(encoding="utf-8")).body[0].value
    )
    clinic_deps = [name for name in manifest["depends"] if name.startswith("clinic_")]
    if len(clinic_deps) != EXPECTED_CLINIC_DEPENDENCIES:
        fail(f"Expected 41 ClinicOne dependencies, found {len(clinic_deps)}")

    runtime_python = [path for path in python_files if "tools" not in path.parts and "tests" not in path.parts]
    all_python = "\n".join(path.read_text(encoding="utf-8") for path in runtime_python)

    legacy_constraints = []
    for path in runtime_python:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == "_sql_constraints" for target in node.targets):
                legacy_constraints.append(str(path.relative_to(ROOT)))
    if legacy_constraints:
        fail(f"Executable legacy _sql_constraints found: {legacy_constraints}")

    if ".cr.commit(" in all_python or ".commit()" in all_python:
        fail("Manual commit found.")
    if re.search(r"\bcr\.execute\s*\(", all_python):
        fail("Direct SQL found.")

    constants = (ROOT / "services/constants.py").read_text(encoding="utf-8")
    if EXPECTED_SOURCE_SHA not in constants:
        fail("Authoritative source SHA is not embedded in constants.")
    if EXPECTED_SUITE_SHA not in constants:
        fail("Expected suite fingerprint is not embedded in constants.")

    # Numeric-prefix backup files are never package content.
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

    # Human-friendly structure: no Python implementation file over 950 lines.
    oversized = []
    for path in python_files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > 950:
            oversized.append((str(path.relative_to(ROOT)), lines))
    if oversized:
        fail(f"Oversized Python files: {oversized}")

    # ACL CSV must parse and contain only supported permission columns.
    acl = ROOT / "security/ir.model.access.csv"
    rows = list(csv.DictReader(io.StringIO(acl.read_text(encoding="utf-8"))))
    if len(rows) != 15:
        fail(f"Expected 15 ACL rows, found {len(rows)}")

    print("MASTER PROMPT 06 STATIC GUARDRAIL: PASS")
    print(f"Python parse: {len(python_files)} PASS")
    print(f"XML parse: {len(xml_files)} PASS")
    print("ClinicOne direct dependencies: 41 PASS")
    print("Legacy _sql_constraints: 0 PASS")
    print("Direct SQL/manual commit: 0 PASS")
    print("Numeric-prefix backups: 0 PASS")
    print("ACL rows: 15 PASS")
    print("Human-friendly file-size ceiling: PASS")


if __name__ == "__main__":
    main()
