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


# ===========================================================================
# HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
# ===========================================================================
if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative addon-35 version must be 19.0.1.0.0")

required_dependencies = {
    "clinic_base",
    "clinic_branch",
    "clinic_staff",
    "clinic_doctor",
    "clinic_treatment_catalog",
    "clinic_inventory",
    "clinic_room_device",
    "clinic_incident_event",
}
missing_dependencies = sorted(
    required_dependencies - depends
)
if missing_dependencies:
    fail(
        0,
        f"required Quality dependencies missing: {missing_dependencies}",
    )

future_dependencies = {
    "clinic_integration_api",
    "clinic_audit",
    "clinic_analytics",
}
future_found = sorted(
    future_dependencies.intersection(depends)
)
if future_found:
    fail(
        0,
        f"future ClinicOne dependencies forbidden: {future_found}",
    )

build = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_QUALITY_BUILD_20260821_V19.0.1.0.0" not in build:
    fail(0, "authoritative addon-35 build marker missing")

preflight = (
    ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md"
).read_text(encoding="utf-8")
official = (
    "Documents standard operating procedures "
    "and compliance quality checks."
)
if official not in preflight:
    fail(0, "official addon-35 blueprint responsibility is not locked")
if "clinic19a(20260821-080252).md" not in preflight:
    fail(0, "latest user baseline is not locked")

if not any(
    line.startswith("[FAIL] HARD GATE 0")
    for line in errors
):
    ok(
        0,
        "ClinicOne addon 35 SOP + compliance-quality identity and baseline locked",
    )


# ===========================================================================
# HARD GATE 1 / 14 — CODEX GOVERNANCE
# ===========================================================================
agents = (ROOT / "AGENTS.md").read_text(
    encoding="utf-8"
).lower()

for term in (
    "bounded implementation worker",
    "architect",
    "simplifier",
    "endless retry",
    "maximum 2",
):
    if term not in agents:
        fail(
            1,
            f"Codex governance term missing: {term}",
        )

if "maximum 1 repeat" not in agents:
    fail(
        14,
        "same-root-cause retry limit missing",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 1")
    for line in errors
):
    ok(
        1,
        "Codex is bounded worker, not Quality/Incident/Inventory architect",
    )
if not any(
    line.startswith("[FAIL] HARD GATE 14")
    for line in errors
):
    ok(
        14,
        "Codex retry limit locked",
    )


# ===========================================================================
# Python / ORM inventory + class-load import audit
# ===========================================================================
python_files = [
    path
    for path in ROOT.rglob("*.py")
    if not path.name.startswith("0")
]
model_files = [
    path
    for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py"
    and not path.name.startswith("0")
]
xml_files = [
    path
    for path in ROOT.rglob("*.xml")
    if not path.name.startswith("0")
]

owned_expected = {
    "clinic.quality.sop",
    "clinic.quality.sop.version",
    "clinic.quality.sop.acknowledgement",
    "clinic.quality.check.template",
    "clinic.quality.check.template.line",
    "clinic.quality.check",
    "clinic.quality.check.line",
    "clinic.quality.schedule",
}
abstract_expected = {
    "clinic.quality.security.mixin",
    "clinic.quality.scope.mixin",
}

owned_models = set()
abstract_models = set()
field_map = defaultdict(dict)
method_map = defaultdict(set)
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
    return (
        current.id
        if isinstance(current, ast.Name)
        else None
    )


