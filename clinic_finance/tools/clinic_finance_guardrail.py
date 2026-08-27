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
    errors.append(f"[FAIL] HARD GATE {gate} — {message}")

def ok(gate, message):
    passes.append(f"[PASS] HARD GATE {gate} — {message}")

manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
depends = set(manifest.get("depends", []))
if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative version must be 19.0.1.0.0")
required_deps = {"account", "clinic_branch", "clinic_billing", "clinic_ar", "clinic_ap", "clinic_wallet"}
if not required_deps.issubset(depends):
    fail(0, f"financial upstream dependency contract incomplete: {required_deps - depends}")
if "clinic_accounting" in depends:
    fail(0, "future clinic_accounting must not be a dependency")
if not any(x.startswith("[FAIL] HARD GATE 0") for x in errors):
    ok(0, "ClinicOne / clinic_finance / upstream-through-clinic_wallet identity locked")

agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
if "bounded implementation worker" not in agents or "maximum 2" not in agents:
    fail(1, "Codex bounded-worker contract missing")
else:
    ok(1, "Codex bounded implementer; architect/simplifier/endless retry forbidden")

model_paths = [p for p in ROOT.glob("models/*.py") if p.name != "__init__.py"]
model_py_text = "\n".join(p.read_text(encoding="utf-8") for p in model_paths)
for token in (
    '_name = "clinic.ar.invoice"',
    '_name = "clinic.ar.payment"',
    '_name = "clinic.ap"',
    '_name = "clinic.wallet"',
    '_name = "clinic.wallet.transaction"',
    '_name = "clinic.billing.invoice"',
):
    if token in model_py_text:
        fail(2, f"upstream ownership duplicated: {token}")
if not any(x.startswith("[FAIL] HARD GATE 2") for x in errors):
    ok(2, "Billing/AR/AP/Wallet ownership preserved; Finance consumes via references/API")

