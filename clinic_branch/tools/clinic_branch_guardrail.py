#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []

def fail(message: str) -> None:
    ERRORS.append(message)

# Python syntax and Odoo 19 naming rules.
for path in sorted(ROOT.rglob("*.py")):
    if path.name.startswith("0") or "tools" in path.parts or "tests" in path.parts:
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        fail(f"Python syntax: {path.relative_to(ROOT)}: {exc}")
    text = path.read_text(encoding="utf-8")
    if "_sql_constraints" in text:
        fail(f"Legacy _sql_constraints: {path.relative_to(ROOT)}")

# XML well-formedness and required search/list/form coverage.
for path in sorted(ROOT.rglob("*.xml")):
    if path.name.startswith("0"):
        continue
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        fail(f"XML parse: {path.relative_to(ROOT)}: {exc}")

required = {
    "views/branch_views.xml": ("<search", "<list", "<form"),
    "views/branch_location_views.xml": ("<search", "<list", "<form"),
}
for rel, markers in required.items():
    text = (ROOT / rel).read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            fail(f"Missing {marker} in {rel}")

# Database identifier guard. Explicit relation/model constraint attribute names remain short.
for path in sorted((ROOT / "models").glob("*.py")):
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"['\"]([a-z0-9_]{64,})['\"]", text):
        candidate = match.group(1)
        if "_" in candidate:
            fail(f"Possible PostgreSQL identifier >63 chars: {candidate}")

# ACL references and dangerous wildcard access check.
acl = ROOT / "security/ir.model.access.csv"
with acl.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
if not rows:
    fail("ACL is empty")
for row in rows:
    if row["group_id:id"] == "base.group_user" and row["perm_unlink"] == "1":
        fail(f"Base user unlink grant is too broad: {row['id']}")

# Manifest order: security before business views.
manifest = (ROOT / "__manifest__.py").read_text(encoding="utf-8")
if manifest.find("security/clinic_branch_security.xml") > manifest.find("views/branch_views.xml"):
    fail("Security must load before views")

if ERRORS:
    print("CLINIC_BRANCH GUARDRAIL: FAIL")
    for error in ERRORS:
        print(f"- {error}")
    sys.exit(1)

print("CLINIC_BRANCH GUARDRAIL: PASS")
