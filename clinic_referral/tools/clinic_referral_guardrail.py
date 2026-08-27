#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import ast
import csv
import re
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []
PASSES = []


def fail(gate, message):
    ERRORS.append(f"[FAIL] HARD GATE {gate} - {message}")


def ok(gate, message):
    PASSES.append(f"[PASS] HARD GATE {gate} - {message}")


def literal(node, default=None):
    if node is None:
        return default
    try:
        return ast.literal_eval(node)
    except Exception:
        return default


manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())

# ---------------------------------------------------------------------------
# HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
# ---------------------------------------------------------------------------
if manifest.get("version") != "19.0.2.0.5":
    fail(0, "version must be 19.0.2.0.5")

required_deps = {
    "clinic_base",
    "clinic_audit",
    "clinic_branch",
    "clinic_patient",
    "clinic_doctor",
    "clinic_booking",
    "clinic_package",
}
missing_deps = sorted(required_deps - set(manifest.get("depends", [])))
if missing_deps:
    fail(0, f"required dependencies missing: {missing_deps}")

forbidden_downstream = {
    "clinic_treatment_session",
    "clinic_membership",
    "clinic_analytics",
}
wrong_deps = sorted(forbidden_downstream.intersection(manifest.get("depends", [])))
if wrong_deps:
    fail(0, f"downstream dependency can create a cycle: {wrong_deps}")

if not (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").exists():
    fail(0, "Project Identity document missing")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in ERRORS):
    ok(0, "ClinicOne addon #40 / Odoo 19 CE / authoritative baseline locked")


# ---------------------------------------------------------------------------
# HARD GATE 1 + 14 — CODEX BOUNDARY / RETRY LIMIT
# ---------------------------------------------------------------------------
agents = (ROOT / "AGENTS.md").read_text().lower()
for term in (
    "bounded implementation worker",
    "architect",
    "simplifier",
    "endless retry engine",
    "maximum bounded implementation repair attempts",
):
    if term not in agents:
        fail(1, f"Codex boundary term missing: {term}")

repair_log = (ROOT / "docs/REPAIR_LOG.md").read_text().lower()
if "maximum bounded implementation repair attempts: **3**" not in repair_log:
    fail(14, "bounded repair ceiling must be exactly 3")

if not any(item.startswith("[FAIL] HARD GATE 1") for item in ERRORS):
    ok(1, "Codex is bounded implementer, not architect/simplifier")
if not any(item.startswith("[FAIL] HARD GATE 14") for item in ERRORS):
    ok(14, "bounded implementation repair ceiling is 3")


# ---------------------------------------------------------------------------
# Python / ORM inventory
# ---------------------------------------------------------------------------
python_files = [
    path for path in ROOT.rglob("*.py")
    if "__pycache__" not in path.parts
]
xml_files = list(ROOT.rglob("*.xml"))

model_fields = defaultdict(set)
model_methods = defaultdict(set)
field_comodel = {}
computed_contracts = {}
constraint_count = 0
comment_count = 0
docstring_count = 0

for path in python_files:
    source = path.read_text()
    comment_count += sum(
        1 for line in source.splitlines()
        if line.strip().startswith("#")
    )
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        fail(12, f"Python syntax {path.relative_to(ROOT)}: {exc}")
        continue

    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if ast.get_docstring(cls):
            docstring_count += 1

        model_name = None
        inherit_name = None
        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "_name":
                    model_name = literal(stmt.value)
                elif isinstance(target, ast.Name) and target.id == "_inherit":
                    value = literal(stmt.value)
                    if isinstance(value, str):
                        inherit_name = value

        technical_model = model_name or inherit_name
        if not technical_model:
            continue

        for stmt in cls.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                model_methods[technical_model].add(stmt.name)
                if ast.get_docstring(stmt):
                    docstring_count += 1
                continue

            if not isinstance(stmt, ast.Assign):
                continue

            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "_sql_constraints":
                    fail(11, f"legacy _sql_constraints in {path.relative_to(ROOT)}")

            if not (
                len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and isinstance(stmt.value.func.value, ast.Name)
            ):
                continue

            owner = stmt.value.func.value.id
            attr = stmt.value.func.attr
            if owner == "models" and attr == "Constraint":
                constraint_count += 1
                continue

            if owner != "fields":
                continue

            field_name = stmt.targets[0].id
            model_fields[technical_model].add(field_name)
            if attr in {"Many2one", "One2many", "Many2many"} and stmt.value.args:
                comodel = literal(stmt.value.args[0])
                if isinstance(comodel, str):
                    field_comodel[(technical_model, field_name)] = comodel

            kwargs = {kw.arg: kw.value for kw in stmt.value.keywords if kw.arg}
            if "compute" in kwargs:
                computed_contracts[(technical_model, field_name)] = {
                    "compute": literal(kwargs.get("compute")),
                    "store": literal(kwargs.get("store"), False),
                    "search": literal(kwargs.get("search")),
                }


