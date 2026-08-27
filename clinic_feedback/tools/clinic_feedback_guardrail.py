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


# HARD GATE 0 — PROJECT IDENTITY PREFLIGHT.
if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative version must be 19.0.1.0.0")

required_dependencies = {
    "clinic_staff",
    "clinic_doctor",
    "clinic_patient",
    "clinic_treatment_catalog",
    "clinic_booking",
    "clinic_queue_room",
    "clinic_encounter",
    "clinic_post_care_followup",
}
missing_dependencies = sorted(required_dependencies - depends)
if missing_dependencies:
    fail(0, f"required ClinicOne dependencies missing: {missing_dependencies}")

future_dependencies = {
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
future_found = sorted(future_dependencies.intersection(depends))
if future_found:
    fail(0, f"future ClinicOne dependencies are forbidden: {future_found}")

build = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_FEEDBACK_BUILD_20260820_V19.0.1.0.0" not in build:
    fail(0, "authoritative build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
if "Collects patient feedback and satisfaction surveys with escalation workflow." not in preflight:
    fail(0, "official blueprint responsibility is not locked in preflight evidence")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 27 / feedback + satisfaction survey + escalation identity locked")


# HARD GATE 1 / 14 — CODEX GOVERNANCE.
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
for term in (
    "bounded implementation worker",
    "architect",
    "simplifier",
    "endless retry",
    "maximum 2",
):
    if term not in agents:
        fail(1, f"Codex governance term missing: {term}")

if not any(item.startswith("[FAIL] HARD GATE 1") for item in errors):
    ok(1, "Codex is bounded implementation worker, not architect/simplifier")

if "maximum 1 repeat" not in agents:
    fail(14, "Codex same-root-cause retry limit missing")
else:
    ok(14, "Codex retry limit is maximum two bounded attempts / one repeated root cause")


# Parse Python and inventory model contracts.
python_files = list(ROOT.rglob("*.py"))
model_files = [
    path for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py"
]
xml_files = list(ROOT.rglob("*.xml"))
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

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
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
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
                    except Exception:
                        value = None
                    if isinstance(value, str):
                        model_name = value

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


# HARD GATE 2 — EXISTING FUNCTION PRESERVATION.
for forbidden in (
    '_name = "booking.feedback.link"',
    '_name = "booking.booking"',
    '_name = "clinic.queue"',
    '_name = "clinic.encounter"',
    '_name = "clinic.postcare.plan"',
    '_name = "clinic.patient"',
    '_name = "clinic.doctor"',
    '_name = "clinic.staff"',
    '_name = "res.partner"',
):
    if forbidden in model_source:
        fail(2, f"upstream model ownership duplicated: {forbidden}")

for required_extension in (
    '_inherit = "booking.feedback.link"',
    '_inherit = "booking.booking"',
    '_inherit = "clinic.queue"',
    '_inherit = "clinic.encounter"',
    '_inherit = "clinic.postcare.plan"',
    '_inherit = "clinic.patient"',
    '_inherit = "clinic.doctor"',
    '_inherit = "clinic.staff"',
    '_inherit = "res.partner"',
):
    if required_extension not in model_source:
        fail(2, f"required non-owning integration extension missing: {required_extension}")

booking_bridge = (ROOT / "models/booking_bridge.py").read_text(encoding="utf-8")
if "super().action_submit_feedback(" not in booking_bridge:
    fail(2, "Booking-owned feedback lifecycle is not preserved through super()")

audit = (ROOT / "docs/CROSS_ADDON_CONTRACT_AUDIT.md").read_text(encoding="utf-8")
for evidence in (
    "booking.feedback.link",
    "action_submit_feedback()",
    "clinic.queue.action_done()",
):
    if evidence not in audit:
        fail(2, f"cross-addon preservation evidence missing: {evidence}")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "Booking/Queue/Encounter/Post-Care/Patient/Doctor/Staff ownership preserved; additive integration passes")


# HARD GATE 3 — ENTERPRISE COMPLETENESS, NOT JUST TEST PASS.
required_files = {
    "security/clinic_feedback_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/mail_template_data.xml",
    "data/cron_data.xml",
    "views/survey_views.xml",
    "views/request_views.xml",
    "views/feedback_views.xml",
    "views/escalation_views.xml",
    "views/integration_views.xml",
    "views/res_config_settings_views.xml",
    "views/public_feedback_templates.xml",
    "controllers/feedback_portal.py",
    "report/feedback_summary_templates.xml",
    "report/feedback_summary_report.xml",
    "tests/test_feedback_enterprise.py",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/UI_UX_MATRIX.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/SOURCE_STATIC_VALIDATION.md",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise deliverables missing: {missing_files}")
else:
    ok(3, "surveys + requests + public form + canonical responses + NPS + service recovery + automation + security + PDF present")


# HARD GATE 4 — FULL STRUCTURAL INVENTORY.
owned_models = {
    "clinic.feedback.survey",
    "clinic.feedback.question",
    "clinic.feedback.request",
    "clinic.feedback",
    "clinic.feedback.answer",
    "clinic.feedback.escalation",
}
missing_models = owned_models - defined_models
if missing_models:
    fail(4, f"owned model inventory incomplete: {sorted(missing_models)}")
else:
    ok(4, "6 owned Feedback models plus 11 inherited integration models inventoried")


# HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE.
required_model_files = {
    "mixins.py",
    "survey.py",
    "request.py",
    "feedback.py",
    "escalation.py",
    "booking_bridge.py",
    "integration_bridge.py",
    "settings.py",
}
actual_model_files = {path.name for path in model_files}
missing_model_files = sorted(required_model_files - actual_model_files)
if missing_model_files:
    fail(5, f"focused model-file structure incomplete: {missing_model_files}")
else:
    ok(5, f"human-friendly responsibilities split across {len(model_files)} focused model files")


# XML parse and aggregate.
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


# HARD GATE 6 — PROFESSIONAL FORM DESIGN.
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "<chatter",
    "alert alert-danger",
):
    if token not in all_xml:
        fail(6, f"professional form token missing: {token}")

