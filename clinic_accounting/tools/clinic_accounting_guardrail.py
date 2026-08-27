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


# ---------------------------------------------------------------------------
# HARD GATE 0 - Project Identity Preflight
# ---------------------------------------------------------------------------
manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
depends = set(manifest.get("depends", []))

if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative version must be 19.0.1.0.0")

required_dependencies = {
    "account",
    "analytic",
    "clinic_base",
    "clinic_audit",
    "clinic_branch",
    "clinic_billing",
    "clinic_ar",
    "clinic_ap",
    "clinic_wallet",
    "clinic_finance",
}
missing_dependencies = required_dependencies - depends
if missing_dependencies:
    fail(0, f"missing financial integration dependencies: {sorted(missing_dependencies)}")

if "clinic_l10n_id" in depends:
    fail(0, "downstream clinic_l10n_id must not be a dependency")

build_marker = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_ACCOUNTING_BUILD_20260820_V19.0.1.0.0" not in build_marker:
    fail(0, "authoritative Accounting build marker missing")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 23 / clinic_accounting / upstream-through-clinic_finance identity locked")


# ---------------------------------------------------------------------------
# HARD GATE 1 - Codex is not architect
# ---------------------------------------------------------------------------
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
agents_lower = agents.lower()
required_agent_terms = (
    "bounded implementation worker",
    "maximum 2",
    "architect",
    "simplifier",
    "endless retry",
)
if not all(term in agents_lower for term in required_agent_terms):
    fail(1, "Codex bounded implementation-worker contract is incomplete")
else:
    ok(1, "Codex is bounded implementer; architect/simplifier/endless-retry roles forbidden")


# ---------------------------------------------------------------------------
# Parse model source once for structural gates.
# ---------------------------------------------------------------------------
model_files = [path for path in ROOT.glob("models/*.py") if path.name != "__init__.py"]
test_files = list(ROOT.glob("tests/*.py"))
python_files = list(ROOT.rglob("*.py"))
xml_files = list(ROOT.rglob("*.xml"))

model_source = "\n".join(path.read_text(encoding="utf-8") for path in model_files)

defined_models = set()
constraints = 0
indexes = 0
class_methods = 0
test_methods = 0
dangerous_multi_inherit = []
python_errors = []

for path in python_files:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        python_errors.append(f"{path.relative_to(ROOT)}: {exc}")
        continue

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        explicit_name = False
        model_name = None
        inherit_value = None

        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods += 1
                if path.parent.name == "tests" and stmt.name.startswith("test_"):
                    test_methods += 1

            if not isinstance(stmt, ast.Assign):
                continue

            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue

                if target.id == "_name":
                    explicit_name = True
                    try:
                        value = ast.literal_eval(stmt.value)
                        if isinstance(value, str):
                            model_name = value
                    except Exception:
                        pass

                elif target.id == "_inherit":
                    try:
                        inherit_value = ast.literal_eval(stmt.value)
                    except Exception:
                        pass

                if isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    if (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "models"
                    ):
                        if func.attr == "Constraint":
                            constraints += 1
                        elif func.attr == "Index":
                            indexes += 1

        if model_name:
            defined_models.add(model_name)

        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_multi_inherit.append(
                f"{path.relative_to(ROOT)}::{node.name}"
            )

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))


# ---------------------------------------------------------------------------
# HARD GATE 2 - Existing Function Preservation
# ---------------------------------------------------------------------------
for forbidden_owner in (
    '_name = "clinic.billing.invoice"',
    '_name = "clinic.ar.invoice"',
    '_name = "clinic.ar.payment"',
    '_name = "clinic.ap"',
    '_name = "clinic.wallet"',
    '_name = "clinic.wallet.transaction"',
    '_name = "clinic.finance.transaction"',
    '_name = "clinic.finance.transfer"',
):
    if forbidden_owner in model_source:
        fail(2, f"upstream model ownership duplicated: {forbidden_owner}")

if '_name = "account.move"' in model_source or '_name = "account.move.line"' in model_source:
    fail(2, "Accounting must inherit native legal-ledger models, not redefine their ownership")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "Billing/AR/AP/Wallet/Finance and native Odoo legal-ledger ownership preserved")


