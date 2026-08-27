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


manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
depends = set(manifest.get("depends", []))

# HARD GATE 0 - Project identity.
if manifest.get("version") != "19.0.1.0.1":
    fail(0, "authoritative version must be 19.0.1.0.1")

required_dependencies = {
    "clinic_patient",
    "clinic_treatment_catalog",
    "clinic_booking",
    "clinic_queue_room",
    "clinic_encounter",
    "clinic_billing",
    "clinic_ar",
    "clinic_ap",
    "clinic_wallet",
    "clinic_finance",
    "clinic_accounting",
    "clinic_l10n_id",
}
if not required_dependencies.issubset(depends):
    fail(0, f"missing required ClinicOne dependencies: {sorted(required_dependencies - depends)}")

future_dependencies = {
    "clinic_post_care_followup",
    "clinic_feedback",
    "clinic_reports",
    "clinic_dashboard",
    "clinic_ecommerce",
    "clinic_portal",
    "clinic_marketing",
    "clinic_telemedicine_secure_messaging",
    "clinic_incident_event",
    "clinic_quality",
    "clinic_integration_api",
    "clinic_analytics",
}
if future_dependencies.intersection(depends):
    fail(0, f"future addon dependencies are forbidden: {sorted(future_dependencies.intersection(depends))}")

marker = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_INSURANCE_AUTHORIZATION_BUILD_20260820_V19.0.1.0.1" not in marker:
    fail(0, "authoritative build marker missing")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 25 / insurance policy + pre-authorization + claim-processing identity locked")


# HARD GATE 1 / 14 - Codex governance.
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
for term in ("bounded implementation worker", "architect", "simplifier", "endless retry", "maximum 2"):
    if term not in agents:
        fail(1, f"Codex governance term missing: {term}")
if not any(item.startswith("[FAIL] HARD GATE 1") for item in errors):
    ok(1, "Codex is bounded implementer and cannot redesign/simplify ownership")

if "maximum 1 repeat" not in agents:
    fail(14, "Codex repeated-root-cause limit missing")
else:
    ok(14, "Codex retry limit is maximum two bounded attempts / one repeated root cause")


# Parse Python.
python_files = list(ROOT.rglob("*.py"))
model_files = [path for path in ROOT.glob("models/*.py") if path.name != "__init__.py"]
xml_files = list(ROOT.rglob("*.xml"))
model_source = "\n".join(path.read_text(encoding="utf-8") for path in model_files)

defined_models = set()
technical_fields = {}
constraints = 0
indexes = 0
dangerous_inherit = []
test_methods = 0
class_methods = 0
comment_lines = 0
docstrings = 0
python_errors = []

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

        model_name = None
        inherit_value = None
        explicit_name = False

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

        technical_model = model_name or (
            inherit_value if isinstance(inherit_value, str) else None
        )
        if technical_model:
            field_map = technical_fields.setdefault(technical_model, {})
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
                    continue
                func = stmt.value.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "fields"
                ):
                    continue
                kwargs = {kw.arg: kw.value for kw in stmt.value.keywords if kw.arg}
                for target in stmt.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    computed = "compute" in kwargs
                    stored = False
                    searchable = "search" in kwargs
                    indexed = False
                    if "store" in kwargs:
                        try:
                            stored = bool(ast.literal_eval(kwargs["store"]))
                        except Exception:
                            pass
                    if "index" in kwargs:
                        try:
                            indexed = bool(ast.literal_eval(kwargs["index"]))
                        except Exception:
                            pass
                    field_map[target.id] = {
                        "computed": computed,
                        "store": stored,
                        "search": searchable,
                        "index": indexed,
                    }

        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{node.name}")

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))


# HARD GATE 2 - Existing function/ownership preservation.
for forbidden in (
    '_name = "clinic.insurance.claim"',
    '_name = "clinic.insurance.claim.line"',
    '_name = "clinic.billing.payment"',
    '_name = "account.move"',
    '_name = "account.move.line"',
):
    if forbidden in model_source:
        fail(2, f"frozen upstream ownership duplicated: {forbidden}")

if '_inherit = "clinic.insurance.claim"' not in model_source:
    fail(2, "Billing Claim extension is missing")
if '_inherit = "clinic.insurance.claim.line"' not in model_source:
    fail(2, "Billing Claim Line extension is missing")
