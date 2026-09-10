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


def manifest_dict():
    tree = ast.parse((ROOT / "__manifest__.py").read_text())
    return ast.literal_eval(tree.body[0].value)


manifest = manifest_dict()

# ----------------------------------------------------------------------
# HG0 / HG1 / HG2 / HG3 / HG14 / HG15 identity documents.
# ----------------------------------------------------------------------
if manifest.get("version") != "19.0.1.0.1":
    fail("HG0 unexpected addon version")
if "clinic_audit" not in manifest.get("depends", []):
    fail("HG2 final analytics layer must consume the completed Audit contract")
if "clinic_integration_api" not in manifest.get("depends", []):
    fail("HG2 Integration API bridge dependency is missing")
if "clinic_analytics" in manifest.get("depends", []):
    fail("HG0 addon cannot depend on itself")

for required in [
    "AGENTS.md",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/ARCHITECTURE_DECISION_RECORD.md",
    "docs/UPSTREAM_CONTRACT_AUDIT.md",
    "docs/UI_UX_MATRIX.md",
    "docs/SECURITY_MODEL.md",
    "docs/FORECAST_METHODS.md",
    "docs/REPAIR_LOG.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
]:
    if not (ROOT / required).exists():
        fail(f"Missing guardrail evidence: {required}")

# ----------------------------------------------------------------------
# Backup hygiene, Python syntax, Odoo 19 ORM naming.
# ----------------------------------------------------------------------
for path in ROOT.rglob("*"):
    if path.is_file() and path.name[:1].isdigit():
        fail(f"Digit-prefixed backup artifact packaged: {path.relative_to(ROOT)}")

constraint_count = 0
comment_count = 0
python_files = [
    p for p in ROOT.rglob("*.py")
    if "__pycache__" not in p.parts
]
for path in python_files:
    text = path.read_text()
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        fail(f"Python syntax: {path.relative_to(ROOT)}: {exc}")
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_sql_constraints":
                    fail(f"HG11 legacy _sql_constraints in {path.relative_to(ROOT)}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "models"
            and node.func.attr == "Constraint"
        ):
            constraint_count += 1

    comment_count += sum(
        1 for line in text.splitlines()
        if line.strip().startswith("#")
    )

if constraint_count < 8:
    fail(f"HG11 expected enterprise constraints; found only {constraint_count}")
if comment_count < 20:
    fail(f"HG13 useful-comment floor not met: {comment_count}")

# Identifier heuristic for explicit relation/index-like strings.
for path in python_files:
    text = path.read_text()
    for candidate in re.findall(r'["\']([a-z][a-z0-9_]{63,})["\']', text):
        if "_" in candidate:
            fail(f"HG11 possible PostgreSQL identifier >63 chars: {candidate}")

# ----------------------------------------------------------------------
# XML well-formedness.
# ----------------------------------------------------------------------
xml_files = list(ROOT.rglob("*.xml"))
for path in xml_files:
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        fail(f"XML parse: {path.relative_to(ROOT)}: {exc}")

# ----------------------------------------------------------------------
# Model inventory from source.
# ----------------------------------------------------------------------
model_fields = {}
model_methods = {}
field_relations = {}
computed_contracts = {}

for path in (ROOT / "models").glob("*.py"):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue

    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        model_names = []
        class_fields = {}
        class_methods = {
            stmt.name
            for stmt in cls.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign):
                continue

            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id in {"_name", "_inherit"}:
                    try:
                        value = ast.literal_eval(stmt.value)
                    except Exception:
                        value = None
                    if isinstance(value, str):
                        model_names.append(value)
                    elif isinstance(value, (list, tuple)):
                        model_names.extend(
                            item for item in value if isinstance(item, str)
                        )

            if (
                len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and isinstance(stmt.value.func.value, ast.Name)
                and stmt.value.func.value.id == "fields"
            ):
                field_name = stmt.targets[0].id
                field_type = stmt.value.func.attr
                class_fields[field_name] = field_type
                if field_type in {"Many2one", "One2many", "Many2many"} and stmt.value.args:
                    try:
                        relation = ast.literal_eval(stmt.value.args[0])
                    except Exception:
                        relation = None
                    if isinstance(relation, str):
                        field_relations[(tuple(model_names), field_name)] = relation

                kwargs = {
                    kw.arg: kw.value
                    for kw in stmt.value.keywords
                    if kw.arg
                }
                if "compute" in kwargs:
                    try:
                        store = ast.literal_eval(kwargs.get("store")) if "store" in kwargs else False
                    except Exception:
                        store = False
                    try:
                        search = ast.literal_eval(kwargs.get("search")) if "search" in kwargs else None
                    except Exception:
                        search = None
                    for model in model_names:
                        computed_contracts[(model, field_name)] = (store, search)

        for model in model_names:
            model_fields.setdefault(model, set()).update(class_fields)
            model_methods.setdefault(model, set()).update(class_methods)

