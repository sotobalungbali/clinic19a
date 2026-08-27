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

# HARD GATE 0 — Project Identity Preflight.
if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative version must be 19.0.1.0.0")

required_dependencies = {
    "clinic_staff",
    "clinic_patient",
    "clinic_treatment_catalog",
    "clinic_booking",
    "clinic_encounter",
    "clinic_care_plan",
    "clinic_branch",
    "clinic_insurance_authorization",
}
if not required_dependencies.issubset(depends):
    fail(0, f"missing required ClinicOne dependencies: {sorted(required_dependencies - depends)}")

future_dependencies = {
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
    fail(0, f"future addon dependency found: {sorted(future_dependencies.intersection(depends))}")

build = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_POST_CARE_FOLLOWUP_BUILD_20260820_V19.0.1.0.0" not in build:
    fail(0, "authoritative build marker missing")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 26 / post-treatment instructions + automated reminders identity locked")


# HARD GATE 1 / 14 — Codex governance.
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
for term in ("bounded implementation worker", "architect", "simplifier", "endless retry", "maximum 2"):
    if term not in agents:
        fail(1, f"Codex governance term missing: {term}")

if not any(item.startswith("[FAIL] HARD GATE 1") for item in errors):
    ok(1, "Codex is bounded implementer, not architect/simplifier")

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


# HARD GATE 2 — Existing Function Preservation.
for forbidden in (
    '_name = "clinic.staff"',
    '_name = "clinic.patient"',
    '_name = "clinic.encounter"',
    '_name = "booking.booking"',
    '_name = "clinic.care.plan"',
    '_name = "clinic.treatment"',
    '_name = "clinic.insurance.authorization"',
):
    if forbidden in model_source:
        fail(2, f"upstream ownership duplicated: {forbidden}")

for required_extension in (
    '_inherit = "clinic.staff"',
    '_inherit = "clinic.patient"',
    '_inherit = "clinic.encounter"',
    '_inherit = "booking.booking"',
    '_inherit = "clinic.care.plan"',
    '_inherit = "clinic.treatment"',
):
    if required_extension not in model_source:
        fail(2, f"required non-owning integration extension missing: {required_extension}")

if '_name = "clinic.postcare.task"' not in model_source:
    fail(2, "historical clinic_staff technical contract clinic.postcare.task is missing")
if 'assignee_id = fields.Many2one(' not in model_source:
    fail(2, "historical clinic_staff assignee_id contract is missing")

for fake_future in (
    "clinic.feedback",
    "clinic.incident",
    "clinic.telemedicine",
):
    if fake_future in model_source:
        fail(2, f"future-addon model coupling found: {fake_future}")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "Staff/Patient/Encounter/Booking/Care Plan/Treatment ownership preserved and historical task contract supplied")


# HARD GATE 3 — Enterprise completeness.
required_files = {
    "security/clinic_postcare_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/mail_template_data.xml",
    "data/cron_data.xml",
    "views/protocol_views.xml",
    "views/plan_views.xml",
    "views/task_views.xml",
    "views/checkin_views.xml",
    "views/escalation_views.xml",
    "views/integration_views.xml",
    "views/res_config_settings_views.xml",
    "report/postcare_instruction_templates.xml",
    "report/postcare_instruction_report.xml",
    "report/postcare_summary_templates.xml",
    "report/postcare_summary_report.xml",
    "tests/test_postcare_enterprise.py",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/UI_UX_MATRIX.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/SOURCE_STATIC_VALIDATION.md",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise deliverable files missing: {missing_files}")
else:
    ok(3, "Protocols + plans + reminders + check-ins + escalation + automation + security + PDFs + tests + docs present")