# ---------------------------------------------------------------------------
# HARD GATE 3 - Enterprise Completeness, not just tests
# ---------------------------------------------------------------------------
required_files = {
    "security/clinic_accounting_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/accounting_ledger_views.xml",
    "views/accounting_adjustment_views.xml",
    "views/accounting_close_views.xml",
    "views/accounting_statement_views.xml",
    "views/account_move_views.xml",
    "views/res_config_settings_views.xml",
    "report/accounting_statement_templates.xml",
    "report/accounting_statement_report.xml",
    "report/accounting_close_templates.xml",
    "report/accounting_close_report.xml",
    "tests/test_accounting_enterprise.py",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/UI_UX_MATRIX.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/SOURCE_STATIC_VALIDATION.md",
}
missing_files = sorted(item for item in required_files if not (ROOT / item).exists())
if missing_files:
    fail(3, f"enterprise deliverable files missing: {missing_files}")
else:
    ok(3, "models + security + workflows + UI + reports + scheduler + tests + evidence present")


# ---------------------------------------------------------------------------
# HARD GATE 4 - Full Structural Inventory
# ---------------------------------------------------------------------------
persistent_models = {
    "clinic.accounting.ledger",
    "clinic.accounting.adjustment",
    "clinic.accounting.adjustment.line",
    "clinic.accounting.close",
    "clinic.accounting.close.check",
    "clinic.accounting.statement",
    "clinic.accounting.statement.line",
}
missing_models = persistent_models - defined_models
if missing_models:
    fail(4, f"persistent model inventory incomplete: {sorted(missing_models)}")
else:
    ok(4, "7 Accounting-owned persistent models plus support/inherited models inventoried")


# ---------------------------------------------------------------------------
# HARD GATE 5 - Human-Friendly Coding Structure
# ---------------------------------------------------------------------------
required_model_files = {
    "mixins.py",
    "accounting_ledger.py",
    "accounting_adjustment.py",
    "accounting_close.py",
    "accounting_statement.py",
    "accounting_settings.py",
    "integration_bridge.py",
}
actual_model_names = {path.name for path in model_files}
if not required_model_files.issubset(actual_model_names):
    fail(5, f"model responsibility split incomplete: {sorted(required_model_files - actual_model_names)}")
elif len(model_files) < 7:
    fail(5, "too few focused model files")
else:
    ok(5, f"human-friendly responsibilities separated across {len(model_files)} focused model files")


# ---------------------------------------------------------------------------
# Parse XML once.
# ---------------------------------------------------------------------------
xml_errors = []
all_xml_parts = []
for path in xml_files:
    content = path.read_text(encoding="utf-8")
    all_xml_parts.append(content)
    try:
        ET.parse(path)
    except Exception as exc:
        xml_errors.append(f"{path.relative_to(ROOT)}: {exc}")

if xml_errors:
    fail(12, "XML parse errors: " + " | ".join(xml_errors))

all_xml = "\n".join(all_xml_parts)


# ---------------------------------------------------------------------------
# HARD GATE 6 - Professional Form Design
# ---------------------------------------------------------------------------
professional_tokens = (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "<chatter",
)
missing_professional = [token for token in professional_tokens if token not in all_xml]
if missing_professional:
    fail(6, f"professional form design tokens missing: {missing_professional}")
else:
    ok(6, "statusbars, smart buttons, governed actions, body actions and chatter are present")


# ---------------------------------------------------------------------------
# HARD GATE 7 - UI/UX Matrix per model
# ---------------------------------------------------------------------------
view_matrix = {
    model: {"search": False, "list": False, "form": False}
    for model in persistent_models
}

for path in xml_files:
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue

        model = None
        arch = None
        for field in record.findall("field"):
            if field.attrib.get("name") == "model":
                model = (field.text or "").strip()
            elif field.attrib.get("name") == "arch":
                arch = field

        if model not in view_matrix or arch is None:
            continue

        children = list(arch)
        if children and children[0].tag in view_matrix[model]:
            view_matrix[model][children[0].tag] = True

missing_matrix = {
    model: [kind for kind, present in kinds.items() if not present]
    for model, kinds in view_matrix.items()
    if not all(kinds.values())
}
if missing_matrix:
    fail(7, f"Search/List/Form matrix incomplete: {missing_matrix}")
else:
    ok(7, "Search/List/Form matrix complete for all 7 Accounting-owned persistent models")


# ---------------------------------------------------------------------------
# HARD GATE 8 - Search View mandatory + ClinicOne Odoo19 runtime contract
# ---------------------------------------------------------------------------
search_count = 0
search_violations = []

for path in xml_files:
    root = ET.parse(path).getroot()
    for search in root.iter("search"):
        search_count += 1
        if search.attrib:
            search_violations.append(
                f"{path.relative_to(ROOT)}::<search> attrs={dict(search.attrib)}"
            )
        for child in list(search):
            if child.tag == "group" and child.attrib:
                search_violations.append(
                    f"{path.relative_to(ROOT)}::<search>/<group> attrs={dict(child.attrib)}"
                )