# Scope mixin fields are inherited by the five scoped primary models.
scope_fields = model_fields.get("clinic.analytics.scope.mixin", set())
for scoped in [
    "clinic.analytics.snapshot",
    "clinic.analytics.forecast",
    "clinic.analytics.cohort",
    "clinic.analytics.insight",
    "clinic.analytics.schedule",
]:
    model_fields.setdefault(scoped, set()).update(scope_fields)

persistent_models = {
    "clinic.analytics.kpi",
    "clinic.analytics.snapshot",
    "clinic.analytics.snapshot.line",
    "clinic.analytics.forecast",
    "clinic.analytics.forecast.point",
    "clinic.analytics.cohort",
    "clinic.analytics.insight",
    "clinic.analytics.schedule",
}

# ----------------------------------------------------------------------
# HG6/HG7/HG8/HG9: Search/List/Form per persistent model.
# ----------------------------------------------------------------------
view_types = {model: set() for model in persistent_models}
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
        arch = record.find("./field[@name='arch']")
        if model_node is None or arch is None:
            continue
        model = (model_node.text or "").strip()
        roots = list(arch)
        if not roots:
            continue
        root_tag = roots[0].tag
        view_records.append((path, model, roots[0]))
        if model in view_types and root_tag in {"search", "list", "form"}:
            view_types[model].add(root_tag)

for model, types in view_types.items():
    missing = {"search", "list", "form"} - types
    if missing:
        fail(f"HG6/HG8/HG9 {model} missing views: {sorted(missing)}")

# ----------------------------------------------------------------------
# Model-specific view field/button contracts including nested O2M lists.
# ----------------------------------------------------------------------
def nested_model(parent_model, field_name):
    # Explicit owned O2M contracts used in nested enterprise lists.
    mapping = {
        ("clinic.analytics.snapshot", "line_ids"): "clinic.analytics.snapshot.line",
        ("clinic.analytics.forecast", "point_ids"): "clinic.analytics.forecast.point",
    }
    return mapping.get((parent_model, field_name), parent_model)


def audit_arch(node, current_model):
    for child in list(node):
        if child.tag == "field" and child.attrib.get("name"):
            field_name = child.attrib["name"]
            if current_model in model_fields and field_name not in model_fields[current_model]:
                # Related/inherited chatter framework fields are intentionally ignored.
                if field_name not in {
                    "message_ids", "message_follower_ids", "activity_ids"
                }:
                    fail(f"HG6 view field {current_model}.{field_name} missing from source contract")

            child_model = nested_model(current_model, field_name)
            for nested in list(child):
                audit_arch(nested, child_model)
            continue

        if child.tag == "button" and child.attrib.get("type") == "object":
            method = child.attrib.get("name")
            if method and method not in model_methods.get(current_model, set()):
                fail(f"HG6 object button {current_model}.{method} has no model method")

        audit_arch(child, current_model)


for _path, model, arch_root in view_records:
    if model in model_fields:
        audit_arch(arch_root, model)

# Explicit upstream inherited view contracts.
for model, fields_required, methods_required in [
    (
        "clinic.dashboard.board",
        {"analytics_forecast_count", "analytics_insight_count"},
        {"action_view_analytics_forecasts", "action_view_analytics_insights"},
    ),
    (
        "clinic.report.definition",
        {"analytics_kpi_count"},
        {"action_view_analytics_kpis"},
    ),
]:
    if not fields_required.issubset(model_fields.get(model, set())):
        fail(f"HG6 missing inherited fields on {model}")
    if not methods_required.issubset(model_methods.get(model, set())):
        fail(f"HG6 missing inherited methods on {model}")

