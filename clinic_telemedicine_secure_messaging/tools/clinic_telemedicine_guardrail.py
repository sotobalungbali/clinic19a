from pathlib import Path
import ast
import csv
import re
import sys
from collections import defaultdict
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
if manifest.get("version") != "19.0.1.0.1":
    fail(0, "authoritative addon-33 repair version must be 19.0.1.0.1")

required_dependencies = {
    "portal",
    "website",
    "clinic_base",
    "clinic_branch",
    "clinic_staff",
    "clinic_doctor",
    "clinic_patient",
    "clinic_booking",
    "clinic_queue_room",
    "clinic_consent_legal",
    "clinic_encounter",
    "clinic_portal",
}
missing_dependencies = sorted(required_dependencies - depends)
if missing_dependencies:
    fail(0, f"required Telemedicine dependencies missing: {missing_dependencies}")

future_dependencies = {
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
if (
    "CLINIC_TELEMEDICINE_SECURE_MESSAGING_BUILD_20260821_V19.0.1.0.1"
    not in build
):
    fail(0, "authoritative addon-33 build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
official_scope = "Teleconsultation and secure doctor-patient chat system with file sharing."
if official_scope not in preflight:
    fail(0, "official addon-33 blueprint responsibility is not locked")

if not any(line.startswith("[FAIL] HARD GATE 0") for line in errors):
    ok(0, "ClinicOne addon 33 Teleconsultation + Secure Messaging identity locked")


# ---------------------------------------------------------------------------
# HARD GATE 1 / 14 - CODEX GOVERNANCE
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
    ok(1, "Codex is bounded worker, not Patient/Doctor/Portal/provider/encryption architect")
if not any(line.startswith("[FAIL] HARD GATE 14") for line in errors):
    ok(14, "Codex retry limit locked to two bounded attempts / one repeated root cause")


# ---------------------------------------------------------------------------
# Python / ORM inventory
# ---------------------------------------------------------------------------
python_files = [
    path for path in ROOT.rglob("*.py")
    if not path.name.startswith("0")
]
model_files = [
    path for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py" and not path.name.startswith("0")
]
controller_files = [
    path for path in ROOT.glob("controllers/*.py")
    if path.name != "__init__.py" and not path.name.startswith("0")
]
xml_files = [
    path for path in ROOT.rglob("*.xml")
    if not path.name.startswith("0")
]

owned_expected = {
    "clinic.telemedicine.session",
    "clinic.telemedicine.thread",
    "clinic.telemedicine.message",
    "clinic.telemedicine.attachment",
}

defined_models = set()
owned_models = set()
field_map = defaultdict(dict)
method_map = defaultdict(set)
parent_map = defaultdict(set)
constraints = []
indexes = []
dangerous_inherit = []
field_method_collisions = []
env_proxy_isinstance = []
class_load_symbol_issues = []
python_errors = []
test_methods = 0
class_methods = 0
comment_lines = 0
docstrings = 0

required_load_symbols = {"api", "fields", "models", "_"}


def root_name(expr):
    current = expr
    while isinstance(current, (ast.Attribute, ast.Call, ast.Subscript)):
        if isinstance(current, ast.Attribute):
            current = current.value
        elif isinstance(current, ast.Call):
            current = current.func
        else:
            current = current.value
    return current.id if isinstance(current, ast.Name) else None


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

    imported_names = set()
    for top in tree.body:
        if isinstance(top, ast.Import):
            imported_names.update(
                alias.asname or alias.name.split(".")[0]
                for alias in top.names
            )
        elif isinstance(top, ast.ImportFrom):
            imported_names.update(
                alias.asname or alias.name
                for alias in top.names
            )
        elif isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            imported_names.add(top.name)
        elif isinstance(top, ast.Assign):
            imported_names.update(
                target.id
                for target in top.targets
                if isinstance(target, ast.Name)
            )

    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if ast.get_docstring(cls):
            docstrings += 1

        # Class-load symbol/import audit. This catches the exact defect class
        # that broke clinic_marketing 19.0.1.0.0.
        for expr in list(cls.bases) + list(cls.decorator_list):
            root = root_name(expr)
            if root in required_load_symbols and root not in imported_names:
                class_load_symbol_issues.append(
                    f"{path.relative_to(ROOT)}:{cls.lineno}:"
                    f"{cls.name} requires missing `{root}` import"
                )

        model_name = None
        inherit_value = None
        explicit_name = False
        class_fields = set()
        class_method_names = set()

        for stmt in cls.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods += 1
                class_method_names.add(stmt.name)
                method_map_key = None

                for deco in stmt.decorator_list:
                    root = root_name(deco)
                    if root in required_load_symbols and root not in imported_names:
                        class_load_symbol_issues.append(
                            f"{path.relative_to(ROOT)}:{stmt.lineno}:"
                            f"{cls.name}.{stmt.name} decorator requires "
                            f"missing `{root}` import"
                        )

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
                        if value in owned_expected:
                            owned_models.add(value)

                elif target.id == "_inherit":
                    try:
                        inherit_value = ast.literal_eval(stmt.value)
                    except Exception:
                        pass

                if isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    load_root = root_name(func)
                    if (
                        load_root in required_load_symbols
                        and load_root not in imported_names
                    ):
                        class_load_symbol_issues.append(
                            f"{path.relative_to(ROOT)}:{stmt.lineno}:"
                            f"class assignment requires missing `{load_root}` import"
                        )

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

        technical_model = model_name or (
            inherit_value if isinstance(inherit_value, str) else None
        )

        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{cls.name}")

        if (
            technical_model
            and isinstance(inherit_value, str)
            and model_name
            and inherit_value != model_name
        ):
            parent_map[technical_model].add(inherit_value)

        if technical_model:
            method_map[technical_model].update(class_method_names)
            for stmt in cls.body:
                if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
                    continue
                func = stmt.value.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "fields"
                ):
                    continue

                comodel = None
                if stmt.value.args:
                    try:
                        first = ast.literal_eval(stmt.value.args[0])
                    except Exception:
                        first = None
                    if (
                        func.attr in ("Many2one", "One2many", "Many2many")
                        and isinstance(first, str)
                    ):
                        comodel = first

                kwargs = {kw.arg: kw.value for kw in stmt.value.keywords if kw.arg}
                for kw in stmt.value.keywords:
                    if kw.arg == "comodel_name":
                        try:
                            value = ast.literal_eval(kw.value)
                        except Exception:
                            value = None
                        if isinstance(value, str):
                            comodel = value

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

                    field_map[technical_model][target.id] = {
                        "type": func.attr,
                        "comodel": comodel,
                        "computed": computed,
                        "store": stored,
                        "search": searchable,
                    }

        collision = class_fields.intersection(class_method_names)
        if collision:
            field_method_collisions.append(
                f"{path.relative_to(ROOT)}::{cls.name}:{sorted(collision)}"
            )

    # Detect Odoo environment recordset aliases incorrectly used as Python
    # classes in isinstance(), the root cause class seen previously in ClinicOne.
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        proxy_names = set()
        for node in ast.walk(function):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            value = node.value
            if (
                isinstance(value, ast.Subscript)
                and isinstance(value.value, ast.Attribute)
                and isinstance(value.value.value, ast.Name)
                and value.value.value.id in {"self", "request"}
                and value.value.attr == "env"
            ):
                proxy_names.add(node.targets[0].id)

        for node in ast.walk(function):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "isinstance"
                and len(node.args) >= 2
            ):
                continue
            second = node.args[1]
            if isinstance(second, ast.Name) and second.id in proxy_names:
                env_proxy_isinstance.append(
                    f"{path.relative_to(ROOT)}:{function.name}:{node.lineno}:"
                    f"{second.id}"
                )

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))
if class_load_symbol_issues:
    fail(
        12,
        "Python class-load symbol/import errors: "
        + " | ".join(class_load_symbol_issues),
    )