for path in python_files:
    source = path.read_text(encoding="utf-8")
    comment_lines += sum(
        1
        for line in source.splitlines()
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
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            imported_names.add(top.name)
        elif isinstance(top, ast.Assign):
            imported_names.update(
                target.id
                for target in top.targets
                if isinstance(target, ast.Name)
            )

    for cls in (
        node
        for node in tree.body
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
        is_abstract = False
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

                elif target.id == "_inherit":
                    try:
                        inherit_value = ast.literal_eval(stmt.value)
                    except Exception:
                        pass

                elif target.id == "_abstract":
                    try:
                        is_abstract = bool(
                            ast.literal_eval(stmt.value)
                        )
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

        if (
            isinstance(inherit_value, list)
            and not explicit_name
        ):
            dangerous_inherit.append(
                f"{path.relative_to(ROOT)}::{cls.name}"
            )

        if model_name in owned_expected:
            owned_models.add(model_name)
        if is_abstract and model_name:
            abstract_models.add(model_name)

        if technical_model:
            method_map[technical_model].update(
                class_methods_local
            )

            for stmt in cls.body:
                if not (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.value, ast.Call)
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
                        first = ast.literal_eval(
                            stmt.value.args[0]
                        )
                    except Exception:
                        first = None

                    if (
                        func.attr
                        in ("Many2one", "One2many", "Many2many")
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
                            relation = ast.literal_eval(
                                kw.value
                            )
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

    # Known ClinicOne defect class:
    # self.env["model"] is a recordset proxy, not a Python isinstance type.
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
            if (
                isinstance(second, ast.Name)
                and second.id in proxies
            ):
                env_proxy_isinstance.append(
                    f"{path.relative_to(ROOT)}:"
                    f"{function.name}:{node.lineno}"
                )

if syntax_errors:
    fail(
        12,
        "Python syntax errors: "
        + " | ".join(syntax_errors),
    )
if class_load_issues:
    fail(
        12,
        "Python class-load import/symbol errors: "
        + " | ".join(class_load_issues),
    )


# ===========================================================================
# HARD GATE 2 — EXISTING FUNCTION PRESERVATION
# ===========================================================================
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

for forbidden_owner in (
    "clinic.incident",
    "clinic.incident.action",
    "clinic.incident.investigation",
    "clinic.room",
    "clinic.staff",
    "clinic.doctor",
    "clinic.treatment",
    "stock.lot",
):
    if f'_name = "{forbidden_owner}"' in model_source:
        fail(
            2,
            f"upstream owner duplicated: {forbidden_owner}",
        )

for required_extension in (
    '_inherit = "clinic.incident"',
    '_inherit = "clinic.branch"',
    '_inherit = "clinic.room"',
    '_inherit = "clinic.staff"',
    '_inherit = "clinic.doctor"',
    '_inherit = "clinic.treatment"',
    '_inherit = "stock.lot"',
):
    if required_extension not in model_source:
        fail(
            2,
            f"required bounded Quality integration missing: {required_extension}",
        )

for prohibited_override in (
    "def action_close(",
    "def action_done(",
    "def action_confirm(",
    "def action_complete_session(",
):
    source_bridges = (
        (ROOT / "models/source_bridges.py").read_text(encoding="utf-8")
        + (ROOT / "models/incident_bridge.py").read_text(encoding="utf-8")
    )
    if prohibited_override in source_bridges:
        fail(
            2,
            f"upstream lifecycle override found in bridge: {prohibited_override}",
        )

if "clinic_quality_state" not in (
    ROOT / "models/source_bridges.py"
).read_text(encoding="utf-8"):
    fail(
        2,
        "Inventory Quality ownership preservation evidence missing",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 2")
    for line in errors
):
    ok(
        2,
        "Incident/Inventory/Branch/Room/Staff/Doctor/Treatment ownership preserved",
    )


# ===========================================================================
# HARD GATE 3 — ENTERPRISE COMPLETENESS
# ===========================================================================
required_files = {
    "models/scope_mixin.py",
    "models/sop.py",
    "models/sop_version.py",
    "models/sop_acknowledgement.py",
    "models/check_template.py",
    "models/quality_check.py",
    "models/quality_check_workflow.py",
    "models/quality_check_navigation.py",
    "models/check_line.py",
    "models/schedule.py",
    "models/incident_bridge.py",
    "models/source_bridges.py",
    "models/settings.py",
    "security/clinic_quality_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/sop_views.xml",
    "views/sop_version_views.xml",
    "views/sop_acknowledgement_views.xml",
    "views/check_template_views.xml",
    "views/check_template_line_views.xml",
    "views/quality_check_views.xml",
    "views/check_line_views.xml",
    "views/schedule_views.xml",
    "views/res_config_settings_views.xml",
    "views/menu_views.xml",
    "report/sop_report.xml",
    "report/quality_check_report.xml",
    "docs/PROJECT_IDENTITY_PREFLIGHT.md",
    "docs/LATEST_BASELINE_AUDIT.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/UI_UX_MATRIX.md",
    "docs/SECURITY_MODEL.md",
    "docs/DATABASE_IDENTIFIER_ORM_NAMING_SAFETY.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/SOURCE_STATIC_VALIDATION.md",
    "tests/test_quality_enterprise.py",
    "tools/clinic_quality_latest_bundle_audit.py",
}
missing_files = sorted(
    rel
    for rel in required_files
    if not (ROOT / rel).exists()
)

if missing_files:
    fail(
        3,
        f"enterprise deliverables missing: {missing_files}",
    )
else:
    ok(
        3,
        "SOP/version/acknowledgement + templates/checks/schedules + Incident integration + reports/tests/docs present",
    )


# ===========================================================================
# HARD GATE 4 — FULL STRUCTURAL INVENTORY
# ===========================================================================
if owned_models != owned_expected:
    fail(
        4,
        f"owned models mismatch expected={sorted(owned_expected)} "
        f"found={sorted(owned_models)}",
    )
if not abstract_expected.issubset(abstract_models):
    fail(
        4,
        f"abstract mixin inventory incomplete: "
        f"{sorted(abstract_expected - abstract_models)}",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 4")
    for line in errors
):
    ok(
        4,
        "8 persistent owners + 2 abstract mixins + bounded bridges inventoried",
    )


# ===========================================================================
# HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
# ===========================================================================
largest_model = max(
    (
        len(
            path.read_text(
                encoding="utf-8"
            ).splitlines()
        ),
        path.name,
    )
    for path in model_files
)

if largest_model[0] > 700:
    fail(
        5,
        f"model file exceeds maintenance threshold: {largest_model}",
    )

if len(model_files) < 11:
    fail(
        5,
        f"responsibility split too coarse: model_files={len(model_files)}",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 5")
    for line in errors
):
    ok(
        5,
        f"human-friendly responsibility split passes; "
        f"largest={largest_model[1]}:{largest_model[0]} lines",
    )


# ===========================================================================
# XML parse aggregate
# ===========================================================================
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
    fail(
        12,
        "XML/QWeb parse errors: "
        + " | ".join(xml_errors),
    )


# ===========================================================================
# HARD GATE 6 — PROFESSIONAL FORM DESIGN
# ===========================================================================
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "<chatter",
    "alert alert-danger",
    "action_acknowledge_current_version",
    "action_create_incidents_for_failed_lines",
    "action_print_current_sop",
    "action_print_quality_check",
):
    if token not in all_xml:
        fail(
            6,
            f"professional Quality UX token missing: {token}",
        )

for token in (
    "view_quality_sop_kanban",
    "view_quality_check_kanban",
    "view_quality_check_pivot",
    "view_quality_check_graph",
    "action_quality_review_queue",
    "action_quality_nonconformity",
):
    if token not in all_xml:
        fail(
            6,
            f"advanced enterprise Quality UI missing: {token}",
        )

if not any(
    line.startswith("[FAIL] HARD GATE 6")
    for line in errors
):
    ok(
        6,
        "statusbars, smart/body/O2M actions, Kanban/Pivot/Graph/review queues/PDF present",
    )


# ===========================================================================
# HARD GATE 7 — UI/UX MATRIX PER MODEL
# ===========================================================================
view_matrix = {
    model: {
        "search": False,
        "list": False,
        "form": False,
    }
    for model in owned_expected
}

for path in xml_files:
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue

        model_node = record.find(
            "./field[@name='model']"
        )
        arch_node = record.find(
            "./field[@name='arch']"
        )
        if (
            model_node is None
            or arch_node is None
        ):
            continue

        model = (model_node.text or "").strip()
        if model not in view_matrix:
            continue

        children = list(arch_node)
        if (
            children
            and children[0].tag
            in view_matrix[model]
        ):
            view_matrix[model][
                children[0].tag
            ] = True

missing_matrix = {
    model: [
        kind
        for kind, present in kinds.items()
        if not present
    ]
    for model, kinds in view_matrix.items()
    if not all(kinds.values())
}

if missing_matrix:
    fail(
        7,
        f"Search/List/Form matrix incomplete: {missing_matrix}",
    )
else:
    ok(
        7,
        "Search/List/Form complete for all 8 owned Quality models",
    )


# ===========================================================================
# HARD GATE 8 — SEARCH VIEW WAJIB
# ===========================================================================
search_count = 0
search_violations = []
unsearchable = []

for path in xml_files:
    root = ET.parse(path).getroot()

    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue

        model_node = record.find(
            "./field[@name='model']"
        )
        model = (
            (model_node.text or "").strip()
            if model_node is not None
            else ""
        )

        for search in record.findall(".//search"):
            search_count += 1

            if search.attrib:
                search_violations.append(
                    f"{path.relative_to(ROOT)}:"
                    f"<search> attrs={dict(search.attrib)}"
                )

            for child in list(search):
                if (
                    child.tag == "group"
                    and child.attrib
                ):
                    search_violations.append(
                        f"{path.relative_to(ROOT)}:"
                        f"<search>/<group> attrs={dict(child.attrib)}"
                    )

            for filter_node in search.findall(
                ".//filter[@domain]"
            ):
                try:
                    domain = ast.literal_eval(
                        filter_node.attrib.get(
                            "domain",
                            "[]",
                        )
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
                    field_name = dotted.split(
                        ".",
                        1,
                    )[0]
                    meta = field_map.get(
                        model,
                        {},
                    ).get(field_name)

                    if (
                        meta
                        and meta["computed"]
                        and not meta["store"]
                        and not meta["search"]
                    ):
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:"
                            f"{model}.{field_name}"
                        )

if search_violations:
    fail(
        8,
        "Odoo19 Search architecture violation: "
        + " | ".join(search_violations),
    )
if unsearchable:
    fail(
        8,
        "non-searchable computed Search field: "
        + " | ".join(unsearchable),
    )
if search_count < 8:
    fail(
        8,
        f"Search coverage too low: {search_count}",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 8")
    for line in errors
):
    ok(
        8,
        f"{search_count} Search Views pass Odoo19 search architecture",
    )


# ===========================================================================
# HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
# ===========================================================================
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(
        9,
        "legacy <tree> architecture found",
    )
else:
    list_count = all_xml.count("<list")
    object_buttons = len(
        re.findall(
            r'<button[^>]+type="object"',
            all_xml,
        )
    )

    if list_count < 13:
        fail(
            9,
            f"enterprise list coverage too low: {list_count}",
        )
    if object_buttons < 70:
        fail(
            9,
            f"enterprise object-button coverage too low: {object_buttons}",
        )

    if not any(
        line.startswith("[FAIL] HARD GATE 9")
        for line in errors
    ):
        ok(
            9,
            f"{list_count} list tags and {object_buttons} object buttons pass enterprise quality",
        )


# ===========================================================================
# HARD GATE 10 — SECURITY CANNOT BE DEFEATED BY UI
# ===========================================================================
security = (
    ROOT / "security/clinic_quality_security.xml"
).read_text(encoding="utf-8")

with (
    ROOT / "security/ir.model.access.csv"
).open(encoding="utf-8") as handle:
    acl_rows = list(
        csv.DictReader(handle)
    )

group_blocks = re.findall(
    r'<record[^>]*model="res.groups">(.*?)</record>',
    security,
    flags=re.S,
)
if any(
    'name="category_id"' in block
    for block in group_blocks
):
    fail(
        10,
        "legacy category_id found directly on res.groups",
    )

if (
    'model="res.groups.privilege"' not in security
    or 'name="privilege_id"' not in security
):
    fail(
        10,
        "Odoo19 Quality privilege hierarchy missing",
    )

record_rules = security.count(
    'model="ir.rule"'
)

if record_rules != 8:
    fail(
        10,
        f"expected 8 Quality record rules, found {record_rules}",
    )
if len(acl_rows) != 32:
    fail(
        10,
        f"expected 32 ACL rows, found {len(acl_rows)}",
    )

for row in acl_rows:
    if row["group_id:id"] in {
        "base.group_public",
        "base.group_portal",
    }:
        fail(
            10,
            f"Portal/Public backend ACL forbidden: {row['id']}",
        )

for token in (
    "user.clinic_quality_access_branch_ids.ids",
    "company_ids",
):
    if token not in security:
        fail(
            10,
            f"company/branch record-rule token missing: {token}",
        )

quality_sources = "\n".join(
    (
        ROOT / rel
    ).read_text(encoding="utf-8")
    for rel in (
        "models/sop.py",
        "models/sop_version.py",
        "models/sop_acknowledgement.py",
        "models/check_template.py",
        "models/quality_check.py",
        "models/check_line.py",
        "models/schedule.py",
    )
)

for token in (
    "_quality_require_user",
    "_quality_require_inspector",
    "_quality_require_approver",
    "_quality_require_manager",
    "quality_sop_version_transition",
    "quality_check_transition",
    "quality_schedule_transition",
):
    if token not in (
        quality_sources
        + (
            ROOT / "models/scope_mixin.py"
        ).read_text(encoding="utf-8")
    ):
        fail(
            10,
            f"backend Quality security/workflow token missing: {token}",
        )

check_line_source = (
    ROOT / "models/check_line.py"
).read_text(encoding="utf-8")
if (
    "clinic_incident_event.group_incident_reporter"
    not in check_line_source
):
    fail(
        10,
        "Quality failure Incident escalation does not preserve Incident Reporter ACL boundary",
    )

source_bridge = (
    ROOT / "models/source_bridges.py"
).read_text(encoding="utf-8")
for prohibited_mutation in (
    'write({"clinic_quality_state"',
    "action_suggest_quarantine_transfer(",
    "action_done(",
    "action_confirm(",
):
    if prohibited_mutation in source_bridge:
        fail(
            10,
            f"Quality bridge mutates upstream workflow: {prohibited_mutation}",
        )

if not any(
    line.startswith("[FAIL] HARD GATE 10")
    for line in errors
):
    ok(
        10,
        "backend roles + company/branch rules + immutable evidence + Incident ACL boundary pass",
    )


# ===========================================================================
# HARD GATE 11 — DATABASE IDENTIFIER & ORM NAMING SAFETY
# ===========================================================================
identifier_issues = []

snake_re = re.compile(
    r"^[a-z][a-z0-9_]*$"
)
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

    table = model_name.replace(
        ".",
        "_",
    )
    if len(table.encode()) > 63:
        identifier_issues.append(
            f"table exceeds PostgreSQL 63-byte limit: {table}"
        )

    for field_name in field_map.get(
        model_name,
        {},
    ):
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
    f"env-model proxy used as isinstance type: {item}"
    for item in env_proxy_isinstance
)

if identifier_issues:
    fail(
        11,
        " | ".join(identifier_issues),
    )
else:
    ok(
        11,
        "8 owner namespaces/fields/relations/constraints/indexes pass DB/ORM safety",
    )


# ===========================================================================
# HARD GATE 12 — ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS
# ===========================================================================
if "_sql_constraints" in model_source:
    fail(
        12,
        "legacy executable _sql_constraints found",
    )

if (
    'attrs="' in all_xml
    or 'states="' in all_xml
):
    fail(
        12,
        "legacy attrs/states XML syntax found",
    )

if "<tree" in all_xml:
    fail(
        12,
        "legacy tree view found",
    )

view_xml = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (
        ROOT / "views"
    ).glob("*.xml")
)

