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


# HARD GATE 0 - Project identity.
manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
depends = set(manifest.get("depends", []))

if manifest.get("version") != "19.0.1.0.1":
    fail(0, "authoritative version must be 19.0.1.0.1")

required = {
    "account",
    "l10n_id",
    "l10n_id_efaktur_coretax",
    "clinic_branch",
    "clinic_billing",
    "clinic_ar",
    "clinic_ap",
    "clinic_wallet",
    "clinic_finance",
    "clinic_accounting",
}
if not required.issubset(depends):
    fail(0, f"missing localization/integration dependencies: {sorted(required - depends)}")

marker = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_L10N_ID_BUILD_20260820_V19.0.1.0.1" not in marker:
    fail(0, "authoritative build marker missing")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 24 / clinic_l10n_id / native Indonesia localization identity locked")


# HARD GATE 1 and 14 - Codex governance.
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
if not all(term in agents for term in (
    "bounded implementation worker",
    "architect",
    "simplifier",
    "endless retry",
    "maximum 2",
)):
    fail(1, "Codex bounded-worker contract incomplete")
else:
    ok(1, "Codex is bounded implementer; architecture and simplification are outside its role")

if "maximum 1 repeat" not in agents:
    fail(14, "bounded retry rule incomplete")
else:
    ok(14, "Codex retry limit is maximum two bounded attempts and one repeated root cause")


# Parse Python source.
python_files = list(ROOT.rglob("*.py"))
model_files = [p for p in ROOT.glob("models/*.py") if p.name != "__init__.py"]
xml_files = list(ROOT.rglob("*.xml"))
model_source = "\n".join(p.read_text(encoding="utf-8") for p in model_files)

defined_models = set()
constraints = 0
indexes = 0
dangerous_inherit = []
test_methods = 0
class_methods = 0
python_errors = []
comment_lines = 0
docstrings = 0

for path in model_files:
    comment_lines += sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("#")
    )

for path in python_files:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        python_errors.append(f"{path.relative_to(ROOT)}: {exc}")
        continue

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        if ast.get_docstring(node):
            docstrings += 1

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
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{node.name}")

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))


# HARD GATE 2 - Preserve native/upstream ownership.
for forbidden in (
    '_name = "account.tax"',
    '_name = "account.move"',
    '_name = "account.move.line"',
    '_name = "l10n_id_efaktur_coretax.document"',
    '_name = "clinic.billing.invoice"',
    '_name = "clinic.ar.invoice"',
    '_name = "clinic.ap"',
    '_name = "clinic.wallet.transaction"',
    '_name = "clinic.finance.transaction"',
):
    if forbidden in model_source:
        fail(2, f"native/upstream ownership duplicated: {forbidden}")

if "def _generate_xml(" in model_source:
    fail(2, "ClinicOne must not duplicate native Coretax XML generation")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "native l10n_id/Coretax and upstream ClinicOne ownership preserved")


# HARD GATE 3 - Enterprise completeness beyond tests.
required_files = {
    "security/clinic_l10n_id_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/tax_profile_views.xml",
    "views/tax_report_views.xml",
    "views/numbering_policy_views.xml",
    "views/compliance_views.xml",
    "views/integration_views.xml",
    "views/res_config_settings_views.xml",
    "report/tax_report_templates.xml",
    "report/tax_report_report.xml",
    "report/compliance_templates.xml",
    "report/compliance_report.xml",
    "tests/test_l10n_id_enterprise.py",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/UI_UX_MATRIX.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/SOURCE_STATIC_VALIDATION.md",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise deliverable files missing: {missing_files}")
else:
    ok(3, "models + security + UI + PPN reporting + compliance + numbering + reports + tests + docs present")


# HARD GATE 4 - Structural inventory.
persistent_models = {
    "clinic.l10n.id.tax.profile",
    "clinic.l10n.id.tax.report",
    "clinic.l10n.id.tax.report.line",
    "clinic.l10n.id.numbering.policy",
    "clinic.l10n.id.compliance.run",
    "clinic.l10n.id.compliance.line",
}
missing_models = persistent_models - defined_models
if missing_models:
    fail(4, f"persistent model inventory incomplete: {sorted(missing_models)}")
else:
    ok(4, "6 localization-owned persistent models plus support/inherited models inventoried")


# HARD GATE 5 - Human friendly coding structure.
required_model_files = {
    "mixins.py",
    "tax_profile.py",
    "tax_report.py",
    "numbering_policy.py",
    "compliance.py",
    "settings.py",
    "integration_bridge.py",
}
actual_model_files = {p.name for p in model_files}
if not required_model_files.issubset(actual_model_files):
    fail(5, f"focused model-file split incomplete: {sorted(required_model_files - actual_model_files)}")
