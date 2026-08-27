#!/usr/bin/env python3
"""Static Enterprise Development Guardrail for ClinicOne clinic_treatment_catalog.

This is intentionally Odoo-server independent. It protects the finished functional
baseline and enterprise hardening contract; it does not replace target-PC runtime
install/upgrade/smoke testing.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "CLINIC_TREATMENT_CATALOG_BASELINE_CONTRACT.json"
EXPECTED_ADDON = "clinic_treatment_catalog"
EXPECTED_NAME = "ClinicOne - Treatment Catalog"
EXPECTED_VERSION_PREFIX = "19.0."
CUSTOM_MODELS = {
    "clinic.treatment.catalog", "clinic.treatment.category", "clinic.treatment.tag",
    "clinic.treatment.attribute", "clinic.treatment.attribute.value", "clinic.treatment.attribute.line",
    "clinic.treatment.bundle", "clinic.treatment.bundle.line", "clinic.treatment.pricelist",
    "clinic.treatment.pricelist.item", "clinic.treatment", "clinic.consent.template",
    "clinic.consent.template.item", "clinic.consent.template.version", "clinic.consent.request",
    "clinic.consent.request.item",
}
REQUIRED_GATES = list(range(16))
REQUIRED_SEQUENCES = {
    "seq_treatment_code", "seq_treatment_category_code", "seq_treatment_tag_code",
    "seq_treatment_bundle_code", "seq_treatment_pricelist_code", "seq_treatment_attribute_code",
    "seq_treatment_attribute_value_code", "seq_treatment_pricelist_item_code", "seq_consent_request",
}

class GateFailure(Exception):
    pass

def fail(message: str) -> None:
    raise GateFailure(message)

def manifest() -> dict:
    try:
        return ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Manifest parse failed: {exc}")

def parse_python(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        fail(f"Python parse failed: {path.relative_to(ROOT)}: {exc}")

def inventory_classes(files: list[str]) -> dict[str, dict]:
    result = {}
    for rel in files:
        path = ROOT / rel
        if not path.is_file():
            fail(f"Baseline source file missing: {rel}")
        tree = parse_python(path)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            fields, methods = set(), set()
            model, inherits = None, []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(item.name)
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id in {"_name", "_inherit"}:
                            try:
                                value = ast.literal_eval(item.value)
                            except Exception:
                                value = None
                            if target.id == "_name":
                                model = value if isinstance(value, str) else None
                            elif isinstance(value, str):
                                inherits = [value]
                            elif isinstance(value, list):
                                inherits = [x for x in value if isinstance(x, str)]
                        if isinstance(item.value, ast.Call):
                            fn = item.value.func
                            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "fields":
                                fields.add(target.id)
            result[f"{rel}::{node.name}"] = {
                "model": model,
                "inherits": inherits,
                "fields": fields,
                "methods": methods,
            }
    return result

def manifest_docs(man: dict):
    docs = []
    for rel in man.get("data", []) + man.get("demo", []):
        p = ROOT / rel
        if not p.is_file():
            fail(f"Manifest references missing file: {rel}")
        if p.name.startswith("0"):
            fail(f"Backup file beginning with 0 is loaded by manifest: {rel}")
        if p.suffix == ".xml":
            try:
                docs.append((rel, ET.parse(p).getroot()))
            except ET.ParseError as exc:
                fail(f"XML parse failed: {rel}: {exc}")
        elif p.suffix == ".csv":
            try:
                list(csv.DictReader(p.open(encoding="utf-8")))
            except Exception as exc:
                fail(f"CSV parse failed: {rel}: {exc}")
    return docs

def view_matrix(docs) -> dict[str, set[str]]:
    matrix = {}
    for _rel, doc in docs:
        for rec in doc.findall(".//record[@model='ir.ui.view']"):
            mf = rec.find("./field[@name='model']")
            af = rec.find("./field[@name='arch']")
            if mf is None or af is None or not len(af):
                continue
            model = (mf.text or "").strip()
            matrix.setdefault(model, set()).add(af[0].tag)
    return matrix

def all_source_text(files: list[str]) -> str:
    return "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in files)

# HARD GATE 0
def gate0(man: dict, contract: dict) -> None:
    if ROOT.name != EXPECTED_ADDON:
        fail(f"Project identity mismatch: folder is {ROOT.name!r}")
    if man.get("name") != EXPECTED_NAME:
        fail(f"Manifest identity mismatch: {man.get('name')!r}")
    if not str(man.get("version", "")).startswith(EXPECTED_VERSION_PREFIX):
        fail(f"Manifest is not Odoo 19 version: {man.get('version')!r}")
    for key, expected in {
        "project": "ClinicOne", "addon": EXPECTED_ADDON, "target_platform": "Odoo 19 CE",
        "functional_baseline_status": "FINISHED_ACTIVE_ON_NOTEBOOK",
    }.items():
        if contract.get(key) != expected:
            fail(f"Identity contract mismatch for {key}: {contract.get(key)!r}")

# HARD GATE 1
def gate1() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for token in ["LIMITED_IMPLEMENTATION_WORKER", "an architect", "a simplifier", "endless retry engine"]:
        if token not in text:
            fail(f"Codex role guardrail token missing: {token}")

# HARD GATE 2
def gate2(man: dict, contract: dict) -> None:
    expected = contract["expected_manifest_dependencies"]
    if man.get("depends") != expected:
        fail(f"Dependency contract changed. Expected {expected!r}; got {man.get('depends')!r}")
    current = inventory_classes(contract["active_source_files"])
    for base in contract["baseline_classes"]:
        key = base["key"]
        if key not in current:
            fail(f"Baseline class missing: {key}")
        cur = current[key]
        missing_fields = sorted(set(base["fields"]) - cur["fields"])
        missing_methods = sorted(set(base["methods"]) - cur["methods"])
        if missing_fields:
            fail(f"{key}: baseline fields removed/renamed: {missing_fields}")
        if missing_methods:
            fail(f"{key}: baseline methods removed/renamed: {missing_methods}")
    # Preserve the intentionally dormant import closure.
    models_init = (ROOT / "models" / "__init__.py").read_text(encoding="utf-8")
    if re.search(r"(?m)^\s*from \. import engines\s*$", models_init):
        fail("Dormant engines were activated without architecture decision")
    bridges_init = (ROOT / "models" / "bridges" / "__init__.py").read_text(encoding="utf-8")
    for forbidden in ["bridge_booking", "bridge_billing", "bridge_inventory", "bridge_reports"]:
        if re.search(rf"(?m)^\s*from \. import {forbidden}\s*$", bridges_init):
            fail(f"Dormant bridge activated: {forbidden}")
    for required in ["bridge_pricing", "integration_consent"]:
        if not re.search(rf"(?m)^\s*from \. import {required}\s*$", bridges_init):
            fail(f"Baseline active bridge missing: {required}")

# HARD GATE 3
def gate3(man: dict) -> None:
    required = [
        "security/clinic_treatment_catalog_security.xml", "security/ir.model.access.csv",
        "data/treatment_sequences.xml", "views/treatment_views.xml", "views/treatment_master_views.xml",
        "views/treatment_attribute_views.xml", "views/treatment_bundle_views.xml",
        "views/treatment_pricelist_views.xml", "views/consent_views.xml", "views/treatment_catalog_menus.xml",
    ]
    for rel in required:
        if rel not in man.get("data", []):
            fail(f"Enterprise completeness file is not loaded: {rel}")
    seq_doc = ET.parse(ROOT / "data" / "treatment_sequences.xml").getroot()
    ids = {rec.get("id") for rec in seq_doc.findall(".//record[@model='ir.sequence']")}
    missing = sorted(REQUIRED_SEQUENCES - ids)
    if missing:
        fail(f"Existing sequence contracts still missing: {missing}")
    combined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in man.get("data", []) if rel.endswith(".xml"))
    for xid in ["action_treatment_tree", "action_treatment_pricelist_item"]:
        if f'id="{xid}"' not in combined:
            fail(f"Existing source action XML contract missing: {xid}")

    # Cross-addon presentation IDs are allowed only through defensive hooks.
    # clinic_base.menu_root is not a runtime XML-ID in the current baseline.
    menu_text = (ROOT / "views" / "treatment_catalog_menus.xml").read_text(encoding="utf-8")
    if 'parent="clinic_base.menu_root"' in menu_text:
        fail("Fragile manifest-loaded parent clinic_base.menu_root must not be restored")
    menu_doc = ET.parse(ROOT / "views" / "treatment_catalog_menus.xml").getroot()
    root_menu = menu_doc.find(".//menuitem[@id='menu_treatment_catalog']")
    if root_menu is None:
        fail("Treatment Catalog root menu XML-ID is missing")
    if root_menu.get("parent"):
        fail("Treatment Catalog runtime root must remain locally installable without an external parent")

# HARD GATE 4
def gate4() -> None:
    text = (ROOT / "docs" / "CLINIC_TREATMENT_CATALOG_STRUCTURAL_INVENTORY.md").read_text(encoding="utf-8")
    for model in CUSTOM_MODELS:
        if f"`{model}`" not in text:
            fail(f"Structural inventory missing model {model}")

# HARD GATE 5
def gate5() -> None:
    required = [
        "models/treatment.py", "models/treatment_category.py", "models/treatment_tag.py",
        "models/treatment_attribute.py", "models/treatment_bundle.py", "models/treatment_pricelist.py",
        "models/treatment_pricelist_item.py", "models/treatment_public.py",
        "views/treatment_views.xml", "views/treatment_master_views.xml", "views/treatment_attribute_views.xml",
        "views/treatment_bundle_views.xml", "views/treatment_pricelist_views.xml", "views/consent_views.xml",
    ]
    missing = [r for r in required if not (ROOT / r).is_file()]
    if missing:
        fail(f"Human-friendly domain structure incomplete: {missing}")

# HARD GATE 6
def gate6(docs) -> None:
    xml = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel, _ in docs)
    required_tokens = [
        'name="action_open_pricelist_items" type="object" class="oe_stat_button"',
        'name="action_open_catalog_record" type="object"',
        'name="action_request" type="object"',
        'name="state" widget="statusbar"',
        '<notebook>',
    ]
    for token in required_tokens:
        if token not in xml:
            fail(f"Professional form contract missing token: {token}")

# HARD GATES 7/8/9
def gate789(matrix: dict[str, set[str]]) -> None:
    for model in CUSTOM_MODELS:
        types = matrix.get(model, set())
        for view_type in ["search", "list", "form"]:
            if view_type not in types:
                fail(f"{model}: required {view_type} view missing")
    # No legacy tree architecture in enterprise views.
    for p in (ROOT / "views").glob("*.xml"):
        text = p.read_text(encoding="utf-8")
        if "<tree" in text or "</tree>" in text:
            fail(f"Legacy tree architecture found in {p.name}")

# HARD GATE 10
def gate10() -> None:
    rows = list(csv.DictReader((ROOT / "security" / "ir.model.access.csv").open(encoding="utf-8")))
    model_ids = {row["model_id:id"].removeprefix("model_").replace("_", ".") for row in rows}
    # Exact string conversion is ambiguous for model underscores, so count + explicit expected model_id names.
    if len(rows) != 16:
        fail(f"ACL coverage must be 16/16; found {len(rows)}")
    expected_ids = {"model_" + m.replace(".", "_") for m in CUSTOM_MODELS}
    actual_ids = {row["model_id:id"] for row in rows}
    if expected_ids != actual_ids:
        fail(f"ACL model coverage mismatch; missing={sorted(expected_ids-actual_ids)}")
    if any(row["group_id:id"] != "base.group_user" for row in rows):
        fail("Unexpected/invented ACL group architecture detected")
    rules = ET.parse(ROOT / "security" / "clinic_treatment_catalog_security.xml").getroot().findall(".//record[@model='ir.rule']")
    if len(rules) != 13:
        fail(f"Company record-rule coverage expected 13, found {len(rules)}")
    for p in [ROOT / "security" / "ir.model.access.csv", ROOT / "security" / "clinic_treatment_catalog_security.xml"]:
        text = p.read_text(encoding="utf-8")
        if "base.group_public" in text or "base.group_portal" in text:
            fail("Public/portal medical catalog access was added without security decision")

# HARD GATE 11
def gate11(contract: dict) -> None:
    text = all_source_text(contract["active_source_files"])
    if "_sql_constraints" in text:
        fail("Legacy _sql_constraints remains in active source")

    for rel in [
        "models/treatment.py",
        "models/treatment_bundle.py",
        "models/treatment_pricelist.py",
    ]:
        source = (ROOT / rel).read_text(encoding="utf-8")
        field_pattern = re.compile(
            r"is_currently_valid\s*=\s*fields\.Boolean\((.*?)\n\s*\)",
            re.S,
        )
        match = field_pattern.search(source)
        if not match or 'search="_search_is_currently_valid"' not in match.group(1):
            fail(f"{rel}: dynamic is_currently_valid is not searchable")
        if "def _search_is_currently_valid(self, operator, value):" not in source:
            fail(f"{rel}: validity search method missing")

    # PostgreSQL identifiers are limited to 63 bytes; flag long explicit ORM names.
    for rel in contract["active_source_files"]:
        source = (ROOT / rel).read_text(encoding="utf-8")
        for candidate in re.findall(r"[\"']([a-z][a-z0-9_]{63,})[\"']", source):
            if "_" in candidate:
                fail(f"{rel}: possible database identifier exceeds 63 characters: {candidate}")

# HARD GATE 12
def gate12(contract: dict) -> None:
    text = all_source_text(contract["active_source_files"])
    forbidden = [
        "_sql_constraints", "def name_search(self, name, args=None", ".read_group(",
        "_get_products_price(", '"view_mode": "tree,form"', '"uom_po_id"',
        '"property_cost_method"', '"discount_policy"',
    ]
    for token in forbidden:
        if token in text:
            fail(f"Odoo 19/human-style forbidden token remains active: {token}")
    count = text.count("models.Constraint(")
    if count != 15:
        fail(f"Expected 15 Odoo 19 models.Constraint objects; found {count}")
    if 'def name_search(self, name="", domain=None' not in text:
        fail("Odoo 19 name_search(domain=None) migration not found")

# HARD GATE 13
def gate13() -> None:
    review = (ROOT / "docs" / "CLINIC_TREATMENT_CATALOG_ODOO19_REVIEW.md").read_text(encoding="utf-8")
    for rationale in ["optional Sale extension", "Existing-code contract repairs", "Dormant"]:
        if rationale not in review:
            fail(f"Useful-rationale documentation missing: {rationale}")

# HARD GATE 14
def gate14(contract: dict) -> None:
    if contract.get("max_focused_repair_attempts_per_blocker") != 3:
        fail("Retry contract is not exactly 3 attempts")
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for token in ["MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3", "MOVE_FORWARD_READY: NO", "STOP"]:
        if token not in text:
            fail(f"Retry-limit guardrail token missing: {token}")

# HARD GATE 15
def gate15() -> None:
    path = ROOT / "docs" / "CLINIC_TREATMENT_CATALOG_ENTERPRISE_COMPLETENESS_MATRIX.md"
    if not path.is_file():
        fail("Enterprise completeness matrix missing")
    text = path.read_text(encoding="utf-8")
    for gate in REQUIRED_GATES:
        if f"| {gate} |" not in text:
            fail(f"Enterprise completeness matrix missing gate {gate}")


def main() -> int:
    try:
        man = manifest()
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        # Global source parse: backups beginning with 0 must not be shipped.
        for p in ROOT.rglob("*"):
            if p.is_file() and p.name.startswith("0"):
                fail(f"Backup file beginning with 0 shipped in hardened addon: {p.relative_to(ROOT)}")
            if p.is_file() and p.suffix == ".py":
                parse_python(p)
        docs = manifest_docs(man)
        matrix = view_matrix(docs)
        checks = [
            ("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT", lambda: gate0(man, contract)),
            ("HARD_GATE_1_CODEX_BUKAN_ARCHITECT", gate1),
            ("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", lambda: gate2(man, contract)),
            ("HARD_GATE_3_ENTERPRISE_COMPLETENESS", lambda: gate3(man)),
            ("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY", gate4),
            ("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE", gate5),
            ("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN", lambda: gate6(docs)),
            ("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL", lambda: gate789(matrix)),
            ("HARD_GATE_8_SEARCH_VIEW_WAJIB", lambda: gate789(matrix)),
            ("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY", lambda: gate789(matrix)),
            ("HARD_GATE_10_SECURITY_OVER_UI", gate10),
            ("HARD_GATE_11_DATABASE_IDENTIFIER_ORM_NAMING_SAFETY", lambda: gate11(contract)),
            ("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY", lambda: gate12(contract)),
            ("HARD_GATE_13_USEFUL_COMMENTS", gate13),
            ("HARD_GATE_14_CODEX_RETRY_LIMIT", lambda: gate14(contract)),
            ("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX", gate15),
        ]
        print("=" * 78)
        print("CLINIC_TREATMENT_CATALOG ENTERPRISE DEVELOPMENT HARD GATE")
        print("=" * 78)
        for name, fn in checks:
            fn()
            print(f"PASS: {name}")
        print("-" * 78)
        print("PASS: HARD GATES 0-15")
        print("CLINIC_TREATMENT_CATALOG_STATIC_MOVE_FORWARD_READY: YES")
        print("RUNTIME_GATE_REQUIRED: YES")
        print("CLINIC_TREATMENT_CATALOG_MOVE_FORWARD_READY: PENDING")
        return 0
    except (GateFailure, OSError, json.JSONDecodeError) as exc:
        print("GUARDRAIL: FAIL")
        print(f"BLOCKER: {exc}")
        print("CLINIC_TREATMENT_CATALOG_STATIC_MOVE_FORWARD_READY: NO")
        return 1

if __name__ == "__main__":
    sys.exit(main())

