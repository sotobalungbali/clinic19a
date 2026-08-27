#!/usr/bin/env python3
"""ClinicOne clinic_ap Enterprise Development Guardrail (source/static only)."""
from __future__ import annotations

import ast
import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "19.0.3.0.2"
EXPECTED_OWNER_MODELS = {
    "clinic.ap",
    "clinic.ap.line",
    "clinic.ap.aging",
    "clinic.ap.aging.line",
    "clinic.cashflow",
    "clinic.cashflow.bucket",
    "clinic.cashflow.detail",
    "clinic.cashflow.adjustment",
    "clinic.ap.integration.event",
}
HARD_GATES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15]

errors: list[str] = []
infos: list[str] = []

def fail(message: str) -> None:
    errors.append(message)

def info(message: str) -> None:
    infos.append(message)

def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None

def call_name(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""

# ---------------------------------------------------------------------------
# Release hygiene and manifest
# ---------------------------------------------------------------------------
for path in ROOT.rglob("*"):
    if path.is_file() and path.name.startswith("0"):
        fail(f"numeric-prefix backup file present: {path.relative_to(ROOT)}")
    if "__pycache__" in path.parts or path.suffix == ".pyc":
        fail(f"cache artifact present: {path.relative_to(ROOT)}")

manifest_path = ROOT / "__manifest__.py"
try:
    manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
except Exception as exc:
    manifest = {}
    fail(f"manifest cannot be parsed: {exc}")

if manifest.get("version") != EXPECTED_VERSION:
    fail(f"manifest version must be {EXPECTED_VERSION}, got {manifest.get('version')!r}")
if not manifest.get("installable") or not manifest.get("application"):
    fail("manifest must be installable=True and application=True")
for data_file in manifest.get("data", []):
    if not (ROOT / data_file).is_file():
        fail(f"manifest data file missing: {data_file}")

# ---------------------------------------------------------------------------
# Python AST inventory
# ---------------------------------------------------------------------------
python_files = sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)
model_fields: dict[str, set[str]] = defaultdict(set)
model_methods: dict[str, set[str]] = defaultdict(set)
relation_map: dict[tuple[str, str], str] = {}
owner_models: set[str] = set()
sql_object_count = 0
constraint_count = 0
legacy_sql_constraints = 0

for path in python_files:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        fail(f"Python syntax error {path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
        continue

    if "_sql_constraints" in source:
        # Executable declaration check, not documentation strings.
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "_sql_constraints" for t in targets):
                    legacy_sql_constraints += 1

    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        model_name = None
        inherit = None
        for stmt in cls.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                value = stmt.value
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    attr = target.id
                    if attr == "_name":
                        value_lit = literal(value)
                        if isinstance(value_lit, str):
                            model_name = value_lit
                    elif attr == "_inherit":
                        inherit = literal(value)
        target_models: list[str] = []
        if model_name:
            owner_models.add(model_name)
            target_models.append(model_name)
        if isinstance(inherit, str):
            target_models.append(inherit)
        elif isinstance(inherit, (list, tuple)):
            # mixins do not become targets if the class already has _name
            if not model_name:
                target_models.extend(x for x in inherit if isinstance(x, str))

        for stmt in cls.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for target_model in target_models:
                    model_methods[target_model].add(stmt.name)
                continue
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            value = stmt.value
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                attr = target.id
                cname = call_name(value.func) if isinstance(value, ast.Call) else ""
                if cname in {"models.Constraint", "models.Index"}:
                    sql_object_count += 1
                    if cname == "models.Constraint":
                        constraint_count += 1
                    if not attr.startswith("_"):
                        fail(f"Odoo 19 SQL table object attribute must start with _: {path.name}:{cls.name}.{attr}")
                if cname.startswith("fields."):
                    for target_model in target_models:
                        model_fields[target_model].add(attr)
                    if cname in {"fields.Many2one", "fields.One2many", "fields.Many2many"}:
                        comodel = literal(value.args[0]) if value.args else None
                        if isinstance(comodel, str):
                            for target_model in target_models:
                                relation_map[(target_model, attr)] = comodel
                    # Odoo 19: res.currency is global; check_company creates an invalid company domain.
                    if cname == "fields.Many2one" and value.args and literal(value.args[0]) == "res.currency":
                        for kw in value.keywords:
                            if kw.arg == "check_company" and literal(kw.value) is True:
                                fail(f"direct res.currency field uses check_company=True: {path.name}:{cls.name}.{attr}")

        if inherit == "res.partner":
            for stmt in cls.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id == "credit_limit":
                            if isinstance(stmt.value, ast.Call) and call_name(stmt.value.func).startswith("fields."):
                                fail("clinic_ap must not redeclare core res.partner.credit_limit")
                        if isinstance(target, ast.Name) and target.id == "property_supplier_payment_term_id":
                            if isinstance(stmt.value, ast.Call) and call_name(stmt.value.func).startswith("fields."):
                                fail("clinic_ap must not redeclare core property_supplier_payment_term_id")

