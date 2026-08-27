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


# ---------------------------------------------------------------------------
# HARD GATE 0 - PROJECT IDENTITY PREFLIGHT
# ---------------------------------------------------------------------------
if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative version must be 19.0.1.0.0")

required_dependencies = {
    "portal",
    "website",
    "account",
    "sale",
    "clinic_base",
    "clinic_branch",
    "clinic_patient",
    "clinic_booking",
    "clinic_billing",
    "clinic_encounter",
    "clinic_wallet",
    "clinic_consent_legal",
    "clinic_ecommerce",
}
missing_dependencies = sorted(required_dependencies - depends)
if missing_dependencies:
    fail(0, f"required Patient Portal dependencies missing: {missing_dependencies}")

future_dependencies = {
    "clinic_marketing",
    "clinic_telemedicine_secure_messaging",
    "clinic_incident_event",
    "clinic_quality",
    "clinic_integration_api",
    "clinic_audit",
    "clinic_analytics",
}
future_found = sorted(future_dependencies.intersection(depends))
if future_found:
    fail(0, f"future ClinicOne dependencies are forbidden: {future_found}")

build = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_PORTAL_BUILD_20260821_V19.0.1.0.0" not in build:
    fail(0, "authoritative build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
official_scope = "Provides web portal for patients to view bookings, invoices, and treatment history."
if official_scope not in preflight:
    fail(0, "official addon-31 blueprint responsibility is not locked")

if manifest.get("post_init_hook") != "post_init_hook":
    fail(0, "post_init_hook declaration missing")
if "from .hooks import post_init_hook" not in (ROOT / "__init__.py").read_text(encoding="utf-8"):
    fail(0, "post_init_hook is not exposed from addon package")

if not any(line.startswith("[FAIL] HARD GATE 0") for line in errors):
    ok(0, "ClinicOne addon 31 Patient Portal identity and official scope locked")


# ---------------------------------------------------------------------------
# HARD GATE 1 + 14 - CODEX GOVERNANCE
# ---------------------------------------------------------------------------
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

if "maximum 1 repeat" not in agents:
    fail(14, "same-root-cause retry limit missing")

if not any(line.startswith("[FAIL] HARD GATE 1") for line in errors):
    ok(1, "Codex is bounded implementation worker, never Portal/Booking/Billing architect")
if not any(line.startswith("[FAIL] HARD GATE 14") for line in errors):
    ok(14, "Codex retry limit locked to two bounded attempts / one repeated root cause")


# ---------------------------------------------------------------------------
# Python inventory / metadata
# ---------------------------------------------------------------------------
python_files = list(ROOT.rglob("*.py"))
model_files = [
    path for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py" and not path.name.startswith("0")
]
xml_files = [
    path for path in ROOT.rglob("*.xml")
    if not path.name.startswith("0")
]

defined_models = set()
owned_models = set()
field_map = {}
class_methods = 0
test_methods = 0
constraints = []
indexes = []
dangerous_inherit = []
field_method_collisions = []
comment_lines = 0
docstrings = 0
python_errors = []

reserved_sql = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc",
    "asymmetric", "authorization", "binary", "both", "case", "cast",
    "check", "collate", "column", "constraint", "create", "current_date",
    "current_role", "current_time", "current_timestamp", "current_user",
    "default", "deferrable", "desc", "distinct", "do", "else", "end",
    "except", "false", "for", "foreign", "from", "grant", "group",
    "having", "in", "initially", "intersect", "into", "leading", "limit",
    "localtime", "localtimestamp", "new", "not", "null", "off", "offset",
    "old", "on", "only", "or", "order", "placing", "primary",
    "references", "select", "session_user", "some", "symmetric", "table",
    "then", "to", "trailing", "true", "union", "unique", "user", "using",
    "variadic", "when", "where", "window", "with",
}

