#!/usr/bin/env python3
"""Static hard gates for ClinicOne clinic_emar.

This script deliberately does not claim Odoo runtime correctness. It catches
source/package regressions before the addon is copied to the Windows runtime.
"""
from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
NOTES: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)


def note(message: str) -> None:
    NOTES.append(message)


# HARD GATE: backup/cache hygiene
for path in ROOT.rglob("*"):
    if path.is_file() and path.name.startswith("0"):
        fail(f"backup-prefixed file packaged: {path.relative_to(ROOT)}")
    if path.is_file() and (path.suffix == ".pyc" or "__pycache__" in path.parts):
        fail(f"python cache packaged: {path.relative_to(ROOT)}")

# Python compile
py_files = [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts]
for path in py_files:
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except Exception as exc:  # static tool: report compiler detail
        fail(f"python compile: {path.relative_to(ROOT)}: {exc}")
note(f"python_files={len(py_files)}")

# Manifest and data paths
manifest_path = ROOT / "__manifest__.py"
try:
    manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
except Exception as exc:
    fail(f"manifest parse failed: {exc}")
    manifest = {}
for rel in manifest.get("data", []):
    if not (ROOT / rel).is_file():
        fail(f"manifest data file missing: {rel}")

forward_forbidden = {
    "clinic_imaging", "clinic_care_plan", "clinic_package", "clinic_membership",
    "clinic_billing", "clinic_ar", "clinic_ap", "clinic_wallet", "clinic_finance",
    "clinic_accounting", "clinic_reports", "clinic_dashboard", "clinic_branch",
    "clinic_audit", "clinic_analytics",
}
for dep in sorted(set(manifest.get("depends", [])) & forward_forbidden):
    fail(f"forward/downstream dependency forbidden: {dep}")

# XML parse + Odoo 19 view syntax
xml_files = list(ROOT.rglob("*.xml"))
for path in xml_files:
    try:
        ET.parse(path)
    except Exception as exc:
        fail(f"xml parse: {path.relative_to(ROOT)}: {exc}")
    text = path.read_text(encoding="utf-8")
    if "<tree" in text or "tree,form" in text:
        fail(f"legacy tree syntax: {path.relative_to(ROOT)}")
    if re.search(r"\b(attrs|states)\s*=", text):
        fail(f"legacy attrs/states syntax: {path.relative_to(ROOT)}")
note(f"xml_files={len(xml_files)}")

# Odoo 19 constraint migration
model_py_files = [p for p in (ROOT / "models").rglob("*.py")] + [p for p in (ROOT / "wizard").rglob("*.py")]
source_text = "\n".join(p.read_text(encoding="utf-8") for p in model_py_files)
if re.search(r"^\s*_sql_constraints\s*=", source_text, flags=re.M):
    fail("legacy _sql_constraints assignment found")
constraint_count = source_text.count("models.Constraint(")
note(f"models.Constraint={constraint_count}")
if constraint_count < 9:
    fail(f"expected at least 9 models.Constraint declarations, found {constraint_count}")



# Odoo 19 registry class-layout safety
#
# Odoo 19 reconstructs model bases during registry setup. A concrete Odoo model
# extension must not also inherit from an arbitrary plain-Python helper class at
# the Python class level (for example ``class X(Helper, models.Model)``). Keep
# shared helpers as module-level functions or Odoo AbstractModel mixins.
for path in model_py_files:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or len(node.bases) <= 1:
            continue
        base_names = [ast.unparse(base) for base in node.bases]
        if any(
            base_name in {"models.Model", "models.AbstractModel", "models.TransientModel"}
            for base_name in base_names
        ):
            fail(
                "Odoo registry-unsafe Python multiple inheritance: "
                f"{path.relative_to(ROOT)}:{node.lineno} "
                f"class {node.name}({', '.join(base_names)})"
            )


# Odoo 19 UoM contract: relative_uom_id replaced the older compatibility assumptions.
med_line_text = (ROOT / "models/core/emar_medication_line.py").read_text(encoding="utf-8")
profile_text = (ROOT / "models/core/emar_medication_profile.py").read_text(encoding="utf-8")
if "relative_uom_id" not in med_line_text:
    fail("Odoo 19 relative_uom_id UoM contract missing")