# ----------------------------------------------------------------------
# HG8: computed non-stored fields must not be used in search domains unless
# they explicitly define search=.
# ----------------------------------------------------------------------
for _path, model, arch_root in view_records:
    if arch_root.tag != "search":
        continue
    for filter_node in arch_root.iter("filter"):
        domain = filter_node.attrib.get("domain", "")
        for (contract_model, field_name), (store, search) in computed_contracts.items():
            if contract_model == model and field_name in domain and not store and not search:
                fail(
                    f"HG8 unsearchable computed field {model}.{field_name} "
                    f"used in filter {filter_node.attrib.get('name')}"
                )

# ----------------------------------------------------------------------
# HG10 ACL coverage.
# ----------------------------------------------------------------------
acl_path = ROOT / "security/ir.model.access.csv"
with acl_path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))

acl_models = {
    row["model_id:id"].replace("model_", "").replace("_", ".")
    for row in rows
}
for model in persistent_models:
    if model not in acl_models:
        fail(f"HG10 no ACL for {model}")

security_text = (ROOT / "security/clinic_analytics_security.xml").read_text()
if "user.allowed_branch_ids.ids" not in security_text:
    fail("HG10 allowed-branch backend record rules missing")
if "group_analytics_manager" not in security_text:
    fail("HG10 manager scope rule missing")

# ----------------------------------------------------------------------
# HG2/HG3 source adapter and integration contracts.
# ----------------------------------------------------------------------
engine = (ROOT / "models/analytics_engine.py").read_text()
fixed_sources = [
    "revenue_total",
    "revenue_paid",
    "booking_count",
    "booking_completion_rate",
    "booking_no_show_rate",
    "unique_patients",
    "repeat_patient_rate",
    "membership_active",
    "membership_renewal_rate",
    "wallet_balance",
    "feedback_nps",
    "feedback_avg_rating",
    "quality_score",
    "incident_count",
    "critical_incident_count",
    "marketing_reach",
    "marketing_delivery_rate",
]
for key in fixed_sources:
    if f"def _metric_{key}" not in engine:
        fail(f"HG3 missing fixed adapter {key}")

if "request.params" in engine or "safe_eval" in engine:
    fail("HG10 arbitrary external expression surface detected")

integration = (ROOT / "models/integration_service.py").read_text()
if "clinic.audit.event" not in integration:
    fail("HG2 Audit bridge missing")
if "clinic.api.event" not in integration:
    fail("HG2 Integration API bridge missing")

# ----------------------------------------------------------------------
# Data / external contract refs and cron.
# ----------------------------------------------------------------------
kpi_data = (ROOT / "data/kpi_data.xml").read_text()
for ref in [
    "clinic_reports.report_definition_fin_revenue",
    "clinic_reports.report_definition_ops_booking",
    "clinic_reports.report_definition_ops_membership",
    "clinic_reports.report_definition_ops_wallet",
    "clinic_reports.report_definition_clinical_feedback",
]:
    if ref not in kpi_data:
        fail(f"HG2 governed report lineage missing: {ref}")

integration_views = (ROOT / "views/integration_views.xml").read_text()
if "clinic_dashboard.view_dashboard_board_form" not in integration_views:
    fail("HG2 Dashboard bridge view missing")
if "clinic_reports.view_report_definition_form" not in integration_views:
    fail("HG2 Reports bridge view missing")

cron_text = (ROOT / "data/cron_data.xml").read_text()
if "model._cron_run_due()" not in cron_text:
    fail("HG3 analytics schedule cron missing")
if "_commit_progress" not in (ROOT / "models/schedule.py").read_text():
    fail("HG3 bounded cron progress contract missing")

# ----------------------------------------------------------------------
# HARD GATE result.
# ----------------------------------------------------------------------
if ERRORS:
    print("CLINIC_ANALYTICS_GUARDRAIL: FAIL")
    for error in ERRORS:
        print(f"- {error}")
    sys.exit(1)

print("CLINIC_ANALYTICS_GUARDRAIL: PASS")
print(f"Python files: {len(python_files)}")
print(f"XML files: {len(xml_files)}")
print(f"Persistent UI models: {len(persistent_models)}")
print(f"models.Constraint: {constraint_count}")
print(f"ACL rows: {len(rows)}")
print(f"Fixed KPI adapters: {len(fixed_sources)}")
print("HARD GATE 0-15: PASS (source/static)")