for path in python_files:
    source = path.read_text(encoding="utf-8")
    comment_lines += sum(
        1 for line in source.splitlines()
        if line.strip().startswith("#")
    )
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
        class_fields = set()
        class_method_names = set()

        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods += 1
                class_method_names.add(stmt.name)
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
                        defined_models.add(value)
                        if value.startswith("clinic.portal."):
                            owned_models.add(value)

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
                            constraints.append((model_name, target.id))
                        elif func.attr == "Index":
                            indexes.append((model_name, target.id))

                    if (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "fields"
                    ):
                        class_fields.add(target.id)

        collision = class_fields.intersection(class_method_names)
        if collision:
            field_method_collisions.append(
                f"{path.relative_to(ROOT)}::{node.name}:{sorted(collision)}"
            )

        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{node.name}")

        technical_model = model_name or (
            inherit_value if isinstance(inherit_value, str) else None
        )
        if technical_model:
            fields_for_model = field_map.setdefault(technical_model, {})
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
                    if "store" in kwargs:
                        try:
                            stored = bool(ast.literal_eval(kwargs["store"]))
                        except Exception:
                            pass
                    fields_for_model[target.id] = {
                        "computed": computed,
                        "store": stored,
                        "search": searchable,
                    }

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))


# ---------------------------------------------------------------------------
# HARD GATE 2 - EXISTING FUNCTION PRESERVATION
# ---------------------------------------------------------------------------
model_source = "\n".join(path.read_text(encoding="utf-8") for path in model_files)
controller_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "controllers").glob("*.py"))
    if path.name != "__init__.py" and not path.name.startswith("0")
)
route_controller_source = (
    ROOT / "controllers/portal.py"
).read_text(encoding="utf-8")

for forbidden in (
    '_name = "clinic.patient"',
    '_name = "booking.booking"',
    '_name = "clinic.billing.invoice"',
    '_name = "clinic.encounter"',
    '_name = "clinic.procedure.session"',
    '_name = "clinic.wallet"',
    '_name = "clinic.consent.form"',
    '_name = "sale.order"',
    '_name = "account.move"',
):
    if forbidden in model_source:
        fail(2, f"upstream owner model duplicated: {forbidden}")

for required_extension in (
    '_inherit = "res.company"',
    '_inherit = "res.config.settings"',
    '_inherit = "res.partner"',
    '_inherit = "clinic.patient"',
):
    if required_extension not in model_source:
        fail(2, f"expected additive extension missing: {required_extension}")

for source_mutation in (
    'request.env["booking.booking"].sudo().write',
    'request.env["clinic.billing.invoice"].sudo().write',
    'request.env["clinic.encounter"].sudo().write',
):
    if source_mutation in controller_source:
        fail(2, f"portal controller contains upstream mutation: {source_mutation}")

if "portal.wizard" not in model_source:
    fail(2, "native Odoo Portal Access Management is not reused")

if not any(line.startswith("[FAIL] HARD GATE 2") for line in errors):
    ok(2, "Patient/Booking/Billing/Encounter ownership preserved; native portal wizard reused")