# ---------------------------------------------------------------------------
# HARD GATE 2 - EXISTING FUNCTION PRESERVATION
# ---------------------------------------------------------------------------
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

for forbidden in (
    '_name = "clinic.staff"',
    '_name = "clinic.doctor"',
    '_name = "clinic.patient"',
    '_name = "clinic.appointment"',
    '_name = "booking.booking"',
    '_name = "clinic.queue"',
    '_name = "clinic.encounter"',
    '_name = "clinic.consent.form"',
    '_name = "clinic.portal.profile"',
):
    if forbidden in model_source:
        fail(2, f"upstream owner model duplicated: {forbidden}")

required_extensions = (
    '_inherit = "clinic.staff"',
    '_inherit = "clinic.doctor"',
    '_inherit = "clinic.patient"',
    '_inherit = "clinic.appointment"',
    '_inherit = "booking.booking"',
    '_inherit = "clinic.queue"',
    '_inherit = "clinic.encounter"',
    '_inherit = "clinic.portal.profile"',
    '_inherit = "res.partner"',
)
for extension in required_extensions:
    if extension not in model_source:
        fail(2, f"required additive integration missing: {extension}")

for mutation in (
    'action_done =',
    'action_confirm =',
    'def action_done(',
    'def action_confirm(',
    'def action_check_in(',
):
    if mutation in (ROOT / "models/integration_bridge.py").read_text(encoding="utf-8"):
        fail(2, f"upstream lifecycle override/mutation detected: {mutation}")