if legacy_sql_constraints:
    fail(f"executable legacy _sql_constraints declarations found: {legacy_sql_constraints}")
if owner_models != EXPECTED_OWNER_MODELS:
    fail(f"persistent owner model inventory mismatch: expected {sorted(EXPECTED_OWNER_MODELS)}, got {sorted(owner_models)}")

# Mandatory fixed inverse contract.
if "stock_move_id" not in model_fields.get("clinic.ap.line", set()):
    fail("clinic.ap.line.stock_move_id is mandatory for the stock.move inverse / 3-way match contract")

# Search views expose match-state filters; the live computed fields must have explicit search contracts.
for path in (ROOT / "models" / "ap_document.py", ROOT / "models" / "ap_line.py"):
    source = path.read_text(encoding="utf-8")
    match = re.search(r"match_state\s*=\s*fields\.Selection\((.*?)\n\s*\)", source, flags=re.S)
    if not match or 'search="_search_match_state"' not in match.group(1):
        fail(f"computed match_state must define _search_match_state: {path.name}")

# Legacy runtime assumptions found in earlier ClinicOne/Odoo generations.
model_python_files = sorted((ROOT / "models").glob("*.py"))
all_python = "\n".join(p.read_text(encoding="utf-8") for p in model_python_files)
if re.search(r"account\.payment.*?state[^\n]{0,80}posted", all_python, flags=re.I):
    fail("legacy account.payment state='posted' assumption detected")
if re.search(r"\.payment_term_id\.compute\s*\(|account\.payment\.term[^\n]*\.compute\s*\(", all_python):
    fail("legacy account.payment.term.compute(...) call detected")
if "._compute_terms(" not in all_python:
    fail("Odoo 19 payment-term _compute_terms() contract is not used")

# Odoo 19 stock-account valuation contract.
# The former stock.valuation.layer / stock_move.stock_valuation_layer_ids API is
# not part of the Odoo 19 stock_account model contract. AP must value through
# the native stock.move.value field while retaining stock_move_id traceability.
if "stock.valuation.layer" in relation_map.values():
    fail("legacy stock.valuation.layer relational comodel detected; use Odoo 19 stock.move.value")

legacy_svl_attribute_refs = 0
for path in model_python_files:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    legacy_svl_attribute_refs += sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "stock_valuation_layer_ids"
        )
        or (
            isinstance(node, ast.Name)
            and node.id == "stock_valuation_layer_ids"
        )
    )
if legacy_svl_attribute_refs:
    fail("legacy stock_move.stock_valuation_layer_ids executable reference detected")

ap_line_source = (ROOT / "models" / "ap_line.py").read_text(encoding="utf-8")
if "stock_move_id.value" not in ap_line_source:
    fail("clinic.ap.line stock valuation must depend on Odoo 19 stock_move_id.value")

# ---------------------------------------------------------------------------
# XML validation + UI matrix + search contracts
# ---------------------------------------------------------------------------
xml_files = sorted(ROOT.rglob("*.xml"))
ui_matrix: dict[str, set[str]] = defaultdict(set)
object_buttons = 0
button_mismatches: list[str] = []
field_mismatches: list[str] = []

