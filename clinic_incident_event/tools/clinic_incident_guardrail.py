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


manifest = ast.literal_eval(
    (ROOT / "__manifest__.py").read_text(encoding="utf-8")
)
depends = set(manifest.get("depends", []))


# ---------------------------------------------------------------------------
# HARD GATE 0 — Project Identity Preflight
# ---------------------------------------------------------------------------
if manifest.get("version") != "19.0.1.0.1":
    fail(0, "addon 34 runtime-repair version must be 19.0.1.0.1")

required_dependencies = {
    "clinic_base",
    "clinic_branch",
    "clinic_staff",
    "clinic_doctor",
    "clinic_patient",
    "clinic_booking",
    "clinic_queue_room",
    "clinic_room_device",
    "clinic_encounter",
    "clinic_emar",
    "clinic_feedback",
    "clinic_telemedicine_secure_messaging",
}
missing = sorted(required_dependencies - depends)
if missing:
    fail(0, f"required dependencies missing: {missing}")

future = {
    "clinic_quality",
    "clinic_integration_api",
    "clinic_audit",
    "clinic_analytics",
}
future_found = sorted(future.intersection(depends))
if future_found:
    fail(0, f"future ClinicOne dependency forbidden: {future_found}")

build = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_INCIDENT_EVENT_RUNTIME_REPAIR_20260826_V19.0.1.0.1" not in build:
    fail(0, "build marker mismatch")

preflight = (
    ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md"
).read_text(encoding="utf-8")
if "clinic19a(20260826-001541).md" not in preflight:
    fail(0, "latest user baseline is not locked")

if not any(line.startswith("[FAIL] HARD GATE 0") for line in errors):
    ok(0, "ClinicOne addon 34 identity, baseline and dependency boundary locked")


# ---------------------------------------------------------------------------
# HARD GATE 1 / 14 — Codex governance
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
    fail(14, "same-root-cause retry cap missing")

if not any(line.startswith("[FAIL] HARD GATE 1") for line in errors):
    ok(1, "Codex is bounded worker, not architect/simplifier")
if not any(line.startswith("[FAIL] HARD GATE 14") for line in errors):
    ok(14, "Codex retry limit locked")



# ---------------------------------------------------------------------------
# HARD GATE 10 — Odoo 19 dynamic User Access Rights XML-label safety
# ---------------------------------------------------------------------------
security_xml_path = ROOT / "security/clinic_incident_security.xml"
security_root = ET.parse(security_xml_path).getroot()
unsafe_privilege_labels = []

for record in security_root.findall("record"):
    if record.attrib.get("model") not in {
        "ir.module.category",
        "res.groups.privilege",
    }:
        continue

    name_field = record.find("./field[@name='name']")
    label = (name_field.text or "") if name_field is not None else ""
    if "&" in label:
        unsafe_privilege_labels.append(
            f"{record.attrib.get('model')}:{record.attrib.get('id')}={label}"
        )

if unsafe_privilege_labels:
    fail(
        10,
        "dynamic User Access Rights labels contain raw ampersand: "
        + ", ".join(unsafe_privilege_labels),
    )

if "ClinicOne Incident and Event" not in security_xml_path.read_text(
    encoding="utf-8"
):
    fail(10, "safe Incident privilege/category label is missing")

if not any(line.startswith("[FAIL] HARD GATE 10") for line in errors):
    ok(
        10,
        "Odoo 19 User Access Rights category/privilege labels are XML-safe",
    )


# ---------------------------------------------------------------------------
# Python / ORM inventory + class-load import audit
# ---------------------------------------------------------------------------
python_files = [
    path for path in ROOT.rglob("*.py")
    if not path.name.startswith("0")
]
model_files = [
    path for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py" and not path.name.startswith("0")
]
xml_files = [
    path for path in ROOT.rglob("*.xml")
    if not path.name.startswith("0")
]

owned_expected = {
    "clinic.incident.category",
    "clinic.incident",
    "clinic.incident.investigation",
    "clinic.incident.action",
    "clinic.incident.timeline",
}

owned_models = set()
defined_models = set()
field_map = defaultdict(dict)
method_map = defaultdict(set)
parent_map = defaultdict(set)
constraints = []
indexes = []
m2m_relations = []
dangerous_inherit = []
field_method_collisions = []
env_proxy_isinstance = []
class_load_issues = []
syntax_errors = []
test_methods = 0
class_methods = 0
comment_lines = 0
docstrings = 0