preservation_evidence = (ROOT / "docs/CROSS_ADDON_CONTRACT_AUDIT.md").read_text(encoding="utf-8")
if "clinic.billing.payment" not in preservation_evidence or "clinic_billing" not in depends:
    fail(2, "existing Billing settlement ownership is not preserved/documented")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "Billing-owned Claim/Claim Line and settlement ownership preserved; extension-only integration passes")

# The current clinic_queue_room baseline does not import its historical
# appointment/treatment/res_partner insurance bridge files. Addon 25 must own
# these live fields itself so related fields can be set up by the registry.
integration_source = (ROOT / "models/integration_bridge.py").read_text(encoding="utf-8")
for required_bridge in (
    'class ClinicAppointment(models.Model):',
    'class ClinicTreatment(models.Model):',
    'insurance_policy_id = fields.Many2one(',
    'authorization_id = fields.Many2one(',
    'related="authorization_id.state"',
):
    if required_bridge not in integration_source:
        fail(2, f"live Insurance bridge contract missing: {required_bridge}")

if integration_source.count('authorization_id = fields.Many2one(') < 2:
    fail(2, "Appointment and Treatment must each define a live authorization_id field")

if integration_source.count('insurance_policy_id = fields.Many2one(') < 4:
    fail(2, "Partner, Booking, Appointment and Treatment live Policy bridges are incomplete")


# HARD GATE 3 - Enterprise completeness beyond test pass.
required_files = {
    "security/clinic_insurance_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/insurance_plan_views.xml",
    "views/insurance_policy_views.xml",
    "views/eligibility_views.xml",
    "views/authorization_views.xml",
    "views/claim_views.xml",
    "views/integration_views.xml",
    "views/res_config_settings_views.xml",
    "report/authorization_templates.xml",
    "report/authorization_report.xml",
    "report/claim_templates.xml",
    "report/claim_report.xml",
    "tests/test_insurance_enterprise.py",
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
    ok(3, "Policy + Eligibility + Authorization + Claim governance + security + UI + PDFs + crons + tests + docs present")


# HARD GATE 4 - Full structural inventory.
owned_models = {
    "clinic.insurance.plan",
    "clinic.insurance.plan.rule",
    "clinic.insurance.policy",
    "clinic.insurance.eligibility.check",
    "clinic.insurance.authorization",
    "clinic.insurance.authorization.line",
}
missing_models = owned_models - defined_models
if missing_models:
    fail(4, f"owned model inventory incomplete: {sorted(missing_models)}")
else:
    ok(4, "6 owned models plus Billing Claim extensions and 9 upstream model bridges inventoried")


# HARD GATE 5 - Human-friendly source split.
required_model_files = {
    "mixins.py",
    "insurance_plan.py",
    "insurance_policy.py",
    "eligibility.py",
    "authorization.py",
    "claim_bridge.py",
    "integration_bridge.py",
    "settings.py",
}
actual_model_files = {path.name for path in model_files}
if not required_model_files.issubset(actual_model_files):
    fail(5, f"focused model-file structure incomplete: {sorted(required_model_files - actual_model_files)}")
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


# HARD GATE 6 - Professional form design.
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "<chatter",
):
    if token not in all_xml:
        fail(6, f"professional form token missing: {token}")
if not any(item.startswith("[FAIL] HARD GATE 6") for item in errors):
    ok(6, "statusbars, smart buttons, governed header actions, body actions, O2M row buttons and chatter are present")


