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
errors = []
passes = []


def fail(gate, message):
    errors.append(f"[FAIL] HARD GATE {gate} - {message}")


def ok(gate, message):
    passes.append(f"[PASS] HARD GATE {gate} - {message}")


manifest = ast.literal_eval(
    ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value
)


# ---------------------------------------------------------------------------
# HARD GATE 0 — Project identity
# ---------------------------------------------------------------------------
if manifest.get("version") != "19.0.2.0.2":
    fail(0, "version must be 19.0.2.0.2")

required_dependencies = {
    "clinic_base",
    "clinic_audit",
    "clinic_branch",
    "clinic_patient",
    "clinic_doctor",
    "clinic_inventory",
    "clinic_booking",
    "clinic_encounter",
    "clinic_package",
    "clinic_referral",
    "clinic_billing",
}
missing_dependencies = sorted(
    required_dependencies - set(manifest.get("depends", []))
)
if missing_dependencies:
    fail(
        0,
        f"required upstream dependencies missing: {missing_dependencies}",
    )

forbidden_downstream = {
    "clinic_membership",
    "clinic_ar",
    "clinic_wallet",
    "clinic_finance",
    "clinic_accounting",
    "clinic_reports",
    "clinic_dashboard",
    "clinic_analytics",
}
bad_dependencies = sorted(
    forbidden_downstream.intersection(manifest.get("depends", []))
)
if bad_dependencies:
    fail(
        0,
        f"downstream dependency would reverse ownership: {bad_dependencies}",
    )

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(
        0,
        "ClinicOne / Odoo 19 CE / source-actual addon #41 identity locked",
    )


# ---------------------------------------------------------------------------
# HARD GATE 1 / 14 — Codex bounded worker
# ---------------------------------------------------------------------------
agents = (ROOT / "AGENTS.md").read_text().lower()
for phrase in (
    "bounded implementation worker",
    "not:\n- the architect",
    "simplifier",
    "endless retry",
    "maximum bounded implementation repair attempts",
):
    if phrase not in agents:
        fail(1, f"Codex governance phrase missing: {phrase}")

repair_log = (ROOT / "docs/REPAIR_LOG.md").read_text()
if "Maximum source-build repair attempts: **3**" not in repair_log:
    fail(14, "bounded source-build repair ceiling must be 3")

if not any(item.startswith("[FAIL] HARD GATE 1") for item in errors):
    ok(1, "Codex is a bounded implementer, not architect/simplifier")
if not any(item.startswith("[FAIL] HARD GATE 14") for item in errors):
    ok(14, "source-build repair ceiling is 3")


# ---------------------------------------------------------------------------
# Parse Python model inventory
# ---------------------------------------------------------------------------
python_files = [
    path
    for path in ROOT.rglob("*.py")
    if "__pycache__" not in path.parts
]
xml_files = list(ROOT.rglob("*.xml"))

fields_by_model = defaultdict(set)
methods_by_model = defaultdict(set)
constraint_count = 0
comment_count = 0
docstring_count = 0

for path in python_files:
    text = path.read_text()
    comment_count += sum(
        1
        for line in text.splitlines()
        if line.strip().startswith("#")
    )

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        fail(
            12,
            f"Python syntax error {path.relative_to(ROOT)}: {exc}",
        )
        continue

    for cls in (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    ):
        if ast.get_docstring(cls):
            docstring_count += 1

        model_names = []

        for statement in cls.body:
            if not isinstance(statement, ast.Assign):
                continue

            for target in statement.targets:
                if not isinstance(target, ast.Name):
                    continue

                if target.id in {"_name", "_inherit"}:
                    try:
                        value = ast.literal_eval(statement.value)
                    except Exception:
                        continue

                    if isinstance(value, str):
                        model_names.append(value)

        model_names = list(dict.fromkeys(model_names))

        for statement in cls.body:
            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                for model_name in model_names:
                    methods_by_model[model_name].add(statement.name)

            if not isinstance(statement, ast.Assign):
                continue

            for target in statement.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "_sql_constraints"
                ):
                    fail(
                        11,
                        f"legacy executable _sql_constraints in {path.relative_to(ROOT)}",
                    )

            if not (
                len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Attribute)
                and isinstance(statement.value.func.value, ast.Name)
            ):
                continue

            owner = statement.value.func.value.id
            attr = statement.value.func.attr

            if owner == "models" and attr == "Constraint":
                constraint_count += 1

            if owner == "fields":
                for model_name in model_names:
                    fields_by_model[model_name].add(
                        statement.targets[0].id
                    )