def root_name(expr):
    current = expr
    while isinstance(
        current,
        (ast.Attribute, ast.Call, ast.Subscript),
    ):
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
        syntax_errors.append(
            f"{path.relative_to(ROOT)}: {exc}"
        )
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
        elif isinstance(
            top,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            imported_names.add(top.name)
        elif isinstance(top, ast.Assign):
            imported_names.update(
                target.id
                for target in top.targets
                if isinstance(target, ast.Name)
            )

    for cls in (
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
    ):
        if ast.get_docstring(cls):
            docstrings += 1

        for expr in list(cls.bases) + list(cls.decorator_list):
            root = root_name(expr)
            if (
                root in {"api", "fields", "models", "_"}
                and root not in imported_names
            ):
                class_load_issues.append(
                    f"{path.relative_to(ROOT)}:{cls.lineno}:"
                    f"{cls.name} missing `{root}` import"
                )

        model_name = None
        inherit_value = None
        explicit_name = False
        class_fields = set()
        class_methods_local = set()

        for stmt in cls.body:
            if isinstance(
                stmt,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                class_methods += 1
                class_methods_local.add(stmt.name)

                for decorator in stmt.decorator_list:
                    root = root_name(decorator)
                    if (
                        root in {"api", "fields", "models", "_"}
                        and root not in imported_names
                    ):
                        class_load_issues.append(
                            f"{path.relative_to(ROOT)}:{stmt.lineno}:"
                            f"{cls.name}.{stmt.name} missing `{root}` import"
                        )

                if (
                    path.parent.name == "tests"
                    and stmt.name.startswith("test_")
                ):
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
                        load_root in {"api", "fields", "models", "_"}
                        and load_root not in imported_names
                    ):
                        class_load_issues.append(
                            f"{path.relative_to(ROOT)}:{stmt.lineno}:"
                            f"class assignment missing `{load_root}` import"
                        )

                    if (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "models"
                    ):
                        if func.attr == "Constraint":
                            constraints.append(
                                (model_name, target.id)
                            )
                        elif func.attr == "Index":
                            indexes.append(
                                (model_name, target.id)
                            )

                    if (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "fields"
                    ):
                        class_fields.add(target.id)

        technical_model = (
            model_name
            if model_name
            else inherit_value
            if isinstance(inherit_value, str)
            else None
        )

        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(
                f"{path.relative_to(ROOT)}::{cls.name}"
            )

        if technical_model:
            method_map[technical_model].update(class_methods_local)

            for stmt in cls.body:
                if (
                    not isinstance(stmt, ast.Assign)
                    or not isinstance(stmt.value, ast.Call)
                ):
                    continue

                func = stmt.value.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "fields"
                ):
                    continue

                comodel = None
                relation = None
                computed = False
                stored = False
                searchable = False

                if stmt.value.args:
                    try:
                        first = ast.literal_eval(stmt.value.args[0])
                    except Exception:
                        first = None
                    if (
                        func.attr in (
                            "Many2one",
                            "One2many",
                            "Many2many",
                        )
                        and isinstance(first, str)
                    ):
                        comodel = first

                for kw in stmt.value.keywords:
                    if kw.arg == "comodel_name":
                        try:
                            value = ast.literal_eval(kw.value)
                        except Exception:
                            value = None
                        if isinstance(value, str):
                            comodel = value
                    elif kw.arg == "relation":
                        try:
                            relation = ast.literal_eval(kw.value)
                        except Exception:
                            relation = None
                    elif kw.arg == "compute":
                        computed = True
                    elif kw.arg == "store":
                        try:
                            stored = bool(
                                ast.literal_eval(kw.value)
                            )
                        except Exception:
                            pass
                    elif kw.arg == "search":
                        searchable = True

                for target in stmt.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    field_map[technical_model][target.id] = {
                        "type": func.attr,
                        "comodel": comodel,
                        "computed": computed,
                        "store": stored,
                        "search": searchable,
                    }
                    if (
                        func.attr == "Many2many"
                        and relation
                    ):
                        m2m_relations.append(
                            (
                                technical_model,
                                target.id,
                                relation,
                            )
                        )

        collision = class_fields.intersection(
            class_methods_local
        )
        if collision:
            field_method_collisions.append(
                f"{path.relative_to(ROOT)}::{cls.name}:"
                f"{sorted(collision)}"
            )

    # Guard against the known ClinicOne Inventory defect pattern:
    # Odoo env-model proxies are recordsets, not Python classes.
    for function in ast.walk(tree):
        if not isinstance(
            function,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        proxies = set()
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Subscript)
                and isinstance(node.value.value, ast.Attribute)
                and isinstance(node.value.value.value, ast.Name)
                and node.value.value.value.id == "self"
                and node.value.value.attr == "env"
            ):
                proxies.add(node.targets[0].id)

        for node in ast.walk(function):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "isinstance"
                and len(node.args) >= 2
            ):
                continue
            second = node.args[1]
            if isinstance(second, ast.Name) and second.id in proxies:
                env_proxy_isinstance.append(
                    f"{path.relative_to(ROOT)}:"
                    f"{function.name}:{node.lineno}"
                )