# ---------------------------------------------------------------------------
# HARD GATE 2 — EXISTING FUNCTION PRESERVATION
# ---------------------------------------------------------------------------
legacy_fields = {
    "clinic.referral": {
        "name", "active", "state", "company_id", "user_id", "patient_id",
        "target_doctor_id", "clinical_reason", "clinical_notes",
        "referrer_type", "internal_referrer_doctor_id",
        "external_referrer_partner_id", "referrer_patient_id",
        "referrer_free_text", "program_id", "source_id", "date_referral",
        "date_received", "valid_until", "date_converted", "date_cancelled",
        "is_expired", "reward_policy", "currency_id", "reward_value",
        "reward_percent", "reward_state", "reward_notes", "origin_model_id",
        "origin_res_id", "origin_display_name", "booking_count",
        "treatment_session_count", "notes",
    },
    "clinic.referral.program": {
        "name", "code", "active", "description", "color", "company_id",
        "user_id", "state", "start_date", "end_date", "is_current",
        "is_future", "is_past", "patient_scope", "min_patient_age",
        "max_patient_age", "allowed_company_ids", "reward_policy",
        "currency_id", "reward_value", "reward_percent", "reward_points",
        "max_reward_per_referral", "max_reward_per_referrer",
        "min_qualifying_amount", "auto_convert_on_first_sale",
        "require_manual_approval", "apply_on_booking", "apply_on_treatment",
        "apply_on_invoice", "apply_on_wallet", "apply_on_membership",
        "apply_on_other", "integration_notes", "referral_ids",
        "referral_count", "referral_converted_count",
        "referral_conversion_rate", "total_reward_value",
    },
    "clinic.referral.source": {
        "name", "code", "active", "description", "sequence", "color",
        "company_id", "category", "referrer_type", "internal_doctor_id",
        "partner_id", "contact_name", "phone", "email", "address",
        "channel_tags", "campaign_name", "tracking_code", "landing_page_url",
        "apply_on_booking", "apply_on_treatment", "apply_on_invoice",
        "apply_on_wallet", "apply_on_membership", "apply_on_marketing",
        "apply_on_other", "integration_notes", "default_program_id",
        "default_reward_policy", "currency_id", "default_reward_value",
        "default_reward_percent", "referral_ids", "referral_count",
        "referral_converted_count", "referral_conversion_rate",
        "patient_count", "booking_count", "treatment_session_count",
    },
}

legacy_methods = {
    "clinic.referral": {
        "_compute_is_expired", "_compute_origin_display_name",
        "_compute_related_counts", "_check_valid_until",
        "_check_reward_percent", "create", "write",
        "_check_state_transition", "action_set_draft", "action_confirm",
        "action_convert", "action_cancel", "action_mark_expired", "name_get",
    },
    "clinic.referral.program": {
        "_compute_period_flags", "_compute_referral_stats",
        "_check_date_range", "_check_reward_percent",
        "_check_patient_age_range", "create", "write",
        "_check_state_transition", "action_set_draft", "action_start",
        "action_pause", "action_close", "action_archive",
        "is_applicable", "get_reward_config", "name_get",
    },
    "clinic.referral.source": {
        "_compute_stats", "_compute_external_counts",
        "_check_default_reward_percent", "create", "write",
        "get_effective_reward_config", "name_get",
    },
}