if "reference_uom_id" in med_line_text or "reference_uom_id" in profile_text:
    fail("legacy/non-Odoo19 reference_uom_id contract found")
if "category_id" in med_line_text:
    fail("legacy UoM category compatibility found in medication line")

# Clinical dose must not be reused as physical stock quantity.
admin_text = (ROOT / "models/core/emar_administration.py").read_text(encoding="utf-8")
inv_integration_text = (ROOT / "models/integrations/inventory_integration.py").read_text(encoding="utf-8")
for marker in ("inventory_qty", "inventory_uom_id"):
    if marker not in admin_text or marker not in inv_integration_text:
        fail(f"clinical-dose/inventory separation missing marker: {marker}")
if 'qty = float(self.administered_qty' in inv_integration_text:
    fail("ClinicOne inventory bridge still consumes clinical administered_qty")

stock_bridge_text = (ROOT / "models/external_bridges/stock_bridge.py").read_text(encoding="utf-8")
if "move_ids_without_package" in stock_bridge_text:
    fail("removed Odoo 19 stock.picking.move_ids_without_package contract found")
if ".move_ids" not in stock_bridge_text:
    fail("Odoo 19 stock.picking.move_ids propagation contract missing")



# Schema-safe company configuration contract
#
# ``res.company`` is read by virtually every Odoo request.  eMAR operational
# settings must therefore remain non-stored proxies; otherwise replacing source
# before a successful module upgrade can make all HTTP requests fail with
# UndefinedColumn.
res_config_path = ROOT / "models/integrations/res_config_settings.py"
if not res_config_path.exists():
    fail("schema-safe eMAR company configuration file missing")