# HARD GATE 7 - Search/List/Form matrix for all owned models.
view_matrix = {model: {"search": False, "list": False, "form": False} for model in owned_models}
integrated_claim_matrix = {
    "clinic.insurance.claim": {"search": False, "list": False, "form": False},
    "clinic.insurance.claim.line": {"search": False, "list": False, "form": False},
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
        if arch is None:
            continue
        children = list(arch)
        if not children:
            continue
        kind = children[0].tag
        if model in view_matrix and kind in view_matrix[model]:
            view_matrix[model][kind] = True
        if model in integrated_claim_matrix and kind in integrated_claim_matrix[model]:
            integrated_claim_matrix[model][kind] = True

missing_matrix = {
    model: [kind for kind, present in kinds.items() if not present]
    for model, kinds in view_matrix.items()
    if not all(kinds.values())
}
missing_claim_matrix = {
    model: [kind for kind, present in kinds.items() if not present]
    for model, kinds in integrated_claim_matrix.items()
    if not all(kinds.values())
}
if missing_matrix:
    fail(7, f"owned Search/List/Form matrix incomplete: {missing_matrix}")
if missing_claim_matrix:
    fail(7, f"integrated Claim Search/List/Form matrix incomplete: {missing_claim_matrix}")
if not any(item.startswith("[FAIL] HARD GATE 7") for item in errors):
    ok(7, "Search/List/Form complete for 6 owned models and both Billing-owned Claim models")


# HARD GATE 8 - Search views and computed-field searchability.
search_count = 0
search_violations = []
unsearchable = []

for path in xml_files:
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue
        model_node = record.find("./field[@name='model']")
        model = (model_node.text or "").strip() if model_node is not None else ""
        for search in record.findall(".//search"):
            search_count += 1
            if search.attrib:
                search_violations.append(f"{path.relative_to(ROOT)}::<search> attrs={dict(search.attrib)}")
            for child in list(search):
                if child.tag == "group" and child.attrib:
                    search_violations.append(f"{path.relative_to(ROOT)}::<search>/<group> attrs={dict(child.attrib)}")

            for filter_node in search.findall(".//filter[@domain]"):
                domain = filter_node.attrib.get("domain", "")
                for field_name in re.findall(r"\('([^']+)'", domain):
                    base = field_name.split(".", 1)[0]
                    meta = technical_fields.get(model, {}).get(base)
                    if meta and meta["computed"] and not meta["store"] and not meta["search"]:
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{base}:{filter_node.attrib.get('name')}"
                        )

if search_violations:
    fail(8, "ClinicOne Odoo19 search structure violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable fields used in search domains: " + " | ".join(unsearchable))
if search_count < 11:
    fail(8, f"search-view coverage too low: {search_count}")
if not any(item.startswith("[FAIL] HARD GATE 8") for item in errors):
    ok(8, f"{search_count} search views pass search architecture and computed-field searchability gates")


# HARD GATE 9 - List quality.
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 11:
        fail(9, f"enterprise list coverage too low: {list_count}")
    if object_buttons < 45:
        fail(9, f"enterprise object-button coverage too low: {object_buttons}")
    if not any(item.startswith("[FAIL] HARD GATE 9") for item in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise list/action quality")


# HARD GATE 10 - Security cannot be defeated by UI.
security = (ROOT / "security/clinic_insurance_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(r'<record[^>]*model="res.groups">(.*?)</record>', security, flags=re.S)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo 19 privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if len(acl_rows) < 16:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")
if record_rules < 6:
    fail(10, f"company record-rule coverage too small: {record_rules}")

for backend_guard in (
    "insurance_transition",
    "insurance_adjudication",
    "Use Authorization workflow actions",
    "Use Insurance Policy workflow actions",
    "Use Claim workflow/adjudication actions",
    "_insurance_claim_permission",
):
    if backend_guard not in model_source:
        fail(10, f"backend security/workflow guard missing: {backend_guard}")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"4-role hierarchy + {record_rules} company rules + {len(acl_rows)} ACL rows + backend transition guards pass")


# HARD GATE 12 - Odoo 19 code style and contracts.
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 12:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 8:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")

for fragile in (
    "clinic_billing.view_",
    "clinic_patient.view_",
    "clinic_booking.view_",
    "clinic_queue_room.view_",
    "clinic_encounter.view_",
    "clinic_accounting.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile inherited custom upstream view XML ID found: {fragile}")

if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not use stable base.res_config_settings_view_form")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 source contracts pass; models.Constraint={constraints}, models.Index={indexes}")


# HARD GATE 13 - Useful comments.
if comment_lines < 25 or docstrings < 12:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful comments/docstrings pass: comments={comment_lines}, docstrings={docstrings}")


# HARD GATE 15 - Enterprise completeness and runtime test evidence.
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate static readiness from runtime acceptance")
elif test_methods < 78:
    fail(15, f"runtime regression/contract suite too small: {test_methods}")
else:
    ok(15, f"enterprise completeness matrix + {test_methods} runtime tests pass source/static gate")


print("ClinicOne clinic_insurance_authorization Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] owned_models={len(owned_models)} models.Constraint={constraints} models.Index={indexes}")
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