# ---------------------------------------------------------------------------
# HARD GATE 2 — Historical contract preservation
# ---------------------------------------------------------------------------
historical_fields = {
    "clinic.treatment.session": {
        "name",
        "display_name",
        "active",
        "company_id",
        "color",
        "patient_id",
        "patient_phone",
        "patient_email",
        "clinic_doctor_id",
        "doctor_user_id",
        "treatment_id",
        "booking_id",
        "booking_state",
        "room_id",
        "start_datetime",
        "end_datetime",
        "duration_planned",
        "duration_actual",
        "is_overtime",
        "state",
        "stage_id",
        "can_edit",
        "note_internal",
        "note_public",
        "chief_complaint",
        "objective_notes",
        "assessment",
        "plan",
        "contraindication_flag",
        "cancellation_reason",
        "no_show_reason",
        "line_ids",
        "move_id",
        "attachment_count",
        "activity_count",
    },
    "clinic.treatment.session.line": {
        "session_id",
        "company_id",
        "patient_id",
        "clinic_doctor_id",
        "treatment_id",
        "sequence",
        "display_name",
        "display_type",
        "usage_type",
        "name",
        "product_id",
        "product_type",
        "product_uom_id",
        "quantity",
        "consumed_qty",
        "is_billable",
        "currency_id",
        "price_unit",
        "discount",
        "tax_ids",
        "price_subtotal",
        "price_total",
        "consumption_state",
        "date_consumed",
        "is_stock_relevant",
        "stock_move_id",
        "location_id",
        "location_dest_id",
        "note_internal",
        "package_line_id",
        "referral_id",
    },
    "clinic.treatment.session.stage": {
        "name",
        "sequence",
        "active",
        "description",
        "color",
        "fold",
        "company_id",
        "technical_state",
        "is_default",
        "is_final",
        "legend_normal",
        "legend_done",
        "legend_blocked",
        "session_ids",
        "sessions_count",
    },
}

historical_methods = {
    "clinic.treatment.session": {
        "_compute_display_name",
        "_compute_duration_actual",
        "_compute_is_overtime",
        "_compute_can_edit",
        "_compute_attachment_count",
        "_compute_activity_count",
        "_check_dates",
        "_check_company_consistency",
        "create",
        "write",
        "unlink",
        "_subscribe_related_partners",
        "action_confirm",
        "action_start",
        "action_done",
        "action_no_show",
        "action_cancel",
        "_sync_stage_with_state",
        "_post_done_hook",
        "action_prepare_billing",
        "action_create_invoice",
        "action_link_payment",
        "cron_send_session_reminders",
        "_send_session_reminder",
        "action_view_attachments",
        "action_view_activities",
        "action_view_patient",
        "action_view_invoice",
        "reschedule",
    },
    "clinic.treatment.session.line": {
        "_compute_display_name",
        "_compute_is_stock_relevant",
        "_compute_amounts",
        "_check_product_required",
        "_check_consumed_not_exceed_quantity",
        "_onchange_product_id",
        "_onchange_usage_type_display_type",
        "_get_default_consumption_locations",
        "action_mark_ready",
        "action_mark_consumed",
        "action_reset_consumption",
        "prepare_billing_payload_line",
    },
    "clinic.treatment.session.stage": {
        "_compute_sessions_count",
        "create",
        "write",
        "unlink",
        "_ensure_single_default_per_state",
        "get_default_stage",
        "action_view_sessions",
        "name_get",
        "_check_final_flag",
    },
}

for model_name, expected in historical_fields.items():
    missing = sorted(expected - fields_by_model.get(model_name, set()))
    if missing:
        fail(
            2,
            f"{model_name} historical fields lost: {missing}",
        )