for path in xml_files:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        fail(f"XML parse error {path.relative_to(ROOT)}: {exc}")
        continue
    doc = tree.getroot()

    for elem in doc.iter():
        if elem.tag == "tree":
            fail(f"legacy <tree> tag found: {path.relative_to(ROOT)}")
        if "attrs" in elem.attrib or "states" in elem.attrib:
            fail(f"legacy attrs/states view attribute found: {path.relative_to(ROOT)} <{elem.tag}>")
        if elem.tag == "filter" and not elem.get("name"):
            fail(f"search filter without technical name: {path.relative_to(ROOT)}")

    # Search group schema: only inspect groups under a <search> node.
    for search in doc.iter("search"):
        for group in search.iter("group"):
            if "expand" in group.attrib or "string" in group.attrib:
                fail(f"legacy search <group expand/string> found: {path.relative_to(ROOT)}")

    # No fragile hard inherited ClinicOne cross-addon views.
    text = path.read_text(encoding="utf-8")
    if "inherit_id" in text and re.search(r'ref="clinic_(?!ap\.)[^\"]+"', text):
        fail(f"hard cross-addon ClinicOne inherited view detected: {path.relative_to(ROOT)}")

    # Find ir.ui.view records and their architecture.
    for record in doc.findall(".//record"):
        if record.get("model") != "ir.ui.view":
            continue
        model_field = record.find("field[@name='model']")
        arch_field = record.find("field[@name='arch']")
        if model_field is None or arch_field is None or not (model_field.text or "").strip():
            continue
        model = (model_field.text or "").strip()
        arch_children = list(arch_field)
        if not arch_children:
            continue
        arch_root = arch_children[0]
        if model in EXPECTED_OWNER_MODELS:
            if arch_root.tag == "search":
                ui_matrix[model].add("search")
            elif arch_root.tag == "list":
                ui_matrix[model].add("list")
            elif arch_root.tag == "form":
                ui_matrix[model].add("form")

        # Context-aware fields/buttons for custom owner-model views.
        if model not in EXPECTED_OWNER_MODELS:
            continue

        def walk(node, current_model: str):
            nonlocal_dummy = None
            global object_buttons
            if node.tag == "field":
                fname = node.get("name")
                if fname and fname not in model_fields.get(current_model, set()):
                    # inherited mail fields are valid on mail-thread owners
                    if fname not in {"message_follower_ids", "activity_ids", "message_ids", "create_date", "write_date"}:
                        field_mismatches.append(f"{path.name}: {current_model}.{fname}")
                child_model = relation_map.get((current_model, fname or ""), current_model)
                for child in list(node):
                    if child.tag in {"list", "form"}:
                        walk(child, child_model)
                    else:
                        walk(child, current_model)
                return
            if node.tag == "button" and node.get("type") == "object":
                object_buttons += 1
                method = node.get("name") or ""
                if method not in model_methods.get(current_model, set()):
                    button_mismatches.append(f"{path.name}: {current_model}.{method}")
            for child in list(node):
                walk(child, current_model)

        walk(arch_root, model)

for model in sorted(EXPECTED_OWNER_MODELS):
    missing = {"search", "list", "form"} - ui_matrix.get(model, set())
    if missing:
        fail(f"UI matrix incomplete for {model}: missing {sorted(missing)}")
if field_mismatches:
    for mismatch in sorted(set(field_mismatches)):
        fail(f"view references unknown custom-model field: {mismatch}")
if button_mismatches:
    for mismatch in sorted(set(button_mismatches)):
        fail(f"context-aware object button method missing: {mismatch}")

# ---------------------------------------------------------------------------
# Security / ACL
# ---------------------------------------------------------------------------
security_path = ROOT / "security" / "clinic_ap_security.xml"
security_text = security_path.read_text(encoding="utf-8")
if re.search(r'<record[^>]+model="res\.groups"[\s\S]*?<field\s+name="category_id"', security_text):
    fail("Odoo 19 res.groups.category_id contract detected; use res.groups.privilege/privilege_id")
security_root = ET.parse(security_path).getroot()
for rec in security_root.findall(".//record[@model='res.groups']"):
    if rec.find("field[@name='privilege_id']") is None:
        fail(f"res.groups record missing privilege_id: {rec.get('id')}")

acl_path = ROOT / "security" / "ir.model.access.csv"
acl_text = acl_path.read_text(encoding="utf-8-sig")
rows = list(csv.DictReader(io.StringIO(acl_text)))
if len(rows) < len(EXPECTED_OWNER_MODELS) * 2:
    fail(f"ACL rows too low: {len(rows)}; expected at least {len(EXPECTED_OWNER_MODELS) * 2}")
for model in EXPECTED_OWNER_MODELS:
    model_xmlid = "model_" + model.replace(".", "_")
    if not any(row.get("model_id:id") == model_xmlid for row in rows):
        fail(f"ACL missing for persistent model {model}")