inherit_refs = set(
    re.findall(
        r'<field name="inherit_id" ref="([^"]+)"',
        view_xml,
    )
)

if inherit_refs != {
    "base.res_config_settings_view_form",
}:
    fail(
        12,
        f"fragile/unexpected inherited views: {sorted(inherit_refs)}",
    )

if len(constraints) < 8:
    fail(
        12,
        f"models.Constraint coverage insufficient: {len(constraints)}",
    )
if len(indexes) < 8:
    fail(
        12,
        f"models.Index coverage insufficient: {len(indexes)}",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 12")
    for line in errors
):
    ok(
        12,
        f"Odoo19 views/class-load/source contracts pass; "
        f"Constraint={len(constraints)}, Index={len(indexes)}",
    )


# ===========================================================================
# HARD GATE 13 — COMMENTS THAT ARE USEFUL
# ===========================================================================
if (
    comment_lines < 45
    or docstrings < 20
):
    fail(
        13,
        f"comment/docstring coverage too low: "
        f"comments={comment_lines}, docstrings={docstrings}",
    )
else:
    ok(
        13,
        f"ownership/security/workflow comments and docs pass: "
        f"comments={comment_lines}, docstrings={docstrings}",
    )


# ===========================================================================
# HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
# ===========================================================================
matrix = (
    ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md"
).read_text(encoding="utf-8")