for model_name, expected in historical_methods.items():
    missing = sorted(expected - methods_by_model.get(model_name, set()))
    if missing:
        fail(
            2,
            f"{model_name} historical methods lost: {missing}",
        )

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(
        2,
        "historical Session/Line/Stage fields and public methods preserved",
    )


# ---------------------------------------------------------------------------
# HARD GATE 3 — Enterprise completeness beyond tests
# ---------------------------------------------------------------------------
required_files = {
    "security/clinic_treatment_session_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/session_stage_data.xml",
    "data/mail_template_data.xml",
    "data/cron_data.xml",
    "data/optional_ui_bridge.xml",
    "views/treatment_session_views.xml",
    "views/treatment_session_line_views.xml",
    "views/session_stage_views.xml",
    "views/res_config_settings_views.xml",
    "views/treatment_session_menus.xml",
    "models/enterprise_session.py",
    "models/enterprise_line.py",
    "models/enterprise_booking.py",
    "models/enterprise_billing.py",
    "models/enterprise_navigation.py",
    "models/canonical_bridges.py",
    "models/referral_bridge.py",
    "models/ui_bridge.py",
    "migrations/19.0.2.0.0/pre-migrate.py",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/UI_UX_MATRIX.md",
    "docs/SECURITY_MODEL.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "tests/test_source_contracts.py",
}
missing_files = sorted(
    rel for rel in required_files
    if not (ROOT / rel).exists()
)
if missing_files:
    fail(3, f"enterprise release files missing: {missing_files}")
else:
    ok(
        3,
        "workflow, security, stock, billing, integration, UI, migration, docs and tests present",
    )


# ---------------------------------------------------------------------------
# HARD GATE 4 — Structural inventory
# ---------------------------------------------------------------------------
owned = {
    "clinic.treatment.session",
    "clinic.treatment.session.line",
    "clinic.treatment.session.stage",
}
missing_owned = sorted(owned - set(fields_by_model))
if missing_owned:
    fail(4, f"owned models missing: {missing_owned}")
else:
    ok(4, "three owned persistent models inventoried")


# ---------------------------------------------------------------------------
# HARD GATE 5 / 12 / 13 — Human-friendly source
# ---------------------------------------------------------------------------
large_model_files = []
for path in (ROOT / "models").rglob("*.py"):
    if path.name[:1].isdigit():
        continue
    lines = len(path.read_text().splitlines())
    if lines > 900:
        large_model_files.append(
            f"{path.relative_to(ROOT)}={lines}"
        )

if large_model_files:
    fail(
        5,
        f"God-class threshold >900 lines: {large_model_files}",
    )
else:
    ok(
        5,
        "model files split by responsibility; no >900-line model file",
    )

if docstring_count < 18:
    fail(
        12,
        f"documentation floor too low: {docstring_count} class docstrings",
    )
else:
    ok(
        12,
        f"human-readable responsibility docs present: {docstring_count}",
    )

if comment_count < 100:
    fail(
        13,
        f"useful comment floor too low: {comment_count}",
    )
else:
    ok(
        13,
        f"useful source comments present: {comment_count}",
    )


# ---------------------------------------------------------------------------
# XML parse and view inventory
# ---------------------------------------------------------------------------
view_types = {
    model_name: set()
    for model_name in owned
}
button_bindings = defaultdict(set)