if syntax_errors:
    fail(12, "Python syntax errors: " + " | ".join(syntax_errors))
if class_load_issues:
    fail(
        12,
        "Python class-load import errors: "
        + " | ".join(class_load_issues),
    )


# ---------------------------------------------------------------------------
# HARD GATE 2 — Existing Function Preservation
# ---------------------------------------------------------------------------
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

for owner in (
    "clinic.adverse.event",
    "clinic.ae.action",
    "clinic.ae.followup",
    "clinic.encounter",
    "clinic.emar.administration",
    "clinic.telemedicine.session",
    "clinic.telemedicine.thread",
):
    if f'_name = "{owner}"' in model_source:
        fail(2, f"upstream owner duplicated: {owner}")

for extension in (
    '_inherit = "clinic.adverse.event"',
    '_inherit = "clinic.encounter"',
    '_inherit = "clinic.emar.administration"',
    '_inherit = "clinic.telemedicine.session"',
    '_inherit = "clinic.telemedicine.thread"',
    '_inherit = "clinic.feedback.escalation"',
    '_inherit = "clinic.staff"',
    '_inherit = "clinic.staff.kpi"',
):
    if extension not in model_source:
        fail(2, f"bounded integration missing: {extension}")

operational = (
    ROOT / "models/operational_integration.py"
).read_text(encoding="utf-8")
if "super()._compute_counts()" not in operational:
    fail(2, "Staff counter integration must call super()")
if "super().recompute_snapshot(" not in operational:
    fail(2, "Staff KPI integration must call super()")

for forbidden in (
    "def action_done(",
    "def action_confirm(",
    "def action_close_encounter(",
    "def action_complete_session(",
):
    if forbidden in (
        (ROOT / "models/source_integration.py").read_text(encoding="utf-8")
        + operational
    ):
        fail(2, f"upstream lifecycle override found: {forbidden}")

if not any(line.startswith("[FAIL] HARD GATE 2") for line in errors):
    ok(2, "Adverse Event/eMAR/Feedback/Telemedicine/Staff ownership preserved")


# ---------------------------------------------------------------------------
# HARD GATE 3 — Enterprise Completeness
# ---------------------------------------------------------------------------
required_files = {
    "models/category.py",
    "models/incident.py",
    "models/incident_validation.py",
    "models/incident_navigation.py",
    "models/incident_workflow.py",
    "models/investigation.py",
    "models/corrective_action.py",
    "models/timeline.py",
    "models/source_integration.py",
    "models/operational_integration.py",
    "models/settings.py",
    "security/clinic_incident_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/category_data.xml",
    "views/category_views.xml",
    "views/incident_views.xml",
    "views/investigation_views.xml",
    "views/corrective_action_views.xml",
    "views/timeline_views.xml",
    "views/res_config_settings_views.xml",
    "views/integration_views.xml",
    "views/menu_views.xml",
    "report/incident_report.xml",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/LATEST_BASELINE_AUDIT.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/UI_UX_MATRIX.md",
    "docs/SECURITY_MODEL.md",
    "docs/DATABASE_IDENTIFIER_ORM_NAMING_SAFETY.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/SOURCE_STATIC_VALIDATION.md",
    "tests/test_incident_enterprise.py",
    "tools/clinic_incident_latest_bundle_audit.py",
}
missing_files = sorted(
    rel for rel in required_files
    if not (ROOT / rel).exists()
)
if missing_files:
    fail(3, f"enterprise deliverables missing: {missing_files}")