for model, expected in legacy_fields.items():
    missing = sorted(expected - model_fields.get(model, set()))
    if missing:
        fail(2, f"{model} historical fields lost: {missing}")

for model, expected in legacy_methods.items():
    missing = sorted(expected - model_methods.get(model, set()))
    if missing:
        fail(2, f"{model} historical methods lost: {missing}")

# Preserve both the historical public name_get API and Odoo 19 display-name
# computation so downstream compatibility is not silently lost.
for model in legacy_fields:
    if "_compute_display_name" not in model_methods.get(model, set()):
        fail(2, f"{model} does not preserve legacy display-name behavior")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in ERRORS):
    ok(2, "historical Referral/Program/Source fields, methods and display behavior preserved")


# ---------------------------------------------------------------------------
# HARD GATE 3 / 4 — COMPLETENESS + STRUCTURAL INVENTORY
# ---------------------------------------------------------------------------
required_files = {
    "security/clinic_referral_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/referral_views.xml",
    "views/referral_program_views.xml",
    "views/referral_source_views.xml",
    "views/referral_integration_views.xml",
    "views/res_config_settings_views.xml",
    "views/referral_menus.xml",
    "data/optional_ui_bridge.xml",
    "models/ui_bridge.py",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/AUTHORITATIVE_SOURCE_AUDIT_20260826.md",
    "docs/UI_UX_MATRIX.md",
    "docs/SECURITY_MODEL.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "tests/test_source_contracts.py",
}
missing_files = sorted(item for item in required_files if not (ROOT / item).exists())
if missing_files:
    fail(3, f"enterprise files missing: {missing_files}")
else:
    ok(3, "workflow, security, sequences, cron, integration, UI, docs and tests present")

owned_models = {
    "clinic.referral",
    "clinic.referral.program",
    "clinic.referral.source",
}
if owned_models - set(model_fields):
    fail(4, f"owned models missing from source inventory: {sorted(owned_models - set(model_fields))}")
else:
    ok(4, "full owned-model structural inventory complete")


# ---------------------------------------------------------------------------
# HARD GATE 5 / 12 / 13 — HUMAN-FRIENDLY CODE
# ---------------------------------------------------------------------------
large_files = [
    path.relative_to(ROOT)
    for path in (ROOT / "models").glob("*.py")
    if len(path.read_text().splitlines()) > 950
]
if large_files:
    fail(5, f"God-class threshold exceeded: {large_files}")
else:
    ok(5, "models split by responsibility; no >950-line model file")

if docstring_count < 10:
    fail(12, f"documentation floor too low: {docstring_count}")
else:
    ok(12, f"human-friendly documented code: {docstring_count} docstrings")

if comment_count < 35:
    fail(13, f"useful comment floor too low: {comment_count}")
else:
    ok(13, f"useful comments present: {comment_count}")


# ---------------------------------------------------------------------------
# XML parse + HARD GATE 6/7/8/9
# ---------------------------------------------------------------------------
for path in xml_files:
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        fail(6, f"XML parse {path.relative_to(ROOT)}: {exc}")

view_types = {model: set() for model in owned_models}
view_records = []