for path in xml_files:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        fail(
            6,
            f"XML parse error {path.relative_to(ROOT)}: {exc}",
        )
        continue

    for xpath in root.iter("xpath"):
        expr = xpath.attrib.get("expr", "")
        if "@string" in expr:
            fail(
                6,
                f"Odoo 19 inherited view selects by translatable string: {path.relative_to(ROOT)} {expr}",
            )

    for record in root.findall("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue

        model_node = record.find("./field[@name='model']")
        arch_node = record.find("./field[@name='arch']")
        if (
            model_node is None
            or arch_node is None
            or not list(arch_node)
        ):
            continue

        model_name = (model_node.text or "").strip()
        arch = list(arch_node)[0]

        if (
            model_name in view_types
            and arch.tag
            in {
                "search",
                "list",
                "form",
                "kanban",
                "calendar",
                "graph",
                "pivot",
            }
        ):
            view_types[model_name].add(arch.tag)

        if model_name in owned:
            for button in arch.iter("button"):
                if button.attrib.get("type") == "object":
                    button_bindings[model_name].add(
                        button.attrib.get("name")
                    )

# Inline Session Line buttons reside inside Session form.
for inline_name in {
    "action_mark_ready",
    "action_mark_consumed",
    "action_open_stock_move",
}:
    button_bindings["clinic.treatment.session"].discard(inline_name)
    button_bindings["clinic.treatment.session.line"].add(inline_name)


# ---------------------------------------------------------------------------
# HARD GATE 8 — computed fields used in Search domains must be searchable
# ---------------------------------------------------------------------------
search_field_meta = {}

for path in (ROOT / "models").rglob("*.py"):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue

    for cls in (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    ):
        model_names = []

        for statement in cls.body:
            if not isinstance(statement, ast.Assign):
                continue

            for target in statement.targets:
                if not (
                    isinstance(target, ast.Name)
                    and target.id in {"_name", "_inherit"}
                ):
                    continue

                try:
                    value = ast.literal_eval(statement.value)
                except Exception:
                    continue

                if isinstance(value, str):
                    model_names.append(value)

        for statement in cls.body:
            if not (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Attribute)
                and isinstance(statement.value.func.value, ast.Name)
                and statement.value.func.value.id == "fields"
            ):
                continue

            kwargs = {
                keyword.arg: keyword.value
                for keyword in statement.value.keywords
                if keyword.arg
            }

            def _literal(name, default=None):
                node = kwargs.get(name)
                if node is None:
                    return default
                try:
                    return ast.literal_eval(node)
                except Exception:
                    return default

            for model_name in model_names:
                search_field_meta[
                    (
                        model_name,
                        statement.targets[0].id,
                    )
                ] = {
                    "compute": _literal("compute"),
                    "store": _literal("store", False),
                    "search": _literal("search"),
                }

searchability_offenders = []

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

        if (
            model_node is None
            or arch_node is None
            or not list(arch_node)
        ):
            continue

        model_name = (model_node.text or "").strip()
        arch = list(arch_node)[0]

        if arch.tag != "search":
            continue

        for filter_node in arch.iter("filter"):
            domain = filter_node.attrib.get("domain", "")

            for field_name in re.findall(
                r"\('([A-Za-z_][A-Za-z0-9_]*)'\s*,",
                domain,
            ):
                meta = search_field_meta.get(
                    (model_name, field_name)
                )

                if (
                    meta
                    and meta["compute"]
                    and not meta["store"]
                    and not meta["search"]
                ):
                    searchability_offenders.append(
                        f"{path.name}:{filter_node.attrib.get('name')}:"
                        f"{model_name}.{field_name}"
                    )

if searchability_offenders:
    fail(
        8,
        "unsearchable computed fields used in Search domains: "
        + ", ".join(searchability_offenders),
    )


# ---------------------------------------------------------------------------
# HARD GATE 6 / 7 / 8 / 9 — UI quality
# ---------------------------------------------------------------------------
for model_name in owned:
    if "form" not in view_types[model_name]:
        fail(6, f"{model_name} missing professional Form View")
    if not {"search", "list", "form"}.issubset(
        view_types[model_name]
    ):
        fail(
            7,
            f"{model_name} incomplete UI matrix: {sorted(view_types[model_name])}",
        )
    if "search" not in view_types[model_name]:
        fail(8, f"{model_name} missing Search View")
    if "list" not in view_types[model_name]:
        fail(9, f"{model_name} missing enterprise List View")

session_rich = {
    "kanban",
    "calendar",
    "graph",
    "pivot",
}
if not session_rich.issubset(
    view_types["clinic.treatment.session"]
):
    fail(
        7,
        "Treatment Session missing Kanban/Calendar/Graph/Pivot enterprise views",
    )

for model_name, buttons in button_bindings.items():
    missing_methods = sorted(
        button
        for button in buttons
        if button
        and button not in methods_by_model.get(model_name, set())
    )
    if missing_methods:
        fail(
            6,
            f"{model_name} object buttons without methods: {missing_methods}",
        )