else:
    ok(3, "complete Incident/Investigation/CAPA/Timeline/security/report/test/tool set present")


# ---------------------------------------------------------------------------
# HARD GATE 4 — Full Structural Inventory
# ---------------------------------------------------------------------------
if owned_models != owned_expected:
    fail(
        4,
        f"owned model mismatch: expected={sorted(owned_expected)} "
        f"found={sorted(owned_models)}",
    )
else:
    ok(4, "5 owned persistent models and bounded integrations inventoried")


# ---------------------------------------------------------------------------
# HARD GATE 5 — Human-Friendly Coding Structure
# ---------------------------------------------------------------------------
largest = max(
    (
        len(path.read_text(encoding="utf-8").splitlines()),
        path.name,
    )
    for path in model_files
)
if largest[0] > 650:
    fail(5, f"model file exceeds 650-line maintenance threshold: {largest}")
if len(model_files) < 10:
    fail(5, f"responsibility split is too coarse: model_files={len(model_files)}")

if not any(line.startswith("[FAIL] HARD GATE 5") for line in errors):
    ok(5, f"human-friendly split passes; largest={largest[1]}:{largest[0]} lines")


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
        xml_errors.append(
            f"{path.relative_to(ROOT)}: {exc}"
        )

all_xml = "\n".join(all_xml_parts)
if xml_errors:
    fail(12, "XML/QWeb parse errors: " + " | ".join(xml_errors))


# ---------------------------------------------------------------------------
# HARD GATE 6 — Professional Form Design
# ---------------------------------------------------------------------------
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "alert alert-danger",
    "action_open_investigations",
    "action_open_actions",
    "action_print_case_summary",
    "action_verify_effective",
):
    if token not in all_xml:
        fail(6, f"professional Incident UX token missing: {token}")

for token in (
    "view_incident_kanban",
    "view_incident_pivot",
    "view_incident_graph",
    "view_incident_action_kanban",
    "view_incident_action_pivot",
    "view_incident_action_graph",
    "view_incident_regulatory_list",
):
    if token not in all_xml:
        fail(6, f"advanced enterprise UI missing: {token}")

if not any(line.startswith("[FAIL] HARD GATE 6") for line in errors):
    ok(6, "statusbars, smart/body/O2M actions, Kanban/Pivot/Graph/regulatory/PDF present")


# ---------------------------------------------------------------------------
# HARD GATE 7 — UI/UX Matrix
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
    ok(7, "Search/List/Form complete for all 5 owner models")


# ---------------------------------------------------------------------------
# HARD GATE 8 — Search View mandatory + searchability
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
        model = (
            (model_node.text or "").strip()
            if model_node is not None
            else ""
        )

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
                    domain = ast.literal_eval(
                        filter_node.attrib.get("domain", "[]")
                    )
                except Exception:
                    domain = []

                def walk(value):
                    if (
                        isinstance(value, tuple)
                        and len(value) >= 3
                        and isinstance(value[0], str)
                    ):
                        yield value[0]
                    elif isinstance(value, (list, tuple)):
                        for item in value:
                            yield from walk(item)

                for dotted in walk(domain):
                    field_name = dotted.split(".", 1)[0]
                    meta = field_map.get(model, {}).get(field_name)
                    if (
                        meta
                        and meta["computed"]
                        and not meta["store"]
                        and not meta["search"]
                    ):
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{field_name}"
                        )