else:
    try:
        config_tree = ast.parse(res_config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse eMAR company configuration: {exc}")
        config_tree = None

    expected_company_fields = {
        "emar_default_warehouse_id",
        "emar_auto_generate_schedules",
        "emar_require_patient_scan",
        "emar_require_product_scan",
        "emar_require_double_check_high_alert",
        "emar_overdue_grace_minutes",
    }

    company_field_nodes = {}
    settings_field_nodes = {}
    if config_tree:
        for node in config_tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            target = None
            if node.name == "ResCompany":
                target = company_field_nodes
            elif node.name == "ResConfigSettings":
                target = settings_field_nodes
            if target is None:
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                    continue
                target_node = stmt.targets[0]
                if isinstance(target_node, ast.Name):
                    target[target_node.id] = stmt.value

    missing_company_fields = expected_company_fields - set(company_field_nodes)
    if missing_company_fields:
        fail(
            "schema-safe res.company eMAR field(s) missing: "
            + ", ".join(sorted(missing_company_fields))
        )

    for field_name in sorted(expected_company_fields & set(company_field_nodes)):
        value = company_field_nodes[field_name]
        if not isinstance(value, ast.Call):
            fail(f"{field_name} is not declared as an Odoo field call")
            continue
        keywords = {kw.arg: kw.value for kw in value.keywords if kw.arg}
        store_node = keywords.get("store")
        compute_node = keywords.get("compute")
        if not (
            isinstance(store_node, ast.Constant)
            and store_node.value is False
        ):
            fail(f"{field_name} must declare store=False")
        if not (
            isinstance(compute_node, ast.Constant)
            and compute_node.value == "_compute_emar_configuration"
        ):
            fail(f"{field_name} must use _compute_emar_configuration")
        if "related" in keywords:
            fail(f"{field_name} must not be a stored/related res.company column")

    missing_settings_fields = expected_company_fields - set(settings_field_nodes)
    if missing_settings_fields:
        fail(
            "res.config.settings eMAR field(s) missing: "
            + ", ".join(sorted(missing_settings_fields))
        )
    for field_name in sorted(expected_company_fields & set(settings_field_nodes)):
        value = settings_field_nodes[field_name]
        if isinstance(value, ast.Call):
            keywords = {kw.arg: kw.value for kw in value.keywords if kw.arg}
            if "related" in keywords:
                fail(
                    f"res.config.settings.{field_name} must persist explicitly "
                    "through company-scoped parameters, not a res.company column"
                )

migration_dir = ROOT / "migrations" / "19.0.3.0.0"
for migration_file in (
    "pre-10-preserve_company_settings.py",
    "post-90-verify_schema.py",
):
    migration_path = migration_dir / migration_file
    if not migration_path.exists():
        fail(f"schema-recovery migration missing: {migration_file}")
        continue
    migration_text = migration_path.read_text(encoding="utf-8")
    if "from odoo.upgrade" in migration_text or "import odoo.upgrade" in migration_text:
        fail(
            f"{migration_file} must not depend on optional odoo.upgrade utilities; "
            "use native Odoo core migration APIs"
        )
    if "Environment(cr, SUPERUSER_ID, {})" not in migration_text:
        fail(f"{migration_file} must construct a native superuser Environment")




# Odoo 19 Settings action/XML-ID contract
manifest_depends = set(manifest.get("depends", []))
if "base_setup" not in manifest_depends:
    fail("base_setup must be a direct dependency for the Odoo Settings framework")

config_view_path = ROOT / "views" / "emar_config_views.xml"
menu_view_path = ROOT / "views" / "emar_menu_views.xml"
config_view_text = config_view_path.read_text(encoding="utf-8") if config_view_path.exists() else ""
menu_view_text = menu_view_path.read_text(encoding="utf-8") if menu_view_path.exists() else ""
if "base.action_res_config_settings" in config_view_text or "base.action_res_config_settings" in menu_view_text:
    fail("removed/invalid Odoo 19 XML ID base.action_res_config_settings found")
if 'id="action_emar_config_settings"' not in config_view_text:
    fail("local eMAR res.config.settings action missing")
if 'action="action_emar_config_settings"' not in menu_view_text:
    fail("eMAR Settings menu must use the local action_emar_config_settings action")
if "'module': 'clinic_emar'" not in config_view_text:
    fail("local eMAR settings action must target the clinic_emar settings app")

# Codex bounded-worker contract is part of the package, not an external convention.
agents_path = ROOT / "AGENTS.md"
if not agents_path.exists():
    fail("AGENTS.md bounded Codex contract missing")
else:
    agents_text = agents_path.read_text(encoding="utf-8")
    for marker in ("bounded implementation worker", "Maximum **2 bounded implementation attempts**", "not a simplifier"):
        if marker not in agents_text:
            fail(f"AGENTS.md missing bounded-worker marker: {marker}")

# Core search/list/form matrix
view_text = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("views/*.xml"))
primary_models = [
    "clinic.emar.medication.profile",
    "clinic.emar.prescription",
    "clinic.emar.medication.line",
    "clinic.emar.order",
    "clinic.emar.schedule",
    "clinic.emar.administration",
    "clinic.emar.alert",
]
for model in primary_models:
    if model not in view_text:
        fail(f"no views found for primary model: {model}")
    # model appears in dedicated files, but enforce tags globally as a minimum.
if view_text.count("<search") < len(primary_models):
    fail("search-view matrix incomplete")
if view_text.count("<list") < len(primary_models):
    fail("list-view matrix incomplete")
if view_text.count("<form") < len(primary_models):
    fail("form-view matrix incomplete")

# Object buttons -> method definitions (best-effort source contract)
object_buttons = set()
for path in xml_files:
    text = path.read_text(encoding="utf-8")
    object_buttons.update(re.findall(r'<button[^>]+name="([A-Za-z_][A-Za-z0-9_]*)"[^>]+type="object"', text))
method_defs = set(re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source_text, flags=re.M))
for method in sorted(object_buttons - method_defs):
    fail(f"object button has no addon Python method: {method}")
note(f"object_buttons={len(object_buttons)}")

# Security coverage
acl_path = ROOT / "security/ir.model.access.csv"
if acl_path.exists():
    acl_text = acl_path.read_text(encoding="utf-8-sig").lstrip("\r\n")
    rows = list(csv.DictReader(acl_text.splitlines()))
    model_ids = {row["model_id:id"] for row in rows}
    for model in primary_models:
        xml_model = "model_" + model.replace(".", "_")
        if xml_model not in model_ids:
            fail(f"ACL missing for {model}")