if "super()._compute_counts()" not in (ROOT / "models/integration_bridge.py").read_text(encoding="utf-8"):
    fail(2, "Staff historical counter integration does not preserve super() counters")

if 'self.env["clinic.telemedicine.thread"]' not in model_source:
    fail(2, "historical Staff clinic.telemedicine.thread contract not supplied")

if not any(line.startswith("[FAIL] HARD GATE 2") for line in errors):
    ok(2, "Staff/Doctor/Patient/Booking/Appointment/Queue/Encounter/Portal ownership preserved")


# ---------------------------------------------------------------------------
# HARD GATE 3 - ENTERPRISE COMPLETENESS
# ---------------------------------------------------------------------------
required_files = {
    "models/session.py",
    "models/session_workflow.py",
    "models/session_navigation.py",
    "models/thread.py",
    "models/message.py",
    "models/attachment.py",
    "models/settings.py",
    "models/portal_bridge.py",
    "models/integration_bridge.py",
    "controllers/portal.py",
    "security/clinic_telemedicine_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "views/telemedicine_session_views.xml",
    "views/telemedicine_thread_views.xml",
    "views/telemedicine_message_views.xml",
    "views/telemedicine_attachment_views.xml",
    "views/portal_access_views.xml",
    "views/res_config_settings_views.xml",
    "views/integration_views.xml",
    "views/portal_templates.xml",
    "views/menu_views.xml",
    "static/src/img/video.svg",
    "static/src/img/chat.svg",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/LATEST_BASELINE_AUDIT.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/SECURITY_MODEL.md",
    "docs/DATABASE_IDENTIFIER_ORM_NAMING_SAFETY.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/RUNTIME_REPAIR_20260821_01.md",
    "tests/test_telemedicine_enterprise.py",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise Telemedicine deliverables missing: {missing_files}")
else:
    ok(3, "Session + secure Thread/Message/File + Portal + source integration + security/tests/docs present")


# ---------------------------------------------------------------------------
# HARD GATE 4 - FULL STRUCTURAL INVENTORY
# ---------------------------------------------------------------------------
if owned_models != owned_expected:
    fail(
        4,
        f"owned model mismatch: expected={sorted(owned_expected)}, "
        f"found={sorted(owned_models)}",
    )
else:
    ok(4, "4 owned models plus bounded upstream integration layer inventoried")


# ---------------------------------------------------------------------------
# HARD GATE 5 - HUMAN-FRIENDLY CODING STRUCTURE
# ---------------------------------------------------------------------------
largest_model = max(
    (
        len(path.read_text(encoding="utf-8").splitlines()),
        path.name,
    )
    for path in model_files
)
largest_controller = max(
    (
        len(path.read_text(encoding="utf-8").splitlines()),
        path.name,
    )
    for path in controller_files
)
if largest_model[0] > 550:
    fail(5, f"model file exceeds maintenance threshold: {largest_model}")
if largest_controller[0] > 600:
    fail(5, f"controller file exceeds maintenance threshold: {largest_controller}")
if len(model_files) < 9:
    fail(5, f"responsibility split too coarse: model_files={len(model_files)}")

if not any(line.startswith("[FAIL] HARD GATE 5") for line in errors):
    ok(
        5,
        f"human-friendly split passes; largest model={largest_model[1]}:{largest_model[0]} "
        f"lines, controller={largest_controller[0]} lines",
    )


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
    "alert alert-info",
    "action_join_meeting",
    "action_open_thread",
    "action_open_messages",
    "action_download",
):
    if token not in all_xml:
        fail(6, f"professional Telemedicine UI token missing: {token}")