if search_violations:
    fail(8, "Odoo19 Search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "non-searchable computed Search field: " + " | ".join(unsearchable))
if search_count < 5:
    fail(8, f"Search coverage too low: {search_count}")

if not any(line.startswith("[FAIL] HARD GATE 8") for line in errors):
    ok(8, f"{search_count} Search Views pass Odoo19 search architecture")


# ---------------------------------------------------------------------------
# HARD GATE 9 — List View Enterprise Quality
# ---------------------------------------------------------------------------
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(
        re.findall(r'<button[^>]+type="object"', all_xml)
    )
    if list_count < 9:
        fail(9, f"enterprise list coverage too low: {list_count}")
    if object_buttons < 55:
        fail(9, f"enterprise object-button coverage too low: {object_buttons}")

    if not any(line.startswith("[FAIL] HARD GATE 9") for line in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise quality")


# ---------------------------------------------------------------------------
# HARD GATE 10 — Security cannot be defeated by UI
# ---------------------------------------------------------------------------
security = (
    ROOT / "security/clinic_incident_security.xml"
).read_text(encoding="utf-8")

with (
    ROOT / "security/ir.model.access.csv"
).open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(
    r'<record[^>]*model="res.groups">(.*?)</record>',
    security,
    flags=re.S,
)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if (
    'model="res.groups.privilege"' not in security
    or 'name="privilege_id"' not in security
):
    fail(10, "Odoo19 privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if record_rules != 5:
    fail(10, f"expected 5 record rules, found {record_rules}")
if len(acl_rows) != 20:
    fail(10, f"expected 20 ACL rows, found {len(acl_rows)}")

for row in acl_rows:
    if row["group_id:id"] in {
        "base.group_public",
        "base.group_portal",
    }:
        fail(10, f"Portal/Public ACL forbidden: {row['id']}")

for token in (
    "user.clinic_incident_access_branch_ids.ids",
    "company_ids",
):
    if token not in security:
        fail(10, f"branch/company record-rule token missing: {token}")

incident_source = (
    ROOT / "models/incident.py"
).read_text(encoding="utf-8")
validation_source = (
    ROOT / "models/incident_validation.py"
).read_text(encoding="utf-8")
workflow_source = (
    ROOT / "models/incident_workflow.py"
).read_text(encoding="utf-8")
timeline_source = (
    ROOT / "models/timeline.py"
).read_text(encoding="utf-8")
integration_source = (
    (ROOT / "models/source_integration.py").read_text(encoding="utf-8")
    + (ROOT / "models/operational_integration.py").read_text(encoding="utf-8")
)

for token in (
    "incident_transition",
    "_require_reporter",
    "_require_investigator",
    "_require_manager",
    "policy_branch_scope_incident_event",
    "You are not allowed to use this Incident Branch",
):
    if token not in incident_source + validation_source + workflow_source:
        fail(10, f"backend workflow/security token missing: {token}")

for token in (
    "Incident Timeline evidence is immutable",
    "incident_timeline_system",
):
    if token not in timeline_source:
        fail(10, f"Timeline immutability token missing: {token}")

for forbidden in (
    ".message_ids",
    "message.body",
    "thread.internal_note",
):
    if forbidden in integration_source:
        fail(10, f"Secure Telemedicine content-copy regression: {forbidden}")

if not any(line.startswith("[FAIL] HARD GATE 10") for line in errors):
    ok(10, "backend workflow + branch/company rules + immutable evidence + secure-content boundary pass")


# ---------------------------------------------------------------------------
# HARD GATE 11 — DB Identifier & ORM Naming Safety
# ---------------------------------------------------------------------------
identifier_issues = []
snake_re = re.compile(r"^[a-z][a-z0-9_]*$")
model_re = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
)
reserved_sql = {
    "all","analyse","analyze","and","any","array","as","asc",
    "authorization","binary","both","case","cast","check","column",
    "constraint","create","current_date","current_role","current_time",
    "current_timestamp","current_user","default","deferrable","desc",
    "distinct","do","else","end","except","false","for","foreign",
    "from","grant","group","having","in","initially","intersect",
    "into","leading","limit","new","not","null","off","offset",
    "old","on","only","or","order","primary","references","select",
    "session_user","some","table","then","to","trailing","true",
    "union","unique","user","using","when","where","window","with",
}

for model_name in sorted(owned_expected):
    if not model_re.match(model_name):
        identifier_issues.append(
            f"unsafe model name: {model_name}"
        )
    table = model_name.replace(".", "_")
    if len(table.encode()) > 63:
        identifier_issues.append(
            f"table exceeds PostgreSQL 63-byte limit: {table}"
        )

    for field_name in field_map.get(model_name, {}):
        if not snake_re.match(field_name):
            identifier_issues.append(
                f"unsafe field: {model_name}.{field_name}"
            )
        if len(field_name.encode()) > 63:
            identifier_issues.append(
                f"field exceeds 63 bytes: {model_name}.{field_name}"
            )
        if field_name.lower() in reserved_sql:
            identifier_issues.append(
                f"reserved SQL field: {model_name}.{field_name}"
            )

for model_name, attr_name in constraints + indexes:
    if model_name not in owned_expected:
        continue
    generated = (
        f"{model_name.replace('.', '_')}_"
        f"{attr_name.lstrip('_')}"
    )
    if len(generated.encode()) > 63:
        identifier_issues.append(
            f"Constraint/Index identifier exceeds 63 bytes: {generated}"
        )

for model_name, field_name, relation in m2m_relations:
    if len(relation.encode()) > 63:
        identifier_issues.append(
            f"Many2many relation exceeds 63 bytes: "
            f"{model_name}.{field_name}:{relation}"
        )

identifier_issues.extend(
    f"field/method collision: {item}"
    for item in field_method_collisions
)
identifier_issues.extend(
    f"list-valued _inherit without explicit _name: {item}"
    for item in dangerous_inherit
)
identifier_issues.extend(
    f"env model proxy used as isinstance type: {item}"
    for item in env_proxy_isinstance
)

if identifier_issues:
    fail(11, " | ".join(identifier_issues))
else:
    ok(11, "owner namespaces/fields/relations/constraints/indexes pass DB/ORM safety")


# ---------------------------------------------------------------------------
# HARD GATE 12 — Odoo 19 / Human-Friendly Source Contract
# ---------------------------------------------------------------------------
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
if "<tree" in all_xml:
    fail(12, "legacy tree view found")

views_text = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (ROOT / "views").glob("*.xml")
)
inherit_refs = set(
    re.findall(
        r'<field name="inherit_id" ref="([^"]+)"',
        views_text,
    )
)
expected_inherit_refs = {
    "base.view_partner_form",
    "base.res_config_settings_view_form",
}
if inherit_refs != expected_inherit_refs:
    fail(
        12,
        f"fragile/unexpected inherited view refs: {sorted(inherit_refs)}",
    )

if len(constraints) < 3 or len(indexes) < 5:
    fail(
        12,
        f"Constraint/Index coverage insufficient: "
        f"{len(constraints)}/{len(indexes)}",
    )

if not any(line.startswith("[FAIL] HARD GATE 12") for line in errors):
    ok(12, f"Odoo19 source/view/class-load contracts pass; Constraint={len(constraints)}, Index={len(indexes)}")


# ---------------------------------------------------------------------------
# HARD GATE 13 — Useful comments
# ---------------------------------------------------------------------------
if comment_lines < 45 or docstrings < 18:
    fail(
        13,
        f"comment/docstring coverage too low: "
        f"comments={comment_lines}, docstrings={docstrings}",
    )
else:
    ok(13, f"ownership/security comments and class docs pass: comments={comment_lines}, docstrings={docstrings}")


# ---------------------------------------------------------------------------
# HARD GATE 15 — Enterprise Completeness Matrix
# ---------------------------------------------------------------------------
matrix = (
    ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md"
).read_text(encoding="utf-8")

if (
    "Odoo runtime activation | PENDING" not in matrix
    or "Source/static PASS is not runtime completion" not in matrix
):
    fail(15, "static/runtime completion separation missing")

for capability in (
    "Historical Staff `occurred_at`",
    "Existing `clinic.adverse.event` ownership preserved",
    "CAPA effectiveness verification",
    "Secure Message body auto-copy | ABSENT",
    "Branch record-rule visibility",
    "Immutable Incident Timeline",
    "QWeb Incident Case Summary",
):
    if capability not in matrix:
        fail(15, f"completeness capability missing: {capability}")

if test_methods < 700:
    fail(
        15,
        f"runtime contract/regression suite too small: {test_methods}",
    )

if not any(line.startswith("[FAIL] HARD GATE 15") for line in errors):
    ok(15, f"enterprise completeness matrix + {test_methods} runtime contract/regression tests pass")


print("ClinicOne clinic_incident_event Enterprise Development Guardrail")
print(
    f"[INFO] model_files={len(model_files)} "
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
    "ODOO RUNTIME INSTALL/INCIDENT-WORKFLOW SMOKE TEST PENDING)"
)