if search_violations:
    fail(8, "invalid ClinicOne Odoo19 search architecture: " + " | ".join(search_violations))
elif search_count < 9:
    fail(8, f"search-view coverage too low: {search_count}")
else:
    ok(8, f"{search_count} search views pass the ClinicOne Odoo19 attribute-free search/group contract")


# ---------------------------------------------------------------------------
# HARD GATE 9 - List View enterprise quality
# ---------------------------------------------------------------------------
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    row_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 10:
        fail(9, f"enterprise list coverage too low: {list_count}")
    elif row_buttons < 20:
        fail(9, f"enterprise action-button coverage too low: {row_buttons}")
    else:
        ok(9, f"{list_count} list tags and {row_buttons} object-button declarations pass enterprise list/action gate")


# ---------------------------------------------------------------------------
# HARD GATE 10 - Security cannot be defeated by UI
# ---------------------------------------------------------------------------
security = (ROOT / "security/clinic_accounting_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(
    r'<record[^>]*model="res.groups">(.*?)</record>',
    security,
    flags=re.S,
)

if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id is used directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo 19 res.groups.privilege hierarchy is missing")
if len(acl_rows) < 16:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")

record_rule_count = security.count('model="ir.rule"')
if record_rule_count < 7:
    fail(10, f"company record-rule coverage too low: {record_rule_count}")

for backend_guard in (
    "accounting_transition",
    "Adjustment content can only be edited while Draft",
    "Adjustment lines are immutable outside Draft",
    "Close workflow, preflight audit, and native-lock evidence",
    "Statement workflow and generation audit fields",
):
    if backend_guard not in model_source:
        fail(10, f"backend governance guard missing: {backend_guard}")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"4-role privilege hierarchy + {record_rule_count} company rules + {len(acl_rows)} ACL rows + RPC workflow guards pass")


# ---------------------------------------------------------------------------
# HARD GATE 12 - Odoo19 code style / contracts
# ---------------------------------------------------------------------------
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_multi_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_multi_inherit}")
if constraints < 9:
    fail(12, f"too few Odoo 19 models.Constraint declarations: {constraints}")
if indexes < 3:
    fail(12, f"too few Odoo 19 models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
for fragile in (
    "clinic_finance.view_",
    "clinic_wallet.view_",
    "clinic_ar.view_",
    "clinic_ap.view_",
    "clinic_billing.view_",
    "clinic_patient.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile custom upstream inherited-view XML ID found: {fragile}")

if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not use stable base.res_config_settings_view_form anchor")

if "fiscalyear_lock_date" not in model_source:
    fail(12, "native Odoo fiscal lock-date integration missing")
if "account.move" not in model_source or "account.move.line" not in model_source:
    fail(12, "native Odoo legal ledger integration missing")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 source contracts pass; models.Constraint={constraints}, models.Index={indexes}")


# ---------------------------------------------------------------------------
# HARD GATE 13 - Useful comments
# ---------------------------------------------------------------------------
comment_lines = 0
docstrings = 0
for path in model_files:
    source = path.read_text(encoding="utf-8")
    comment_lines += sum(
        1 for line in source.splitlines()
        if line.strip().startswith("#")
    )
    try:
        tree = ast.parse(source)
    except SyntaxError:
        continue
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and ast.get_docstring(node):
            docstrings += 1

if comment_lines < 20 or docstrings < 8:
    fail(13, f"useful-comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful architecture/business comments and docstrings pass: comments={comment_lines}, docstrings={docstrings}")


# ---------------------------------------------------------------------------
# HARD GATE 14 - Codex retry limit
# ---------------------------------------------------------------------------
if "maximum 2" not in agents or "maximum 1 repeat" not in agents:
    fail(14, "bounded retry rule is incomplete")
else:
    ok(14, "Codex retry limit fixed at maximum two bounded attempts and one repeated root cause")


# ---------------------------------------------------------------------------
# HARD GATE 15 - Enterprise completeness matrix
# ---------------------------------------------------------------------------
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate static readiness from runtime acceptance")
elif test_methods < 60:
    fail(15, f"runtime contract/regression suite too small: {test_methods}")
else:
    ok(15, f"enterprise completeness matrix + {test_methods} runtime contract tests pass static gate")


print("ClinicOne clinic_accounting Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] persistent_models={len(persistent_models)} models.Constraint={constraints} models.Index={indexes}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} record_rules={record_rule_count}")
print(f"[INFO] test_methods={test_methods} class_methods={class_methods}")

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/SMOKE TEST PENDING)")