for token in (
    "view_telemedicine_session_kanban",
    "view_telemedicine_thread_kanban",
    "portal_telemedicine_sessions",
    "portal_secure_thread",
):
    if token not in all_xml:
        fail(6, f"enterprise Telemedicine UX surface missing: {token}")

if not any(line.startswith("[FAIL] HARD GATE 6") for line in errors):
    ok(6, "statusbars, smart/body/O2M actions, Kanban and Patient Portal UX present")


# ---------------------------------------------------------------------------
# HARD GATE 7 - UI/UX MATRIX PER OWNED MODEL
# ---------------------------------------------------------------------------
view_matrix = {
    model: {"search": False, "list": False, "form": False}
    for model in owned_expected
}

for path in xml_files:
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue
        model_node = record.find("./field[@name='model']")
        arch_node = record.find("./field[@name='arch']")
        if model_node is None or arch_node is None:
            continue
        model = (model_node.text or "").strip()
        if model not in view_matrix:
            continue
        children = list(arch_node)
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
    ok(7, "Search/List/Form complete for all 4 owned Telemedicine models")


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
                    if (
                        meta
                        and meta["computed"]
                        and not meta["store"]
                        and not meta["search"]
                    ):
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{base}:"
                            f"{filter_node.attrib.get('name')}"
                        )

if search_violations:
    fail(8, "Odoo19 Search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "non-searchable computed field used in Search domain: " + " | ".join(unsearchable))
if search_count < 5:
    fail(8, f"Search coverage too low: {search_count}")

if not any(line.startswith("[FAIL] HARD GATE 8") for line in errors):
    ok(8, f"{search_count} Search Views pass Odoo19 search architecture/searchability")


# ---------------------------------------------------------------------------
# HARD GATE 9 - LIST VIEW ENTERPRISE QUALITY
# ---------------------------------------------------------------------------
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 8:
        fail(9, f"enterprise list coverage too low: {list_count}")
    if object_buttons < 55:
        fail(9, f"enterprise object-button coverage too low: {object_buttons}")

    if not any(line.startswith("[FAIL] HARD GATE 9") for line in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise quality")


# ---------------------------------------------------------------------------
# HARD GATE 10 - SECURITY CANNOT BE DEFEATED BY UI
# ---------------------------------------------------------------------------
security = (ROOT / "security/clinic_telemedicine_security.xml").read_text(encoding="utf-8")
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
    fail(10, "Odoo19 Telemedicine privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if record_rules != 4:
    fail(10, f"expected exactly 4 company rules, found {record_rules}")
if len(acl_rows) != 12:
    fail(10, f"expected 12 ACL rows, found {len(acl_rows)}")

for row in acl_rows:
    if row["group_id:id"] in {"base.group_public", "base.group_portal"}:
        fail(10, f"Portal/Public backend ACL is forbidden: {row['id']}")

portal_source = (ROOT / "controllers/portal.py").read_text(encoding="utf-8")
portal_bridge = (ROOT / "models/portal_bridge.py").read_text(encoding="utf-8")
attachment_source = (ROOT / "models/attachment.py").read_text(encoding="utf-8")
session_sources = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "models").glob("session*.py"))
)

for token in (
    "allow_telemedicine_access",
    "allow_secure_messaging",
    "_clinic_profile(allow_create=False)",
    "_portal_telemedicine_session_domain",
    "_portal_secure_thread_domain",
):
    if token not in portal_source + portal_bridge:
        fail(10, f"Patient Portal authorization control missing: {token}")

for token in (
    '[("id", "=", session_id)]',
    "profile._portal_telemedicine_session_domain()",
    '[("id", "=", thread_id)]',
    "profile._portal_secure_thread_domain()",
):
    if token not in portal_source:
        fail(10, f"browser ID exact-owner intersection missing: {token}")

if "commercial_partner_id" in portal_source:
    fail(10, "commercial-partner family scope is forbidden for clinical communication")

# Feature grants must be security-first.
profile_model_source = (ROOT / "models/portal_bridge.py").read_text(encoding="utf-8")
for field_name in ("allow_telemedicine_access", "allow_secure_messaging"):
    segment = profile_model_source.split(field_name, 1)[1].split(")", 1)[0]
    if "default=False" not in segment:
        fail(10, f"{field_name} must default False")