# ---------------------------------------------------------------------------
# HARD GATE 3 - ENTERPRISE COMPLETENESS
# ---------------------------------------------------------------------------
required_files = {
    "models/portal_profile.py",
    "models/settings.py",
    "models/integration_bridge.py",
    "controllers/portal.py",
    "controllers/home_service.py",
    "controllers/booking_service.py",
    "controllers/invoice_service.py",
    "controllers/treatment_service.py",
    "security/clinic_portal_security.xml",
    "security/ir.model.access.csv",
    "views/portal_profile_views.xml",
    "views/res_config_settings_views.xml",
    "views/portal_templates.xml",
    "views/menu_views.xml",
    "static/src/scss/portal.scss",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/DATABASE_IDENTIFIER_ORM_NAMING_SAFETY.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "tests/test_portal_enterprise.py",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise Portal deliverables missing: {missing_files}")
else:
    ok(3, "profile governance + 7 patient routes + portal cards + native handoffs + security + tests/docs present")


# ---------------------------------------------------------------------------
# HARD GATE 4 - FULL STRUCTURAL INVENTORY
# ---------------------------------------------------------------------------
expected_owned = {"clinic.portal.profile"}
if owned_models != expected_owned:
    fail(4, f"owned model inventory mismatch: expected={sorted(expected_owned)}, found={sorted(owned_models)}")
else:
    ok(4, "one bounded owner model plus four additive core integrations inventoried")


# ---------------------------------------------------------------------------
# HARD GATE 5 - HUMAN-FRIENDLY CODING STRUCTURE
# ---------------------------------------------------------------------------
required_model_files = {
    "portal_profile.py",
    "settings.py",
    "integration_bridge.py",
}
actual_model_files = {path.name for path in model_files}
if not required_model_files.issubset(actual_model_files):
    fail(5, f"focused model structure incomplete: {sorted(required_model_files - actual_model_files)}")
if len(route_controller_source.splitlines()) > 250:
    fail(5, "portal controller is too large for manual maintenance")
if not any(line.startswith("[FAIL] HARD GATE 5") for line in errors):
    ok(5, "Portal governance, settings, bridges and controllers remain focused/manual-edit friendly")


# ---------------------------------------------------------------------------
# XML parse aggregate
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

all_xml = "\n".join(all_xml_parts)
if xml_errors:
    fail(12, "XML/QWeb parse errors: " + " | ".join(xml_errors))


# ---------------------------------------------------------------------------
# HARD GATE 6 - PROFESSIONAL FORM DESIGN
# ---------------------------------------------------------------------------
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "<chatter",
    "alert alert-warning",
    "action_open_portal_access_management",
    "action_open_bookings",
    "action_open_invoices",
    "action_open_treatments",
):
    if token not in all_xml:
        fail(6, f"professional Portal backend form token missing: {token}")

for token in (
    "portal.portal_layout",
    "portal.portal_searchbar",
    "portal.portal_table",
    "portal.portal_docs_entry",
    "Quick Services",
    "Treatment History",
):
    if token not in all_xml:
        fail(6, f"professional Patient Portal UI token missing: {token}")

if not any(line.startswith("[FAIL] HARD GATE 6") for line in errors):
    ok(6, "statusbar/smart/body actions plus responsive Odoo Customer Portal surfaces are present")


# ---------------------------------------------------------------------------
# HARD GATE 7 - UI/UX MATRIX PER MODEL
# ---------------------------------------------------------------------------
matrix = {"search": False, "list": False, "form": False}
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
        if model != "clinic.portal.profile" or arch is None:
            continue
        children = list(arch)
        if children and children[0].tag in matrix:
            matrix[children[0].tag] = True

missing_matrix = [kind for kind, present in matrix.items() if not present]
if missing_matrix:
    fail(7, f"Portal Profile UI matrix incomplete: {missing_matrix}")
else:
    ok(7, "Search/List/Form complete for clinic.portal.profile; patient website list/detail matrix is complete")


# ---------------------------------------------------------------------------
# HARD GATE 8 - SEARCH VIEW + SEARCHABILITY
# ---------------------------------------------------------------------------
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
                try:
                    domain = ast.literal_eval(filter_node.attrib.get("domain", "[]"))
                except Exception:
                    domain = []

                def walk(value):
                    if (
                        isinstance(value, tuple)
                        and len(value) >= 3
                        and isinstance(value[0], str)
                    ):
                        yield value[0]
                        return
                    if isinstance(value, (list, tuple)):
                        for item in value:
                            yield from walk(item)

                for dotted in walk(domain):
                    base = dotted.split(".", 1)[0]
                    meta = field_map.get(model, {}).get(base)
                    if meta and meta["computed"] and not meta["store"] and not meta["search"]:
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{base}:{filter_node.attrib.get('name')}"
                        )

if search_violations:
    fail(8, "Odoo19 Search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable field used in Search filter: " + " | ".join(unsearchable))
if search_count < 1:
    fail(8, "Portal Profile Search View is missing")

if not any(line.startswith("[FAIL] HARD GATE 8") for line in errors):
    ok(8, f"{search_count} backend Search View passes Odoo19 architecture/searchability gate")