for path in (ROOT / "views").glob("*.xml"):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        continue
    for record in root.findall("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue
        model_node = record.find("./field[@name='model']")
        arch_node = record.find("./field[@name='arch']")
        if model_node is None or arch_node is None or not list(arch_node):
            continue
        model = (model_node.text or "").strip()
        arch = list(arch_node)[0]
        view_records.append((path.name, model, arch))
        if model in view_types and arch.tag in {"search", "list", "form"}:
            view_types[model].add(arch.tag)

for model, types in view_types.items():
    if "form" not in types:
        fail(6, f"{model} missing Form")
    if {"search", "list", "form"} - types:
        fail(7, f"{model} UI matrix missing: {sorted({'search','list','form'} - types)}")
    if "search" not in types:
        fail(8, f"{model} missing Search")
    if "list" not in types:
        fail(9, f"{model} missing List")

# Model-specific object-button binding, including nested Referral history rows.
nested_model = {
    ("clinic.referral.program", "referral_ids"): "clinic.referral",
    ("clinic.referral.source", "referral_ids"): "clinic.referral",
}


def audit_buttons(node, current_model):
    for child in list(node):
        if child.tag == "button" and child.attrib.get("type") == "object":
            method = child.attrib.get("name")
            if method not in model_methods.get(current_model, set()):
                fail(6, f"object button {current_model}.{method} has no local model method")
        if child.tag == "field" and child.attrib.get("name"):
            field_name = child.attrib["name"]
            child_model = nested_model.get((current_model, field_name), current_model)
            for grandchild in list(child):
                audit_buttons(grandchild, child_model)
        else:
            audit_buttons(child, current_model)


for _file_name, model, arch in view_records:
    if model in model_methods:
        audit_buttons(arch, model)

# Dynamic nonstored computed fields used by Search must define search=.
for _file_name, model, arch in view_records:
    if arch.tag != "search":
        continue
    for filter_node in arch.iter("filter"):
        domain = filter_node.attrib.get("domain", "")
        for (contract_model, field_name), meta in computed_contracts.items():
            if (
                contract_model == model
                and field_name in domain
                and meta["compute"]
                and not meta["store"]
                and not meta["search"]
            ):
                fail(8, f"unsearchable computed field {model}.{field_name} used in Search domain")

if not any(item.startswith("[FAIL] HARD GATE 6") for item in ERRORS):
    ok(6, "professional forms and model-specific object-button bindings pass")
if not any(item.startswith("[FAIL] HARD GATE 7") for item in ERRORS):
    ok(7, "UI/UX matrix complete for all owned persistent models")
if not any(item.startswith("[FAIL] HARD GATE 8") for item in ERRORS):
    ok(8, "Search Views present and dynamic computed filters searchable")
if not any(item.startswith("[FAIL] HARD GATE 9") for item in ERRORS):
    ok(9, "enterprise List Views present with state decoration/actions")


# ---------------------------------------------------------------------------
# HARD GATE 10 — SECURITY > UI
# ---------------------------------------------------------------------------
security_text = (ROOT / "security/clinic_referral_security.xml").read_text()
for marker in (
    "res.groups.privilege",
    "group_referral_user",
    "group_referral_manager",
    "user.allowed_branch_ids.ids",
    "company_ids",
):
    if marker not in security_text:
        fail(10, f"security marker missing: {marker}")

with (ROOT / "security/ir.model.access.csv").open(newline="", encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))
acl_models = {row["model_id:id"] for row in acl_rows}
expected_acl = {
    "model_clinic_referral",
    "model_clinic_referral_program",
    "model_clinic_referral_source",
}
if not expected_acl.issubset(acl_models):
    fail(10, f"ACL coverage missing: {sorted(expected_acl - acl_models)}")

referral_source = (ROOT / "models/referral.py").read_text()
if "def _require_manager" not in referral_source or "def _ensure_user_scope" not in referral_source:
    fail(10, "Python manager/scope guards missing")

# ---------------------------------------------------------------------------
# HARD GATE 11 — bootstrap-safe res.company Referral settings
# ---------------------------------------------------------------------------
company_setting_fields = {
    "clinic_referral_default_valid_days",
    "clinic_referral_require_source",
    "clinic_referral_require_program_for_reward",
}

for field_name in sorted(company_setting_fields):
    meta = computed_contracts.get(("res.company", field_name))
    if not meta:
        fail(
            11,
            f"res.company.{field_name} must be a non-stored computed setting",
        )
        continue
    if meta.get("store"):
        fail(
            11,
            f"res.company.{field_name} must not require a PostgreSQL column",
        )