# No generic chatter/email copy of secure message body. Documentation may
# mention mail.thread to explain why it is NOT used, therefore check executable
# inheritance/API patterns instead of a raw prose substring.
message_source = (ROOT / "models/message.py").read_text(encoding="utf-8")
for forbidden in (
    '_inherit = "mail.thread"',
    "_inherit = ['mail.thread'",
    '_inherit = ["mail.thread"',
    "message_post(",
    'self.env["mail.mail"]',
    'self.env["mailing.mailing"]',
):
    if forbidden in message_source:
        fail(
            10,
            f"Secure Message content leaks into generic notification surface: {forbidden}",
        )

# Secure file controls.
for token in (
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
    "clinic_telemedicine_max_file_mb",
    "hashlib.sha256",
    'raw.startswith(b"%PDF-")',
    'raw.startswith(b"\\\\xff\\\\xd8\\\\xff")',
    'raw.startswith(b"\\\\x89PNG\\\\r\\\\n\\\\x1a\\\\n")',
):
    if token not in attachment_source:
        fail(10, f"secure Attachment control missing: {token}")

for token in (
    "Cache-Control",
    "no-store",
    "X-Content-Type-Options",
    "nosniff",
):
    if token not in portal_source:
        fail(10, f"secure download response control missing: {token}")

# Meeting URL and join evidence.
for token in (
    'parsed.scheme.lower() != "https"',
    "_patient_join_allowed",
    "telemedicine_patient_join",
    "_provision_meeting_via_provider",
):
    if token not in session_sources:
        fail(10, f"Teleconsultation URL/join/provider security control missing: {token}")

if not any(line.startswith("[FAIL] HARD GATE 10") for line in errors):
    ok(10, "explicit grants + exact patient/company domains + secure files + HTTPS join + no Portal ACL pass")


# ---------------------------------------------------------------------------
# HARD GATE 11 - DATABASE IDENTIFIER & ORM NAMING SAFETY
# ---------------------------------------------------------------------------
identifier_issues = []
snake_re = re.compile(r"^[a-z][a-z0-9_]*$")
model_re = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
reserved_sql = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc",
    "authorization", "binary", "both", "case", "cast", "check", "column",
    "constraint", "create", "current_date", "current_role", "current_time",
    "current_timestamp", "current_user", "default", "deferrable", "desc",
    "distinct", "do", "else", "end", "except", "false", "for", "foreign",
    "from", "grant", "group", "having", "in", "initially", "intersect",
    "into", "leading", "limit", "new", "not", "null", "off", "offset",
    "old", "on", "only", "or", "order", "primary", "references", "select",
    "session_user", "some", "table", "then", "to", "trailing", "true",
    "union", "unique", "user", "using", "when", "where", "window", "with",
}

for model_name in sorted(owned_expected):
    if not model_re.match(model_name):
        identifier_issues.append(f"unsafe model name: {model_name}")
    table = model_name.replace(".", "_")
    if len(table.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"SQL table identifier exceeds 63 bytes: {table}")

    for field_name in field_map.get(model_name, {}):
        if not snake_re.match(field_name):
            identifier_issues.append(f"unsafe field: {model_name}.{field_name}")
        if len(field_name.encode("ascii", errors="ignore")) > 63:
            identifier_issues.append(f"field exceeds 63 bytes: {model_name}.{field_name}")
        if field_name.lower() in reserved_sql:
            identifier_issues.append(f"reserved SQL field: {model_name}.{field_name}")

for model_name, attr_name in constraints + indexes:
    if model_name not in owned_expected:
        continue
    table = model_name.replace(".", "_")
    generated = f"{table}_{attr_name.lstrip('_')}"
    if len(attr_name.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"Constraint/Index attribute too long: {attr_name}")
    if len(generated.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"generated DB identifier exceeds 63 bytes: {generated}")

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
if env_proxy_isinstance:
    identifier_issues.extend(
        f"env-model proxy used as isinstance type: {item}"
        for item in env_proxy_isinstance
    )

if identifier_issues:
    fail(11, " | ".join(identifier_issues))
else:
    ok(11, "4 owner namespaces/fields/constraints/indexes and ORM method namespaces pass safety")


# ---------------------------------------------------------------------------
# HARD GATE 12 - ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS
# ---------------------------------------------------------------------------
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not inherit stable base.res_config_settings_view_form")
if "<tree" in all_xml:
    fail(12, "legacy tree view found")