if not any(item.startswith("[FAIL] HARD GATE 6") for item in errors):
    ok(
        6,
        "professional forms, status/actions and model-specific object buttons pass",
    )
if not any(item.startswith("[FAIL] HARD GATE 7") for item in errors):
    ok(
        7,
        "UI/UX matrix complete for all owned models plus rich Session views",
    )
if not any(item.startswith("[FAIL] HARD GATE 8") for item in errors):
    ok(8, "Search Views present for every owned persistent model")
if not any(item.startswith("[FAIL] HARD GATE 9") for item in errors):
    ok(9, "enterprise List Views present for every owned persistent model")


# ---------------------------------------------------------------------------
# HARD GATE 10 — Security
# ---------------------------------------------------------------------------
security_text = (
    ROOT / "security/clinic_treatment_session_security.xml"
).read_text()

for marker in (
    "group_treatment_session_user",
    "group_treatment_session_clinician",
    "group_treatment_session_manager",
    "user.allowed_branch_ids.ids",
    "company_ids",
):
    if marker not in security_text:
        fail(10, f"security marker missing: {marker}")

with (
    ROOT / "security/ir.model.access.csv"
).open(newline="", encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

expected_acl_models = {
    "model_clinic_treatment_session",
    "model_clinic_treatment_session_line",
    "model_clinic_treatment_session_stage",
}
actual_acl_models = {
    row["model_id:id"]
    for row in acl_rows
}
if not expected_acl_models.issubset(actual_acl_models):
    fail(
        10,
        f"ACL coverage missing: {sorted(expected_acl_models - actual_acl_models)}",
    )

enterprise_session = (
    ROOT / "models/enterprise_session.py"
).read_text()
enterprise_line = (
    ROOT / "models/enterprise_line.py"
).read_text()

for marker in (
    "def _require_manager(",
    "def _require_clinician(",
    "def _check_state_transition(",
):
    if marker not in enterprise_session:
        fail(10, f"backend workflow guard missing: {marker}")

if "def _require_clinician(" not in enterprise_line:
    fail(10, "line-level clinician backend guard missing")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(
        10,
        f"ACL={len(acl_rows)}, company/branch rules and Python workflow guards pass",
    )


# ---------------------------------------------------------------------------
# HARD GATE 11 — ORM / identifier safety
# ---------------------------------------------------------------------------
if constraint_count < 4:
    fail(
        11,
        f"expected at least 4 Odoo 19 models.Constraint declarations, found {constraint_count}",
    )

for path in ROOT.rglob("*"):
    if (
        path.is_file()
        and path.name[:1].isdigit()
    ):
        fail(
            11,
            f"digit-prefixed backup file packaged: {path.relative_to(ROOT)}",
        )

# High-signal technical identifiers declared by this addon.
identifier_candidates = []
for path in python_files:
    text = path.read_text()
    identifier_candidates.extend(
        re.findall(
            r'["\']([a-z][a-z0-9_]{1,})["\']',
            text,
        )
    )

for identifier in identifier_candidates:
    if (
        len(identifier) > 63
        and "_" in identifier
        and (
            identifier.startswith("clinic_")
            or identifier.startswith("model_")
        )
    ):
        fail(
            11,
            f"possible PostgreSQL/Odoo identifier >63 chars: {identifier}",
        )

# Odoo 19 create()/MRO runtime safety.
create_contract_offenders = []

for path in (ROOT / "models").rglob("*.py"):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != "create":
            continue

        decorators = []
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
            ):
                decorators.append(
                    f"{decorator.value.id}.{decorator.attr}"
                )

        argument_name = (
            node.args.args[-1].arg
            if node.args.args
            else ""
        )
        direct_dict_calls = []

        for subnode in ast.walk(node):
            if not (
                isinstance(subnode, ast.Call)
                and isinstance(subnode.func, ast.Attribute)
                and isinstance(subnode.func.value, ast.Name)
                and subnode.func.value.id == argument_name
                and subnode.func.attr
                in {
                    "get",
                    "setdefault",
                    "update",
                    "pop",
                    "items",
                    "keys",
                    "values",
                }
            ):
                continue
            direct_dict_calls.append(subnode.func.attr)

        if (
            direct_dict_calls
            and "api.model_create_multi" not in decorators
        ):
            create_contract_offenders.append(
                f"{path.relative_to(ROOT)}:{node.lineno}"
            )