else:
    ok(5, f"human-friendly responsibilities split across {len(model_files)} focused model files")


# Parse XML.
xml_errors = []
all_xml_parts = []
for path in xml_files:
    content = path.read_text(encoding="utf-8")
    all_xml_parts.append(content)
    try:
        ET.parse(path)
    except Exception as exc:
        xml_errors.append(f"{path.relative_to(ROOT)}: {exc}")

all_xml = "\n".join(all_xml_parts)
if xml_errors:
    fail(12, "XML parse errors: " + " | ".join(xml_errors))


# HARD GATE 6 - Professional forms.
for token in ('widget="statusbar"', "oe_stat_button", "btn-primary", 'class="d-flex gap-2', "<chatter"):
    if token not in all_xml:
        fail(6, f"professional form token missing: {token}")

if not any(item.startswith("[FAIL] HARD GATE 6") for item in errors):
    ok(6, "professional forms include statusbars, smart buttons, governed actions, body actions and chatter")


# HARD GATE 7 - Search/List/Form matrix.
view_matrix = {model: {"search": False, "list": False, "form": False} for model in persistent_models}
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
    ok(7, "Search/List/Form matrix complete for all 6 localization-owned persistent models")


# HARD GATE 8 - Search view contract.
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

if search_violations:
    fail(8, "invalid ClinicOne Odoo19 search structure: " + " | ".join(search_violations))
elif search_count < 7:
    fail(8, f"search-view coverage too low: {search_count}")
else:
    ok(8, f"{search_count} search views pass ClinicOne Odoo19 search/group contract")

# Search-domain safety for computed fields used by Numbering Policy filters.
numbering_source = (ROOT / "models/numbering_policy.py").read_text(encoding="utf-8")
if "domain=\"[('compliant','=',False)]\"" in all_xml:
    if not re.search(
        r"compliant\s*=\s*fields\.Boolean\(.*?store\s*=\s*True",
        numbering_source,
        flags=re.S,
    ):
        fail(8, "Numbering Policy mismatch filter requires compliant to be stored/searchable")


# HARD GATE 9 - Enterprise lists.
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> view found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 8:
        fail(9, f"list coverage too low: {list_count}")
    elif object_buttons < 25:
        fail(9, f"object-button coverage too low: {object_buttons}")
    else:
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise UI gate")


# HARD GATE 10 - Security backend.
security = (ROOT / "security/clinic_l10n_id_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(r'<record[^>]*model="res.groups">(.*?)</record>', security, flags=re.S)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo 19 privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if len(acl_rows) < 12:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")
if record_rules < 6:
    fail(10, f"record-rule coverage too small: {record_rules}")

for backend_guard in (
    "l10n_transition",
    "Locked PPN Reports",
    "will not mutate journal",
    "Compliance workflow and audit fields",
):
    if backend_guard not in model_source:
        fail(10, f"backend governance guard missing: {backend_guard}")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"4-role security + {record_rules} company rules + {len(acl_rows)} ACL rows + RPC guards pass")


# HARD GATE 12 - Odoo19 style / safety.
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 6:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 4:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")

for fragile in (
    "clinic_accounting.view_",
    "clinic_finance.view_",
    "clinic_billing.view_",
    "clinic_ar.view_",
    "clinic_ap.view_",
    "clinic_wallet.view_",
    "clinic_patient.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile upstream custom inherited-view XML ID found: {fragile}")

if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not use stable base.res_config_settings_view_form")

if "l10n_id_efaktur_coretax.document" not in model_source:
    fail(12, "native Coretax document integration missing")
if "account.tax" not in model_source or "account.move.line" not in model_source:
    fail(12, "native tax/legal-ledger integration missing")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 source contracts pass; models.Constraint={constraints}, models.Index={indexes}")


# HARD GATE 13 - Useful comments.
if comment_lines < 20 or docstrings < 8:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful comments/docstrings pass: comments={comment_lines}, docstrings={docstrings}")


# HARD GATE 15 - Completeness matrix and tests.
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate source/static from runtime")
elif test_methods < 60:
    fail(15, f"runtime regression suite too small: {test_methods}")
else:
    ok(15, f"enterprise completeness matrix + {test_methods} runtime contract tests pass source/static gate")


print("ClinicOne clinic_l10n_id Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] persistent_models={len(persistent_models)} models.Constraint={constraints} models.Index={indexes}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} record_rules={record_rules}")
print(f"[INFO] test_methods={test_methods} class_methods={class_methods}")

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/SMOKE TEST PENDING)")