# ---------------------------------------------------------------------------
# Guardrail document numbering
# ---------------------------------------------------------------------------
guardrail_text = (ROOT / "docs" / "ENTERPRISE_DEVELOPMENT_GUARDRAIL.md").read_text(encoding="utf-8")
found = [int(x) for x in re.findall(r"HARD GATE\s+(\d+)", guardrail_text)]
# Deduplicate while preserving order.
found_unique = list(dict.fromkeys(found))
if found_unique != HARD_GATES:
    fail(f"Hard Gate numbering mismatch: expected {HARD_GATES}, got {found_unique}")
if "HARD GATE 11" in guardrail_text:
    fail("Hard Gate 11 must not be invented")


# ---------------------------------------------------------------------------
# Odoo 19 global Settings ownership / routing safety
# ---------------------------------------------------------------------------
ap_settings_path = ROOT / "views" / "res_config_settings_views.xml"
ap_settings_root = ET.parse(ap_settings_path).getroot()

settings_view = ap_settings_root.find(
    ".//record[@id='view_clinic_ap_settings_form'][@model='ir.ui.view']"
)
if settings_view is None:
    fail("AP settings view record is missing")
else:
    model_node = settings_view.find("field[@name='model']")
    inherit_node = settings_view.find("field[@name='inherit_id']")
    mode_node = settings_view.find("field[@name='mode']")
    arch_node = settings_view.find("field[@name='arch']")

    if model_node is None or (model_node.text or "").strip() != "res.config.settings":
        fail("AP settings view must target res.config.settings")
    if inherit_node is None or inherit_node.get("ref") != "base.res_config_settings_view_form":
        fail("AP settings view must inherit base.res_config_settings_view_form")
    if mode_node is None or (mode_node.text or "").strip() != "extension":
        fail("AP settings view must be extension mode, never a standalone primary form")
    if arch_node is None or arch_node.find(".//app[@name='clinic_ap']") is None:
        fail("AP settings extension must provide the clinic_ap Odoo 19 settings app")

settings_action = ap_settings_root.find(
    ".//record[@id='action_clinic_ap_settings'][@model='ir.actions.act_window']"
)
if settings_action is None:
    fail("AP settings action is missing")
else:
    view_id_node = settings_action.find("field[@name='view_id']")
    path_node = settings_action.find("field[@name='path']")
    context_node = settings_action.find("field[@name='context']")
    if view_id_node is None or view_id_node.get("eval") != "False":
        fail("AP settings action must explicitly clear the historical pinned view_id")
    if path_node is None or (path_node.text or "").strip() != "clinic-ap-settings":
        fail("AP settings action must use unique Odoo 19 path clinic-ap-settings")
    if context_node is None or "clinic_ap" not in (context_node.text or ""):
        fail("AP settings action must focus the clinic_ap settings app")

menu_source = (ROOT / "views" / "menu_views.xml").read_text(encoding="utf-8")
if 'id="menu_clinic_ap_settings" name="AP Settings"' not in menu_source:
    fail("AP configuration menu must use explicit label 'AP Settings'")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
info(f"python_files={len(python_files)}")
info(f"xml_files={len(xml_files)}")
info(f"persistent_models={len(owner_models)}/{len(EXPECTED_OWNER_MODELS)}")
info(f"models.Constraint={constraint_count}")
info(f"sql_objects={sql_object_count}")
info(f"object_buttons={object_buttons}")
info(f"ui_matrix={sum(1 for m in EXPECTED_OWNER_MODELS if ui_matrix.get(m) == {'search','list','form'})}/{len(EXPECTED_OWNER_MODELS)}")
info(f"acl_rows={len(rows)}")
# Count test methods without importing Odoo.
test_count = 0
for path in (ROOT / "tests").glob("test_*.py"):
    try:
        test_tree = ast.parse(path.read_text(encoding="utf-8"))
        test_count += sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.walk(test_tree))
    except SyntaxError:
        pass
info(f"test_methods={test_count}")
info(f"legacy__sql_constraints={legacy_sql_constraints}")
info("direct_res_currency_check_company_true=0" if not any("direct res.currency" in e for e in errors) else "direct_res_currency_check_company_true=FAIL")

print("clinic_ap Enterprise Development Guardrail")
for item in infos:
    print(f"[INFO] {item}")
if errors:
    for item in errors:
        print(f"[FAIL] {item}")
    print("RESULT: FAIL (SOURCE/STATIC ONLY)")
    sys.exit(1)
print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)")
