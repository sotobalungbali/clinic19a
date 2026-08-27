#!/usr/bin/env python3
"""Static hard-gate runner for ClinicOne clinic_package."""

from __future__ import annotations

import ast
import csv
import io
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_MODELS = {
    "clinic.package",
    "clinic.package.pricing",
    "clinic.package.policy",
    "clinic.package.benefit",
    "clinic.package.allocation",
    "clinic.package.usage",
    "clinic.package.voucher",
    "clinic.package.integration.event",
}
COMPANY_CONFIG_FIELDS = {
    "clinic_pkg_default_pricing_id",
    "clinic_pkg_default_policy_id",
    "clinic_pkg_voucher_prefix",
    "clinic_pkg_voucher_code_length",
    "clinic_pkg_voucher_valid_days",
    "clinic_pkg_auto_expire_allocations",
    "clinic_pkg_auto_expire_vouchers",
}


def fail(message):
    print("[FAIL]", message)
    raise SystemExit(1)


def active_files(pattern):
    return [
        path for path in ROOT.rglob(pattern)
        if not path.name.startswith("0")
        and "__pycache__" not in path.parts
    ]


py_files = active_files("*.py")
xml_files = active_files("*.xml")

for path in py_files:
    try:
        compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    except Exception as exc:
        fail(f"Python compile: {path.relative_to(ROOT)}: {exc}")

for path in xml_files:
    try:
        ET.parse(path)
    except Exception as exc:
        fail(f"XML parse: {path.relative_to(ROOT)}: {exc}")

manifest_path = ROOT / "__manifest__.py"
try:
    manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8-sig"))
except Exception as exc:
    fail(f"manifest parse: {exc}")

for rel in manifest.get("data", []):
    if not (ROOT / rel).is_file():
        fail(f"manifest data file missing: {rel}")

all_python = "\n".join(path.read_text(encoding="utf-8-sig") for path in py_files)
if re.search(r"^\s*_sql_constraints\s*=", all_python, re.M):
    fail("legacy executable _sql_constraints declaration found")

constraint_count = len(re.findall(r"models\.Constraint\s*\(", all_python))

# Odoo concrete classes must use one Python ORM base only.
for path in py_files:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        orm_bases = []
        for base in node.bases:
            text = ast.unparse(base)
            if text.endswith("models.Model") or text in {
                "models.Model", "models.TransientModel", "models.AbstractModel"
            }:
                orm_bases.append(text)
        if orm_bases and len(node.bases) > 1:
            fail(
                f"unsafe Python multiple base on Odoo class "
                f"{path.relative_to(ROOT)}:{node.name}"
            )

# Public package config proxies on res.company must be explicitly store=False.
config_text = (ROOT / "models" / "res_config_settings.py").read_text(
    encoding="utf-8-sig"
)
for field_name in COMPANY_CONFIG_FIELDS:
    match = re.search(
        rf"{re.escape(field_name)}\s*=\s*fields\.\w+\((.*?)\n\s*\)",
        config_text,
        re.S,
    )
    if not match or "store=False" not in match.group(1):
        fail(f"res.company package setting is not schema-safe: {field_name}")

# Primary Search/List/Form matrix.
matrix = {model: set() for model in PRIMARY_MODELS}
for path in xml_files:
    root = ET.parse(path).getroot()
    for rec in root.iter("record"):
        if rec.get("model") != "ir.ui.view":
            continue
        model_name = None
        arch_field = None
        for field in rec.findall("field"):
            if field.get("name") == "model":
                model_name = (field.text or "").strip()
            elif field.get("name") == "arch":
                arch_field = field
        if model_name not in matrix or arch_field is None:
            continue
        children = list(arch_field)
        if not children:
            continue
        tag = children[0].tag
        if tag in {"search", "list", "form"}:
            matrix[model_name].add(tag)

for model_name, kinds in matrix.items():
    missing = {"search", "list", "form"} - kinds
    if missing:
        fail(f"UI matrix incomplete for {model_name}: missing {sorted(missing)}")

# Object button actions should resolve to a method present in package Python.
method_names = set()
for path in py_files:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_names.add(node.name)

object_buttons = []
for path in xml_files:
    root = ET.parse(path).getroot()
    for button in root.iter("button"):
        if button.get("type") == "object" and button.get("name"):
            object_buttons.append((path, button.get("name")))
missing_methods = sorted(
    {name for _path, name in object_buttons if name not in method_names}
)
if missing_methods:
    fail("object button method(s) missing: " + ", ".join(missing_methods))

# ACL CSV integrity.
acl = ROOT / "security" / "ir.model.access.csv"
raw = acl.read_text(encoding="utf-8-sig")
raw = "\n".join(line for line in raw.splitlines() if line.strip())
reader = csv.DictReader(io.StringIO(raw))
required_headers = {
    "id", "name", "model_id:id", "group_id:id",
    "perm_read", "perm_write", "perm_create", "perm_unlink",
}
if set(reader.fieldnames or []) != required_headers:
    fail(f"unexpected ACL header: {reader.fieldnames}")
list(reader)

# Mandatory regression/migration artefacts.
for rel in (
    "migrations/19.0.3.0.0/pre-10-preserve_company_settings.py",
    "migrations/19.0.3.0.0/post-90-verify_schema.py",
    "docs/ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/INTEGRATION_CONTRACTS.md",
    "AGENTS.md",
):
    if not (ROOT / rel).is_file():
        fail(f"required artefact missing: {rel}")

backup_files = [
    path.relative_to(ROOT) for path in ROOT.rglob("*")
    if path.is_file() and path.name.startswith("0")
]
if backup_files:
    fail("backup-prefix files packaged: " + ", ".join(map(str, backup_files)))

test_text = (ROOT / "tests" / "test_package_enterprise.py").read_text(
    encoding="utf-8-sig"
)
test_count = len(re.findall(r"^\s*def test_", test_text, re.M))

print("clinic_package Enterprise Development Guardrail")
print(f"[INFO] python_files={len(py_files)}")
print(f"[INFO] xml_files={len(xml_files)}")
print(f"[INFO] models.Constraint={constraint_count}")
print(f"[INFO] object_buttons={len(object_buttons)}")
print(f"[INFO] test_methods={test_count}")
print(f"[INFO] primary_ui_matrix={len(PRIMARY_MODELS)}/{len(PRIMARY_MODELS)}")
print("[INFO] stored_res_company_clinic_pkg_fields=0")
print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)")