company_source = (ROOT / "models/res_company.py").read_text()
for inverse_name in (
    "_inverse_clinic_referral_default_valid_days",
    "_inverse_clinic_referral_require_source",
    "_inverse_clinic_referral_require_program_for_reward",
):
    if inverse_name not in company_source:
        fail(11, f"Referral company-setting inverse missing: {inverse_name}")

runtime_migration = (
    ROOT
    / "migrations"
    / "19.0.2.0.1"
    / "pre-migrate-company-settings.py"
)
if not runtime_migration.exists():
    fail(11, "19.0.2.0.1 bootstrap compatibility migration is missing")


# ---------------------------------------------------------------------------
# HARD GATE 6 — Odoo 19 inherited-view selector safety
# ---------------------------------------------------------------------------
unsafe_string_selectors = []

for xml_path in (ROOT / "views").glob("*.xml"):
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        continue

    for xpath in root.iter("xpath"):
        expr = xpath.attrib.get("expr", "")
        if "@string" in expr:
            unsafe_string_selectors.append(
                f"{xml_path.name}: {expr}"
            )

if unsafe_string_selectors:
    fail(
        6,
        "Odoo 19 inheritance may not select by string: "
        + "; ".join(unsafe_string_selectors),
    )

integration_source = (
    ROOT / "views/referral_integration_views.xml"
).read_text()
if "//form//field[@name='patient_id']" not in integration_source:
    fail(
        6,
        "Booking Referral integration must use the technical patient_id anchor",
    )


# ---------------------------------------------------------------------------
# HARD GATE 2 / 6 — optional runtime UI bridge resilience
# ---------------------------------------------------------------------------
integration_source = (
    ROOT / "views/referral_integration_views.xml"
).read_text()
ui_bridge_source = (
    ROOT / "models/ui_bridge.py"
).read_text()
menu_source = (
    ROOT / "views/referral_menus.xml"
).read_text()
optional_bridge_source = (
    ROOT / "data/optional_ui_bridge.xml"
).read_text()

# Patient/Branch presentation bridges must never be load-time inherited views.
for local_id in (
    "view_patient_form_referral",
    "view_branch_form_referral",
):
    if f'id="{local_id}"' in integration_source:
        fail(
            6,
            f"{local_id} must be installed by runtime UI bridge, not load-time XML",
        )
    if f'"{local_id}"' not in ui_bridge_source:
        fail(
            6,
            f"runtime UI bridge does not preserve local XML-ID {local_id}",
        )

for required_runtime_pattern in (
    "def _find_usable_form_parent(",
    "raise_if_not_found=False",
    '("mode", "=", "primary")',
    "def _parent_supports_button_box(",
    "def _upsert_optional_form_bridge(",
    "with self.env.cr.savepoint():",
    "def _ensure_optional_cross_addon_ui(",
):
    if required_runtime_pattern not in ui_bridge_source:
        fail(
            6,
            f"runtime UI bridge safety pattern missing: {required_runtime_pattern}",
        )

if "_ensure_optional_cross_addon_ui" not in optional_bridge_source:
    fail(
        6,
        "optional_ui_bridge.xml must invoke runtime cross-addon integration",
    )

# The local menu must remain independently valid before optional reparenting.
try:
    menu_root = ET.parse(
        ROOT / "views/referral_menus.xml"
    ).getroot()
    root_menu = menu_root.find(
        "./menuitem[@id='menu_referral_root']"
    )

    if root_menu is None:
        fail(
            6,
            "Referral root must use native Odoo menuitem syntax",
        )
    else:
        if root_menu.attrib.get("parent"):
            fail(
                6,
                "Referral root must be parentless before runtime reparenting",
            )
        if (
            root_menu.attrib.get("groups")
            != "clinic_referral.group_referral_user"
        ):
            fail(
                10,
                "Referral root menu must preserve Referral User visibility",
            )

    # Odoo 19 ir.ui.menu field is group_ids. Raw groups_id is invalid.
    for menu_record in menu_root.findall(
        "./record[@model='ir.ui.menu']"
    ):
        for field in menu_record.findall("field"):
            if field.attrib.get("name") == "groups_id":
                fail(
                    11,
                    "Odoo 19 ir.ui.menu may not use legacy/invalid groups_id",
                )