if not any(item.startswith("[FAIL] HARD GATE 6") for item in errors):
    ok(6, "statusbars, smart buttons, body buttons, O2M actions, alerts and chatter are present")


# HARD GATE 7 — UI/UX MATRIX PER OWNED MODEL.
view_matrix = {
    model: {"search": False, "list": False, "form": False}
    for model in owned_models
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
    ok(7, "Search/List/Form complete for all 6 owned Feedback models")


# HARD GATE 8 — SEARCH VIEW + COMPUTED-FIELD SEARCHABILITY.
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
                search_violations.append(
                    f"{path.relative_to(ROOT)}::<search> attrs={dict(search.attrib)}"
                )
            for child in list(search):
                if child.tag == "group" and child.attrib:
                    search_violations.append(
                        f"{path.relative_to(ROOT)}::<search>/<group> attrs={dict(child.attrib)}"
                    )

            for filter_node in search.findall(".//filter[@domain]"):
                domain = filter_node.attrib.get("domain", "")
                try:
                    domain_value = ast.literal_eval(domain)
                except Exception:
                    domain_value = []

                def walk_domain(obj):
                    if (
                        isinstance(obj, tuple)
                        and len(obj) >= 3
                        and isinstance(obj[0], str)
                    ):
                        yield obj[0]
                        return
                    if isinstance(obj, (list, tuple)):
                        for item in obj:
                            yield from walk_domain(item)

                for dotted in walk_domain(domain_value):
                    base = dotted.split(".", 1)[0]
                    meta = technical_fields.get(model, {}).get(base)
                    if meta and meta["computed"] and not meta["store"] and not meta["search"]:
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{base}:{filter_node.attrib.get('name')}"
                        )

if search_violations:
    fail(8, "Odoo19 search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable fields used in search domains: " + " | ".join(unsearchable))
if search_count < 14:
    fail(8, f"search-view coverage too low: {search_count}")

if not any(item.startswith("[FAIL] HARD GATE 8") for item in errors):
    ok(8, f"{search_count} search views pass architecture and computed-field searchability gates")


# HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY.
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 16:
        fail(9, f"enterprise list coverage too low: {list_count}")
    if object_buttons < 50:
        fail(9, f"enterprise object-button coverage too low: {object_buttons}")
    if not any(item.startswith("[FAIL] HARD GATE 9") for item in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise list/action quality")


# HARD GATE 10 — SECURITY CANNOT BE DEFEATED BY UI.
security = (ROOT / "security/clinic_feedback_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(
    r'<record[^>]*model="res.groups">(.*?)</record>',
    security,
    flags=re.S,
)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo19 res.groups.privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if len(acl_rows) < 17:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")
if record_rules < 6:
    fail(10, f"company record-rule coverage too small: {record_rules}")

for backend_guard in (
    "feedback_transition",
    "_feedback_require_group",
    "Use Feedback workflow actions",
    "Use Feedback Request workflow actions",
    "Use Feedback Escalation workflow actions",
    "Submitted Feedback Answers are immutable",
):
    if backend_guard not in model_source:
        fail(10, f"backend security/workflow guard missing: {backend_guard}")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"4-role hierarchy + {record_rules} company rules + {len(acl_rows)} ACL rows + backend guards pass")


# HARD GATE 12 — ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS.
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 9:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 12:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")

for fragile in (
    "clinic_booking.view_",
    "clinic_queue_room.view_",
    "clinic_encounter.view_",
    "clinic_post_care_followup.view_",
    "clinic_patient.view_",
    "clinic_doctor.view_",
    "clinic_staff.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile inherited custom upstream view XML ID found: {fragile}")

if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not inherit stable base.res_config_settings_view_form")

lower_source = model_source.lower()
for implementation_pattern in (
    '"whatsapp"',
    "'whatsapp'",
    "whatsapp_id = fields.",
    "whatsapp_message",
    'self.env["clinic.integration.api"]',
    "self.env['clinic.integration.api']",
):
    if implementation_pattern in lower_source:
        fail(
            12,
            f"unsupported/future delivery implementation found: {implementation_pattern}",
        )

controller = (ROOT / "controllers/feedback_portal.py").read_text(encoding="utf-8")
if "/clinic/feedback/<string:token>" not in controller:
    fail(12, "public token Feedback route missing")
if "csrf=True" not in controller:
    fail(12, "public Feedback POST route does not explicitly keep CSRF protection")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 source contracts pass; models.Constraint={constraints}, models.Index={indexes}")


# HARD GATE 13 — COMMENTS THAT ARE USEFUL.
if comment_lines < 30 or docstrings < 16:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful comments/docstrings pass: comments={comment_lines}, docstrings={docstrings}")


# HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX.
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Source/static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate source/static from runtime acceptance")
elif test_methods < 100:
    fail(15, f"runtime regression/contract suite too small: {test_methods}")
else:
    ok(15, f"enterprise completeness matrix + {test_methods} runtime tests pass source/static gate")


print("ClinicOne clinic_feedback Enterprise Development Guardrail")
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