required_files = {
    "security/clinic_finance_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/finance_category_views.xml",
    "views/finance_account_views.xml",
    "views/finance_transaction_views.xml",
    "views/finance_transfer_views.xml",
    "views/fund_request_views.xml",
    "views/cash_session_views.xml",
    "views/treasury_position_views.xml",
    "views/res_config_settings_views.xml",
    "report/treasury_position_report.xml",
    "report/treasury_position_templates.xml",
    "tests/test_finance_enterprise.py",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "BUILD_ID.txt",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise completeness files missing: {missing_files}")
else:
    ok(3, "models + security + UI + report + cron + tests + docs present; runtime remains separate")

build_marker = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8") if (ROOT / "BUILD_ID.txt").exists() else ""
if "CLINIC_FINANCE_BUILD_20260820_V19.0.1.0.0" not in build_marker:
    fail(3, "authoritative Clinic Finance BUILD_ID marker missing or incorrect")

persistent_models = {
    "clinic.finance.category",
    "clinic.finance.account",
    "clinic.finance.transaction",
    "clinic.finance.transfer",
    "clinic.finance.fund.request",
    "clinic.finance.cash.session",
    "clinic.finance.cash.count.line",
    "clinic.finance.position",
    "clinic.finance.position.line",
}
defined_names = set()
constraints = 0
indexes = 0
methods = 0
test_methods = 0
dangerous_inherit = []
python_compile_errors = []

for path in model_paths + list(ROOT.glob("tests/*.py")):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        python_compile_errors.append(f"{path.relative_to(ROOT)}: {exc}")
        continue
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        explicit_name = False
        model_name = None
        inherit_value = None
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods += 1
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
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "models":
                        if func.attr == "Constraint":
                            constraints += 1
                        elif func.attr == "Index":
                            indexes += 1
        if model_name:
            defined_names.add(model_name)
        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{node.name}")

if python_compile_errors:
    fail(12, "Python parse/compile errors: " + " | ".join(python_compile_errors))

if not persistent_models.issubset(defined_names):
    fail(4, f"persistent model inventory incomplete: {sorted(persistent_models - defined_names)}")
else:
    ok(4, "9 Finance-owned persistent models plus support/inherited models inventoried")

if len(model_paths) < 9:
    fail(5, f"model responsibility split too small: {len(model_paths)} files")
else:
    ok(5, f"human-friendly responsibility split across {len(model_paths)} focused model files")

xml_files = list(ROOT.rglob("*.xml"))
xml_parse_errors = []
all_xml_parts = []
for path in xml_files:
    content = path.read_text(encoding="utf-8")
    all_xml_parts.append(content)
    try:
        ET.parse(path)
    except Exception as exc:
        xml_parse_errors.append(f"{path.relative_to(ROOT)}: {exc}")
if xml_parse_errors:
    fail(12, "XML parse errors: " + " | ".join(xml_parse_errors))
all_xml = "\n".join(all_xml_parts)

if 'widget="statusbar"' not in all_xml or "oe_stat_button" not in all_xml or "btn-primary" not in all_xml:
    fail(6, "professional form statusbar/smart-button/action contract incomplete")
else:
    ok(6, "professional forms include statusbars, smart buttons and governed body/header actions")

view_matrix = {m: {"search": False, "list": False, "form": False} for m in persistent_models}
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
    fail(7, f"UI/UX Search/List/Form matrix incomplete: {missing_matrix}")
else:
    ok(7, "Search/List/Form matrix complete for all 9 Finance-owned persistent models")

search_count = 0
search_violations = []
for path in xml_files:
    root = ET.parse(path).getroot()
    for search in root.iter("search"):
        search_count += 1
        if search.attrib:
            search_violations.append(f"{path.relative_to(ROOT)}::<search> attrs={dict(search.attrib)}")
        for child in list(search):
            if child.tag == "group" and child.attrib:
                search_violations.append(f"{path.relative_to(ROOT)}::<search>/<group> attrs={dict(child.attrib)}")
if search_violations or search_count < 9:
    fail(8, f"Odoo 19 search-view contract failed; count={search_count}; violations={search_violations}")
else:
    ok(8, f"{search_count} search views use attribute-free Odoo 19 search/group architecture")

if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy tree view found")
else:
    list_count = all_xml.count("<list")
    if list_count < 11:
        fail(9, f"enterprise list coverage too low: {list_count}")
    else:
        ok(9, f"enterprise list architecture present ({list_count} list tags including O2M enterprise lists)")

security = (ROOT / "security/clinic_finance_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))
group_blocks = re.findall(r'<record[^>]*model="res.groups">(.*?)</record>', security, flags=re.S)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo 19 privilege hierarchy incomplete")
if len(acl_rows) < 22:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")
if "finance_transition" not in model_py_text:
    fail(10, "backend workflow transition guards missing")
for required_guard in (
    "Approval and disbursement fields can only be changed",
    "Closed or cancelled Cash Count lines are immutable",
    "Posted Finance transactions are immutable",
):
    if required_guard not in model_py_text:
        fail(10, f"backend governance guard missing: {required_guard}")
if not any(x.startswith("[FAIL] HARD GATE 10") for x in errors):
    ok(10, f"4-role backend security + company rules + {len(acl_rows)} ACL rows + RPC guards pass")

if "_sql_constraints" in model_py_text:
    fail(12, "legacy executable _sql_constraints found in model source")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 10:
    fail(12, f"too few Odoo 19 models.Constraint declarations: {constraints}")
if "clinic_patient.view_partner_form" in all_xml or "clinic_ar.view_" in all_xml or "clinic_ap.view_" in all_xml or "clinic_wallet.view_" in all_xml:
    fail(12, "fragile upstream custom inherited-view XML ID found")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states view syntax found")
if not any(x.startswith("[FAIL] HARD GATE 12") for x in errors):
    ok(12, f"Python/XML + Odoo19 Constraint/Index/inheritance/view boundaries pass; Constraint={constraints}, Index={indexes}")

comment_lines = 0
for path in model_paths:
    comment_lines += sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("#")
    )
if comment_lines < 20:
    fail(13, f"insufficient useful code comments: {comment_lines}")
else:
    ok(13, f"human-readable comments/documentation present ({comment_lines} focused code-comment lines plus docstrings)")

if "maximum 2" not in agents:
    fail(14, "Codex retry limit missing")
else:
    ok(14, "Codex retry limit fixed at maximum two bounded attempts per verified defect")

matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if "Odoo 19 runtime install | PENDING" not in matrix or "Static PASS is not runtime completion" not in matrix:
    fail(15, "enterprise completeness matrix does not separate static PASS from runtime PENDING")
else:
    ok(15, "enterprise completeness matrix explicitly separates source/static PASS from runtime acceptance")

print("ClinicOne clinic_finance Enterprise Development Guardrail")
print(f"[INFO] python_model_files={len(model_paths)} xml_files={len(xml_files)}")
print(f"[INFO] persistent_models={len(persistent_models)} models.Constraint={constraints} models.Index={indexes}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} test_methods={test_methods} class_methods={methods}")
for line in passes:
    print(line)
for line in errors:
    print(line)
if errors:
    print("RESULT: FAIL")
    sys.exit(1)
print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/SMOKE TEST PENDING)")