except ET.ParseError:
    pass

if "def _ensure_referral_menu_parent(" not in ui_bridge_source:
    fail(
        6,
        "runtime Referral menu reparenting method is missing",
    )

if 'parent="clinic_patient.menu_root"' in menu_source:
    fail(
        6,
        "Referral menu XML must not hard-require clinic_patient.menu_root",
    )


# User Settings routing safety.
settings_root = ET.parse(ROOT / "views/res_config_settings_views.xml").getroot()
settings_record = settings_root.find(
    ".//record[@id='res_config_settings_view_form_referral']"
)
inherit = settings_record.find("field[@name='inherit_id']") if settings_record is not None else None
mode = settings_record.find("field[@name='mode']") if settings_record is not None else None
if (
    settings_record is None
    or inherit is None
    or inherit.attrib.get("ref") != "base.res_config_settings_view_form"
    or mode is None
    or (mode.text or "").strip() != "extension"
):
    fail(10, "Referral Settings must be an extension of the global Odoo Settings form")

# Category/privilege labels must remain safe for Odoo dynamic User Rights XML.
try:
    sec_root = ET.parse(ROOT / "security/clinic_referral_security.xml").getroot()
    for record in sec_root.findall("record"):
        if record.attrib.get("model") not in {"ir.module.category", "res.groups.privilege"}:
            continue
        name_node = record.find("./field[@name='name']")
        label = (name_node.text or "") if name_node is not None else ""
        if "&" in label:
            fail(10, f"unsafe User Access Rights label: {label}")
except ET.ParseError:
    pass

if not any(item.startswith("[FAIL] HARD GATE 10") for item in ERRORS):
    ok(10, f"ACL={len(acl_rows)}, branch/company rules, Python guards and Settings routing pass")


# ---------------------------------------------------------------------------
# HARD GATE 11 — DB IDENTIFIER / ORM NAMING SAFETY
# ---------------------------------------------------------------------------
if constraint_count < 1:
    fail(11, "Odoo 19 models.Constraint conversion missing")

for path in ROOT.rglob("*"):
    if path.is_file() and path.name[:1].isdigit():
        fail(11, f"digit-prefixed backup artifact packaged: {path.relative_to(ROOT)}")

# Explicit relation-table identifiers and SQL-like identifiers should stay <=63.
for path in python_files:
    source = path.read_text()
    for candidate in re.findall(r'["\']([a-z][a-z0-9_]{63,})["\']', source):
        if "_" in candidate:
            fail(11, f"possible PostgreSQL identifier >63 chars: {candidate}")

if not any(item.startswith("[FAIL] HARD GATE 11") for item in ERRORS):
    ok(11, f"models.Constraint={constraint_count}; backup/identifier hygiene passes")


# ---------------------------------------------------------------------------
# HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
# ---------------------------------------------------------------------------
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text()
for term in (
    "Referral Source master",
    "Referral Program governance",
    "Booking attribution",
    "Patient 360 bridge",
    "CRM / UTM attribution",
    "Multi-company / branch security",
    "Odoo 19 `models.Constraint`",
):
    if term not in matrix:
        fail(15, f"completeness evidence missing: {term}")

if not any(item.startswith("[FAIL] HARD GATE 15") for item in ERRORS):
    ok(15, "enterprise completeness matrix covers master/workflow/security/integration/analytics")


if ERRORS:
    print("CLINIC_REFERRAL_GUARDRAIL: FAIL")
    for item in PASSES:
        print(item)
    for item in ERRORS:
        print(item)
    sys.exit(1)

print("CLINIC_REFERRAL_GUARDRAIL: PASS")
for item in PASSES:
    print(item)
print(f"Python files: {len(python_files)}")
print(f"XML files: {len(xml_files)}")
print(f"ACL rows: {len(acl_rows)}")
print(f"models.Constraint: {constraint_count}")
print("HARD GATE 0-15: PASS (source/static)")