if class_load_symbol_issues:
    fail(12, "class-load import/symbol resolution failed")

# Runtime-repair rule:
# - Booking's custom view resolved successfully earlier in the same failed
#   installation attempt and remains an audited source-owner integration.
# - Patient smart navigation MUST use Odoo's stable native Contact form because
#   clinic_patient.view_clinic_patient_form is absent from the installed DB.
integration_xml = (ROOT / "views/integration_views.xml").read_text(encoding="utf-8")
allowed_inherit_refs = {
    "clinic_booking.view_booking_booking_form",
    "base.view_partner_form",
}
inherit_refs = set(
    re.findall(r'<field name="inherit_id" ref="([^"]+)"', integration_xml)
)
unexpected = sorted(inherit_refs - allowed_inherit_refs)
if unexpected:
    fail(12, f"unexpected fragile integration inherit IDs: {unexpected}")

if 'ref="clinic_patient.view_clinic_patient_form"' in integration_xml:
    fail(
        12,
        "runtime-failed clinic_patient.view_clinic_patient_form dependency "
        "must not re-enter addon 33",
    )

if "base.view_partner_form" not in integration_xml:
    fail(
        12,
        "stable native Patient Contact integration via base.view_partner_form is missing",
    )

if len(constraints) < 4 or len(indexes) < 4:
    fail(
        12,
        f"models.Constraint/Index coverage insufficient: "
        f"constraints={len(constraints)}, indexes={len(indexes)}",
    )

# The term Secure Messaging must not be promoted as E2E encryption.
for path in [ROOT / "README.md"] + list((ROOT / "views").glob("*.xml")):
    content = path.read_text(encoding="utf-8").lower()
    if "end-to-end encrypted" in content or "e2e encrypted" in content:
        fail(12, f"unsupported encryption claim found: {path.relative_to(ROOT)}")

if not any(line.startswith("[FAIL] HARD GATE 12") for line in errors):
    ok(
        12,
        f"Odoo19 views/source/class-load contracts pass; "
        f"models.Constraint={len(constraints)}, models.Index={len(indexes)}",
    )


# ---------------------------------------------------------------------------
# HARD GATE 13 - COMMENTS THAT ARE USEFUL
# ---------------------------------------------------------------------------
if comment_lines < 35 or docstrings < 12:
    fail(
        13,
        f"comment/docstring coverage too low: "
        f"comments={comment_lines}, docstrings={docstrings}",
    )
else:
    ok(
        13,
        f"security/ownership comments and class docs pass: "
        f"comments={comment_lines}, docstrings={docstrings}",
    )


# ---------------------------------------------------------------------------
# HARD GATE 15 - ENTERPRISE COMPLETENESS MATRIX
# ---------------------------------------------------------------------------
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Source/static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate static and runtime status")

if test_methods < 450:
    fail(15, f"runtime contract/regression suite too small: {test_methods}")

for capability in (
    "Teleconsultation lifecycle",
    "Immutable Secure Message",
    "Controlled attachment download",
    "Exact-patient Portal Session domain",
    "Historical Staff Thread contract",
    "End-to-end encryption claim | ABSENT",
):
    if capability not in matrix:
        fail(15, f"enterprise completeness capability missing: {capability}")

if not any(line.startswith("[FAIL] HARD GATE 15") for line in errors):
    ok(
        15,
        f"Teleconsultation + exact-patient messaging/files + source integrations "
        f"+ {test_methods} tests pass source/static completeness",
    )


print("ClinicOne clinic_telemedicine_secure_messaging Enterprise Development Guardrail")
print(
    f"[INFO] model_files={len(model_files)} "
    f"controller_files={len(controller_files)} "
    f"python_files={len(python_files)} xml_files={len(xml_files)}"
)
print(
    f"[INFO] owned_models={len(owned_expected)} "
    f"models.Constraint={len(constraints)} models.Index={len(indexes)}"
)
print(
    f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} "
    f"record_rules={record_rules}"
)
print(
    f"[INFO] test_methods={test_methods} class_methods={class_methods} "
    f"comments={comment_lines} docstrings={docstrings}"
)

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print(
    "RESULT: PASS (SOURCE/STATIC ONLY; "
    "ODOO RUNTIME INSTALL/PATIENT-ISOLATION/TELECONSULTATION SMOKE TEST PENDING)"
)