else:
    fail("ACL CSV missing")

rules_text = (ROOT / "security/emar_rules.xml").read_text(encoding="utf-8") if (ROOT / "security/emar_rules.xml").exists() else ""
for model in primary_models:
    xml_model = "model_" + model.replace(".", "_")
    if xml_model not in rules_text:
        fail(f"company record rule missing for {model}")

# ORM state guard contract
workflow_guard = (ROOT / "models/integrations/workflow_guard.py")
if not workflow_guard.exists():
    fail("ORM workflow guard missing")
else:
    guard_text = workflow_guard.read_text(encoding="utf-8")
    for model in ("clinic.emar.prescription", "clinic.emar.order", "clinic.emar.schedule", "clinic.emar.administration"):
        if model not in guard_text:
            fail(f"ORM state guard missing for {model}")

# Odoo 19 mail tracking contract on the medication-line ledger.
medication_line_source = (ROOT / "models/core/emar_medication_line.py").read_text(encoding="utf-8")
medication_line_view = (ROOT / "views/emar_medication_line_views.xml").read_text(encoding="utf-8")
if '"mail.thread"' not in medication_line_source:
    fail("Medication Line uses tracking=True but does not inherit mail.thread")
if '"mail.activity.mixin"' not in medication_line_source:
    fail("Medication Line enterprise activity contract missing mail.activity.mixin")
if "<chatter/>" not in medication_line_view:
    fail("Medication Line form does not expose chatter/activity history")
if "order.clinic_patient_id" not in medication_line_source or "order.clinic_doctor_id" not in medication_line_source:
    fail("Medication Line core header resolver does not use canonical ClinicOne patient/doctor")


# Upgrade-window background-job schema safety
schedule_source = (ROOT / "models/core/emar_schedule.py").read_text(encoding="utf-8")
wizard_source = (ROOT / "wizard/emar_reschedule_wizard.py").read_text(encoding="utf-8")
for required_marker in (
    "def _cron_schema_ready",
    "SELECT to_regclass(%s)",
    "if not self._cron_schema_ready()",
):
    if required_marker not in schedule_source:
        fail(f"schedule upgrade-window schema guard missing: {required_marker}")
for required_marker in (
    "def _transient_vacuum",
    "with self.env.cr.savepoint()",
    "except UndefinedTable",
):
    if required_marker not in wizard_source:
        fail(f"wizard transient schema guard missing: {required_marker}")

# Regression-test floor
for path in ROOT.glob("tests/test_*.py"):
    pass
test_text = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("tests/test_*.py"))
test_count = len(re.findall(r"^\s*def\s+test_", test_text, flags=re.M))
note(f"test_methods={test_count}")
if test_count < 30:
    fail(f"enterprise regression-test floor not met: {test_count}")

# Critical clinical-state/canonical-context integrity markers
schedule_text = (ROOT / "models/core/emar_schedule.py").read_text(encoding="utf-8")
if "order_id.clinic_patient_id" not in schedule_text or "order_id.clinic_doctor_id" not in schedule_text:
    fail("schedule does not depend on canonical ClinicOne patient/doctor identity")
if "order_id.clinic_patient_id" not in admin_text or "order_id.clinic_doctor_id" not in admin_text:
    fail("administration does not depend on canonical ClinicOne patient/doctor identity")
if 'try:\n                    rec.schedule_id._emar_guarded_write({"state": "administered"})' in admin_text:
    fail("administration still swallows schedule-finalization failure")

# Clinical cross-comodel safety marker
for bridge in (ROOT / "models/external_bridges/account_bridge.py", ROOT / "models/external_bridges/stock_bridge.py"):
    text = bridge.read_text(encoding="utf-8")
    if "_clinic_patient_from" not in text or "_clinic_doctor_from" not in text:
        fail(f"canonical clinical resolver missing: {bridge.relative_to(ROOT)}")

print("clinic_emar Enterprise Development Guardrail")
for item in NOTES:
    print(f"[INFO] {item}")
if ERRORS:
    for item in ERRORS:
        print(f"[FAIL] {item}")
    print(f"RESULT: FAIL ({len(ERRORS)} issue(s))")
    sys.exit(1)
print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)")