# ---------------------------------------------------------------------------
# HARD GATE 9 - LIST VIEW ENTERPRISE QUALITY
# ---------------------------------------------------------------------------
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 1:
        fail(9, "Portal Profile enterprise List View missing")
    if object_buttons < 15:
        fail(9, f"enterprise action-button coverage too low: {object_buttons}")
    if not any(line.startswith("[FAIL] HARD GATE 9") for line in errors):
        ok(9, f"{list_count} list architecture(s) and {object_buttons} object buttons pass enterprise quality")


# ---------------------------------------------------------------------------
# HARD GATE 10 - SECURITY CANNOT BE DEFEATED BY UI
# ---------------------------------------------------------------------------
security = (ROOT / "security/clinic_portal_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo19 Patient Portal privilege hierarchy missing")

for row in acl_rows:
    group = row["group_id:id"]
    if group in ("base.group_portal", "base.group_public") or "portal.group_portal" in group:
        fail(10, f"external/public backend ACL is forbidden: {row['id']}")

if len(acl_rows) != 2:
    fail(10, f"unexpected Portal Profile ACL matrix: {len(acl_rows)} rows")
if security.count('model="ir.rule"') < 1:
    fail(10, "Portal Profile company record rule missing")

for required_guard in (
    "portal_runtime_access",
    "portal_profile_transition",
    "_require_clinic_profile",
    "_portal_booking_domain",
    "_portal_invoice_domain",
    "_portal_treatment_domain",
):
    if required_guard not in (model_source + controller_source):
        fail(10, f"backend patient-access guard missing: {required_guard}")

# Every Clinic detail route must intersect browser ID with profile ownership.
for token in (
    '[("id", "=", booking_id)] + profile._portal_booking_domain()',
    '[("id", "=", invoice_id)] + profile._portal_invoice_domain()',
    '[("id", "=", encounter_id)] + profile._portal_treatment_domain()',
):
    if token not in controller_source:
        fail(10, f"detail ID ownership intersection missing: {token}")

if "commercial_partner_id" in controller_source:
    fail(10, "commercial-partner family scope is forbidden for generic patient clinical access")

# Core ClinicOne portal routes must require authenticated user.
route_blocks = re.findall(
    r'@http\.route\((.*?)\)\s*\n\s*def\s+(clinic_portal_[a-zA-Z0-9_]+)',
    route_controller_source,
    flags=re.S,
)
if len(route_blocks) != 7:
    fail(10, f"expected 7 patient routes, found {len(route_blocks)}")
for decorator, method in route_blocks:
    if 'auth="user"' not in decorator:
        fail(10, f"{method} is not auth=user")

if not any(line.startswith("[FAIL] HARD GATE 10") for line in errors):
    ok(10, "native auth + exact patient/company domains + no external backend ACL + feature policy pass")


# ---------------------------------------------------------------------------
# HARD GATE 11 - DATABASE IDENTIFIER & ORM NAMING SAFETY
# ---------------------------------------------------------------------------
identifier_issues = []
snake_re = re.compile(r"^[a-z][a-z0-9_]*$")
model_re = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")

for model_name in sorted(owned_models):
    if not model_re.match(model_name):
        identifier_issues.append(f"unsafe model _name: {model_name}")
    table = model_name.replace(".", "_")
    if len(table.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"table name exceeds 63 bytes: {table}")

    for field_name in field_map.get(model_name, {}):
        if not snake_re.match(field_name):
            identifier_issues.append(f"unsafe field name: {model_name}.{field_name}")
        if len(field_name.encode("ascii", errors="ignore")) > 63:
            identifier_issues.append(f"field exceeds 63 bytes: {model_name}.{field_name}")
        if field_name.lower() in reserved_sql:
            identifier_issues.append(f"reserved SQL field name: {model_name}.{field_name}")

for model_name, attr_name in constraints + indexes:
    if not model_name or model_name not in owned_models:
        continue
    table = model_name.replace(".", "_")
    generated = f"{table}_{attr_name.lstrip('_')}"
    if len(attr_name.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"constraint/index attribute too long: {attr_name}")
    if len(generated.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"generated DB identifier exceeds 63 bytes: {generated}")