# HARD GATE 4 — Full Structural Inventory.
owned_models = {
    "clinic.postcare.protocol",
    "clinic.postcare.protocol.step",
    "clinic.postcare.plan",
    "clinic.postcare.task",
    "clinic.postcare.checkin",
    "clinic.postcare.escalation",
}
missing_models = owned_models - defined_models
if missing_models:
    fail(4, f"owned model inventory incomplete: {sorted(missing_models)}")
else:
    ok(4, "6 owned persistent Post-Care models plus 8 inherited integration models inventoried")


# HARD GATE 5 — Human-friendly coding structure.
required_model_files = {
    "mixins.py",
    "protocol.py",
    "plan.py",
    "task.py",
    "checkin.py",
    "escalation.py",
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


# HARD GATE 6 — Professional Form Design.
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
    ok(6, "statusbars, smart buttons, body actions, O2M row actions, alerts and chatter are present")


# HARD GATE 7 — UI/UX Matrix.
view_matrix = {model: {"search": False, "list": False, "form": False} for model in owned_models}
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
    ok(7, "Search/List/Form complete for all 6 owned Post-Care models")


# HARD GATE 8 — Search view architecture + searchability.
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
                    search_violations.append(
                        f"{path.relative_to(ROOT)}::<search>/<group> attrs={dict(child.attrib)}"
                    )

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
    fail(8, "ClinicOne Odoo19 search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable fields used in search domains: " + " | ".join(unsearchable))
if search_count < 9:
    fail(8, f"search-view coverage too low: {search_count}")

if not any(item.startswith("[FAIL] HARD GATE 8") for item in errors):
    ok(8, f"{search_count} search views pass architecture and computed-field searchability gates")


# HARD GATE 9 — List quality.
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> view found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 12:
        fail(9, f"enterprise list coverage too low: {list_count}")
    if object_buttons < 45:
        fail(9, f"enterprise object-button coverage too low: {object_buttons}")
    if not any(item.startswith("[FAIL] HARD GATE 9") for item in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise list/action quality")


# HARD GATE 10 — Security cannot be defeated by UI.
security = (ROOT / "security/clinic_postcare_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(r'<record[^>]*model="res.groups">(.*?)</record>', security, flags=re.S)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo 19 privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if len(acl_rows) < 18:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")
if record_rules < 6:
    fail(10, f"record-rule coverage too small: {record_rules}")

for backend_guard in (
    "postcare_transition",
    "_postcare_require_group",
    "Use Post-Care Plan workflow actions",
    "Use Post-Care Task workflow actions",
    "Use Check-in workflow actions",
    "Use Escalation workflow actions",
):
    if backend_guard not in model_source:
        fail(10, f"backend workflow/security guard missing: {backend_guard}")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"4-role hierarchy + {record_rules} company rules + {len(acl_rows)} ACL rows + backend guards pass")


# HARD GATE 12 — Odoo 19 / source safety.
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 6:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 10:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")

for fragile in (
    "clinic_staff.view_",
    "clinic_patient.view_",
    "clinic_encounter.view_",
    "clinic_booking.view_",
    "clinic_care_plan.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile custom upstream inherited-view XML ID found: {fragile}")

if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not use stable base.res_config_settings_view_form")

for fake_delivery in ("sms", "whatsapp", "clinic.integration.api"):
    if fake_delivery in model_source.lower():
        fail(12, f"unsupported/future delivery implementation found: {fake_delivery}")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 source contracts pass; models.Constraint={constraints}, models.Index={indexes}")


# HARD GATE 13 — Useful comments.
if comment_lines < 25 or docstrings < 14:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful comments/docstrings pass: comments={comment_lines}, docstrings={docstrings}")


# HARD GATE 15 — Completeness evidence and tests.
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Source/static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate source/static from runtime")
elif test_methods < 80:
    fail(15, f"runtime regression/contract suite too small: {test_methods}")
else:
    ok(15, f"enterprise completeness matrix + {test_methods} runtime tests pass source/static gate")


print("ClinicOne clinic_post_care_followup Enterprise Development Guardrail")
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