if create_contract_offenders:
    fail(
        11,
        "Odoo 19 create() dict/list contract offenders: "
        + ", ".join(create_contract_offenders),
    )

legacy_behavior_source = (
    ROOT / "models/treatment_session_legacy_methods.py"
).read_text()
if "super(ClinicTreatmentSession, self)" in legacy_behavior_source:
    fail(
        11,
        "split historical Session behavior has stale class-qualified super()",
    )


# Odoo 19 menu field hygiene.
for path in (ROOT / "views").glob("*.xml"):
    root = ET.parse(path).getroot()
    for record in root.findall(".//record[@model='ir.ui.menu']"):
        for field in record.findall("field"):
            if field.attrib.get("name") == "groups_id":
                fail(
                    11,
                    f"Odoo 19 ir.ui.menu may not use invalid groups_id: {path.name}",
                )

if not any(item.startswith("[FAIL] HARD GATE 11") for item in errors):
    ok(
        11,
        f"models.Constraint={constraint_count}; identifier/menu/backup hygiene passes",
    )


# ---------------------------------------------------------------------------
# Settings and optional UI safety
# ---------------------------------------------------------------------------
settings_root = ET.parse(
    ROOT / "views/res_config_settings_views.xml"
).getroot()
settings_view = settings_root.find(
    ".//record[@id='res_config_settings_view_form_treatment_session']"
)
if settings_view is None:
    fail(10, "Treatment Session Settings extension view missing")
else:
    inherit = settings_view.find("field[@name='inherit_id']")
    if (
        inherit is None
        or inherit.attrib.get("ref")
        != "base.res_config_settings_view_form"
    ):
        fail(
            10,
            "Treatment Session Settings must extend base Settings",
        )

ui_bridge = (ROOT / "models/ui_bridge.py").read_text()
for marker in (
    "raise_if_not_found=False",
    "_get_combined_arch()",
    "with self.env.cr.savepoint():",
):
    if marker not in ui_bridge:
        fail(
            6,
            f"runtime-safe optional UI bridge pattern missing: {marker}",
        )

# No hard foreign inherited-view references except Odoo base Settings.
for path in (ROOT / "views").glob("*.xml"):
    root = ET.parse(path).getroot()
    for record in root.findall("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue
        inherit = record.find("field[@name='inherit_id']")
        if inherit is None:
            continue
        ref = inherit.attrib.get("ref")
        if ref and ref != "base.res_config_settings_view_form":
            fail(
                6,
                f"load-time foreign inherited-view XML-ID not allowed: {ref}",
            )


# ---------------------------------------------------------------------------
# HARD GATE 15 — Evidence matrix
# ---------------------------------------------------------------------------
matrix = (
    ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md"
).read_text()

for phrase in (
    "Historical model/method preservation",
    "Booking → Session generation",
    "State-machine workflow",
    "Stock move completion verification",
    "Clinic Billing bridge",
    "Multi-company / branch security",
    "Runtime-safe smart-button bridges",
    "Odoo 19 models.Constraint",
    "Upgrade migration",
):
    if phrase not in matrix:
        fail(
            15,
            f"completeness evidence missing: {phrase}",
        )

if not any(item.startswith("[FAIL] HARD GATE 15") for item in errors):
    ok(
        15,
        "enterprise completeness matrix covers workflow, stock, billing, security and integration",
    )


if errors:
    print("CLINIC_TREATMENT_SESSION_GUARDRAIL: FAIL")
    for item in passes:
        print(item)
    for item in errors:
        print(item)
    sys.exit(1)

print("CLINIC_TREATMENT_SESSION_GUARDRAIL: PASS")
for item in passes:
    print(item)

print(f"Python files: {len(python_files)}")
print(f"XML files: {len(xml_files)}")
print(f"ACL rows: {len(acl_rows)}")
print(f"models.Constraint: {constraint_count}")
print("HARD GATE 0-15: PASS (source/static)")