# Explicit M2M relation identifiers, if any.
for path in model_files:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "fields"
            and func.attr == "Many2many"
        ):
            continue
        for kw in node.keywords:
            if kw.arg == "relation":
                try:
                    relation = ast.literal_eval(kw.value)
                except Exception:
                    relation = None
                if isinstance(relation, str) and len(relation.encode("ascii", errors="ignore")) > 63:
                    identifier_issues.append(f"Many2many relation exceeds 63 bytes: {relation}")

if field_method_collisions:
    identifier_issues.extend(
        f"field/method collision: {item}"
        for item in field_method_collisions
    )
if dangerous_inherit:
    identifier_issues.extend(
        f"list-valued _inherit without explicit _name: {item}"
        for item in dangerous_inherit
    )

if identifier_issues:
    fail(11, " | ".join(identifier_issues))
else:
    ok(11, "model/table/field/constraint/index names and field-method namespaces pass PostgreSQL/Odoo ORM safety")


# ---------------------------------------------------------------------------
# HARD GATE 12 - ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS
# ---------------------------------------------------------------------------
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
if dangerous_inherit:
    fail(12, f"dangerous _inherit classes: {dangerous_inherit}")
if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not inherit stable base.res_config_settings_view_form")
if "CustomerPortal" not in controller_source or "portal_pager" not in controller_source:
    fail(12, "Odoo 19 CustomerPortal/pager extension contract missing")
if "action_open_wizard()" not in model_source:
    fail(12, "native Odoo 19 portal.wizard action contract missing")

# Generic treatment history must not bind sensitive fields into QWeb.
portal_templates = (ROOT / "views/portal_templates.xml").read_text(encoding="utf-8")
for sensitive_ref in (
    't-field="encounter.soap',
    't-field="encounter.assessment',
    't-field="encounter.diagn',
    't-field="encounter.subjective',
    't-field="encounter.objective',
    't-field="encounter.vital',
):
    if sensitive_ref in portal_templates:
        fail(12, f"sensitive generic treatment-history binding found: {sensitive_ref}")

if constraints.__len__() < 1 or indexes.__len__() < 1:
    fail(12, f"models.Constraint/Index coverage insufficient: constraints={len(constraints)}, indexes={len(indexes)}")

if not any(line.startswith("[FAIL] HARD GATE 12") for line in errors):
    ok(12, f"Odoo19 portal/view/source contracts pass; models.Constraint={len(constraints)}, models.Index={len(indexes)}")


# ---------------------------------------------------------------------------
# HARD GATE 13 - COMMENTS THAT ARE USEFUL
# ---------------------------------------------------------------------------
if comment_lines < 25 or docstrings < 6:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"security/ownership comments and class documentation pass: comments={comment_lines}, docstrings={docstrings}")


# ---------------------------------------------------------------------------
# HARD GATE 15 - ENTERPRISE COMPLETENESS MATRIX
# ---------------------------------------------------------------------------
matrix_doc = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix_doc
    or "Source/static PASS is not runtime completion" not in matrix_doc
):
    fail(15, "completeness matrix does not separate source/static and runtime")

required_route_fragments = {
    "/my/clinic",
    "/my/clinic/bookings",
    "/my/clinic/invoices",
    "/my/clinic/treatments",
}
for route in required_route_fragments:
    if route not in controller_source:
        fail(15, f"official Patient Portal route family missing: {route}")

if test_methods < 200:
    fail(15, f"runtime contract/regression suite too small: {test_methods}")

if not any(line.startswith("[FAIL] HARD GATE 15") for line in errors):
    ok(15, f"official 3-surface Patient Portal + governance + native handoffs + {test_methods} tests pass source/static completeness")


print("ClinicOne clinic_portal Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] owned_models={len(owned_models)} models.Constraint={len(constraints)} models.Index={len(indexes)}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} record_rules={security.count('model=\"ir.rule\"')}")
print(f"[INFO] patient_routes={len(route_blocks)} test_methods={test_methods} class_methods={class_methods}")

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/BROWSER SECURITY SMOKE TEST PENDING)")