if (
    "Odoo runtime activation | PENDING"
    not in matrix
    or "Source/static PASS is not runtime completion"
    not in matrix
):
    fail(
        15,
        "completeness matrix does not separate static/runtime status",
    )

for capability in (
    "SOP immutable approved versions",
    "SOP Staff acknowledgement",
    "Critical-failure Incident gate",
    "Inventory quality-state mutation | ABSENT",
    "Recurring Quality Schedules",
    "Search/List/Form 8/8",
    "Current SOP PDF",
    "Quality Check PDF",
):
    if capability not in matrix:
        fail(
            15,
            f"completeness capability missing: {capability}",
        )

if test_methods < 1200:
    fail(
        15,
        f"runtime contract/regression suite too small: {test_methods}",
    )

if not any(
    line.startswith("[FAIL] HARD GATE 15")
    for line in errors
):
    ok(
        15,
        f"SOP + compliance checks + scheduling + controlled Incident escalation "
        f"+ {test_methods} runtime contract/regression tests pass source/static completeness",
    )


print(
    "ClinicOne clinic_quality Enterprise Development Guardrail"
)
print(
    f"[INFO] model_files={len(model_files)} "
    f"python_files={len(python_files)} "
    f"xml_files={len(xml_files)}"
)
print(
    f"[INFO] persistent_models={len(owned_expected)} "
    f"abstract_models={len(abstract_expected)} "
    f"models.Constraint={len(constraints)} "
    f"models.Index={len(indexes)}"
)
print(
    f"[INFO] search_views={search_count} "
    f"acl_rows={len(acl_rows)} "
    f"record_rules={record_rules}"
)
print(
    f"[INFO] test_methods={test_methods} "
    f"class_methods={class_methods} "
    f"comments={comment_lines} "
    f"docstrings={docstrings}"
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
    "ODOO RUNTIME INSTALL/QUALITY-WORKFLOW SMOKE TEST PENDING)"
)
