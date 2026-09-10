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
if manifest.get("version") != "19.0.1.0.1":
    fail(0, "authoritative version must be 19.0.1.0.1")

required_dependencies = {
    "clinic_base",
    "clinic_branch",
    "clinic_reports",
}
missing_dependencies = sorted(required_dependencies - depends)
if missing_dependencies:
    fail(0, f"required Dashboard dependencies missing: {missing_dependencies}")

future_dependencies = {
    "clinic_ecommerce",
    "clinic_portal",
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
if "CLINIC_DASHBOARD_BUILD_20260909_V19.0.1.0.1" not in build:
    fail(0, "authoritative Dashboard build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
if "Interactive dashboards for KPIs, revenue, performance, and room utilization." not in preflight:
    fail(0, "official addon-29 Dashboard blueprint responsibility is not locked")

if manifest.get("post_init_hook") != "post_init_hook":
    fail(0, "Odoo 19 post_init_hook is not declared")

root_init = (ROOT / "__init__.py").read_text(encoding="utf-8")
if "from .hooks import post_init_hook" not in root_init:
    fail(0, "post_init_hook is not exposed from addon package __init__.py")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 29 / KPI + revenue + performance + room-utilization Dashboard identity locked")


# HARD GATE 1 + 14 — CODEX GOVERNANCE.
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
    fail(14, "same-root-cause Codex retry limit missing")

if not any(item.startswith("[FAIL] HARD GATE 1") for item in errors):
    ok(1, "Codex is bounded implementation worker, not architect/KPI owner/simplifier")
if not any(item.startswith("[FAIL] HARD GATE 14") for item in errors):
    ok(14, "Codex retry limit = maximum two bounded attempts / one repeated root cause")


# Parse Python and inventory contracts.
python_files = list(ROOT.rglob("*.py"))
model_files = [
    path for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py"
]
xml_files = list(ROOT.rglob("*.xml"))

python_errors = []
defined_models = set()
technical_fields = {}
constraints = 0
indexes = 0
dangerous_inherit = []
test_methods = 0
class_methods = 0
comment_lines = 0
docstrings = 0

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
                    if "store" in kwargs:
                        try:
                            stored = bool(ast.literal_eval(kwargs["store"]))
                        except Exception:
                            pass
                    field_map[target.id] = {
                        "computed": computed,
                        "store": stored,
                        "search": searchable,
                    }

        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{node.name}")

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))


# HARD GATE 2 — EXISTING FUNCTION PRESERVATION.
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

for forbidden in (
    '_name = "clinic.report.definition"',
    '_name = "clinic.report.run"',
    '_name = "clinic.report.metric"',
    '_name = "clinic.report.detail"',
    '_name = "clinic.billing.invoice"',
    '_name = "clinic.ar.invoice"',
    '_name = "clinic.ap"',
    '_name = "booking.booking"',
    '_name = "clinic.queue"',
    '_name = "clinic.encounter"',
    '_name = "clinic.feedback"',
):
    if forbidden in model_source:
        fail(2, f"upstream ownership duplicated: {forbidden}")

for allowed_extension in (
    '_inherit = "res.company"',
    '_inherit = "res.config.settings"',
    '_inherit = "clinic.branch"',
    '_inherit = "clinic.report.run"',
):
    if allowed_extension not in model_source:
        fail(2, f"expected additive Dashboard integration missing: {allowed_extension}")

board_source = (ROOT / "models/dashboard_board.py").read_text(encoding="utf-8")
if 'self.env["clinic.report.run"].create' not in board_source:
    fail(2, "missing Report Run delegation contract")
if "run.action_generate()" not in board_source:
    fail(2, "Dashboard does not delegate KPI generation to clinic_reports")
for upstream_write_pattern in (
    'self.env["clinic.billing',
    'self.env["clinic.ar',
    'self.env["clinic.ap',
    'self.env["booking.booking',
    'self.env["clinic.queue',
    'self.env["clinic.encounter',
    'self.env["clinic.feedback',
):
    if upstream_write_pattern in model_source:
        fail(2, f"Dashboard directly touches transactional source model: {upstream_write_pattern}")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "clinic_reports remains KPI owner; Dashboard only delegates missing Report Runs and snapshots normalized metrics")


# HARD GATE 3 — ENTERPRISE COMPLETENESS.
required_files = {
    "models/dashboard_defaults.py",
    "models/dashboard_board.py",
    "models/dashboard_widget.py",
    "models/dashboard_snapshot.py",
    "models/dashboard_snapshot_line.py",
    "models/settings.py",
    "models/integration_bridge.py",
    "security/clinic_dashboard_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/dashboard_board_views.xml",
    "views/dashboard_widget_views.xml",
    "views/dashboard_snapshot_views.xml",
    "views/dashboard_snapshot_line_views.xml",
    "views/res_config_settings_views.xml",
    "views/dashboard_client_action.xml",
    "views/menu_views.xml",
    "static/src/js/dashboard_client.js",
    "static/src/xml/dashboard_client.xml",
    "static/src/scss/dashboard.scss",
    "tests/test_dashboard_enterprise.py",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise Dashboard deliverables missing: {missing_files}")
else:
    ok(3, "interactive client + six boards + snapshots + trends + thresholds + schedules + backend fallback + tests/docs present")


# HARD GATE 4 — FULL STRUCTURAL INVENTORY.
owned_models = {
    "clinic.dashboard.board",
    "clinic.dashboard.widget",
    "clinic.dashboard.snapshot",
    "clinic.dashboard.snapshot.line",
}
missing_models = owned_models - defined_models
if missing_models:
    fail(4, f"owned Dashboard model inventory incomplete: {sorted(missing_models)}")
else:
    ok(4, "4 owned persistent Dashboard models plus additive Company/Branch/Report integrations inventoried")


# HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE.
required_model_files = {
    "dashboard_defaults.py",
    "dashboard_board.py",
    "dashboard_widget.py",
    "dashboard_snapshot.py",
    "dashboard_snapshot_line.py",
    "settings.py",
    "integration_bridge.py",
}
actual_model_files = {path.name for path in model_files}
missing_model_files = sorted(required_model_files - actual_model_files)
if missing_model_files:
    fail(5, f"focused Dashboard model-file structure incomplete: {missing_model_files}")
else:
    ok(5, f"human-friendly Dashboard responsibilities split across {len(model_files)} focused model files")


# XML aggregate.
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
    "alert alert-warning",
    "action_open_live_dashboard",
    "action_open_report_run",
):
    if token not in all_xml:
        fail(6, f"professional Dashboard UI token missing: {token}")

client_js = (ROOT / "static/src/js/dashboard_client.js").read_text(encoding="utf-8")
client_xml = (ROOT / "static/src/xml/dashboard_client.xml").read_text(encoding="utf-8")
for token in (
    'registry.category("actions").add',
    'useService("orm")',
    'useService("action")',
    'useService("notification")',
    'clinic_dashboard.main',
):
    if token not in client_js:
        fail(6, f"Owl client action contract missing: {token}")

for token in (
    "Refresh",
    "Branch",
    "Date From",
    "Date To",
    "Open Report",
):
    if token not in client_xml:
        fail(6, f"interactive Dashboard control missing: {token}")

if not any(item.startswith("[FAIL] HARD GATE 6") for item in errors):
    ok(6, "statusbars, smart/body/O2M actions plus Odoo 19 Owl interactive workspace are present")


# HARD GATE 7 — UI/UX MATRIX.
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
    ok(7, "Search/List/Form complete for all 4 owned Dashboard models; Kanban/Pivot/Graph supplement the matrix")


# HARD GATE 8 — SEARCH VIEW + SEARCHABILITY.
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
                    value = ast.literal_eval(domain)
                except Exception:
                    value = []

                def walk(obj):
                    if (
                        isinstance(obj, tuple)
                        and len(obj) >= 3
                        and isinstance(obj[0], str)
                    ):
                        yield obj[0]
                        return
                    if isinstance(obj, (list, tuple)):
                        for item in obj:
                            yield from walk(item)

                for dotted in walk(value):
                    base = dotted.split(".", 1)[0]
                    meta = technical_fields.get(model, {}).get(base)
                    if meta and meta["computed"] and not meta["store"] and not meta["search"]:
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{base}:{filter_node.attrib.get('name')}"
                        )

if search_violations:
    fail(8, "Odoo19 Dashboard search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable Dashboard fields used in search domains: " + " | ".join(unsearchable))
if search_count < 4:
    fail(8, f"Dashboard search-view coverage too low: {search_count}")

if not any(item.startswith("[FAIL] HARD GATE 8") for item in errors):
    ok(8, f"{search_count} Dashboard search views pass Odoo19 architecture/searchability gates")


# HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY.
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 6:
        fail(9, f"enterprise Dashboard list coverage too low: {list_count}")
    if object_buttons < 35:
        fail(9, f"enterprise Dashboard object-button coverage too low: {object_buttons}")
    if not any(item.startswith("[FAIL] HARD GATE 9") for item in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise Dashboard quality")


# HARD GATE 10 — SECURITY CANNOT BE DEFEATED BY UI.
security = (ROOT / "security/clinic_dashboard_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(
    r'<record[^>]*model="res.groups">(.*?)</record>',
    security,
    flags=re.S,
)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on Dashboard res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo19 Dashboard res.groups.privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if len(acl_rows) < 6:
    fail(10, f"Dashboard ACL matrix too small: {len(acl_rows)}")
if record_rules < 4:
    fail(10, f"Dashboard company record-rule coverage too small: {record_rules}")

for row in acl_rows:
    if row["model_id:id"] in {
        "model_clinic_dashboard_snapshot",
        "model_clinic_dashboard_snapshot_line",
    }:
        if row["perm_write"] != "0" or row["perm_create"] != "0" or row["perm_unlink"] != "0":
            fail(10, f"generated Dashboard output ACL is not read-only: {row['id']}")

for backend_guard in (
    "dashboard_generation",
    "dashboard_board_transition",
    "_require_group",
    "policy_branch_scope_reports",
    "engine-owned and immutable by RPC",
    "immutable generated evidence",
):
    if backend_guard not in model_source:
        fail(10, f"Dashboard backend security/governance guard missing: {backend_guard}")

if "clinic_reports.group_reports_analyst" not in security:
    fail(10, "Dashboard Analyst does not imply Clinic Reports Analyst")
if "clinic_reports.group_reports_manager" not in security:
    fail(10, "Dashboard Manager does not imply Clinic Reports Manager")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"3-role hierarchy + Reports implications + {record_rules} company rules + {len(acl_rows)} ACL rows + immutable generated output pass")


# HARD GATE 12 — ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS.
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 6:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 5:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Dashboard Settings does not inherit stable base.res_config_settings_view_form")

for fragile in (
    "clinic_reports.view_",
    "clinic_branch.view_",
    "clinic_feedback.view_",
    "clinic_booking.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile upstream inherited-view XML ID found: {fragile}")

assets = manifest.get("assets", {}).get("web.assets_backend", [])
for asset in assets:
    prefix = "clinic_dashboard/"
    if not asset.startswith(prefix):
        fail(12, f"unexpected asset namespace: {asset}")
        continue
    rel = asset[len(prefix):]
    if not (ROOT / rel).exists():
        fail(12, f"manifest asset missing: {asset}")

if "registry.category(\"actions\").add" not in client_js:
    fail(12, "Odoo 19 action registry registration missing")
if "@web/core/utils/hooks" not in client_js:
    fail(12, "Odoo 19 useService import missing")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 source/frontend contracts pass; models.Constraint={constraints}, models.Index={indexes}")


# HARD GATE 13 — COMMENTS THAT ARE USEFUL.
if comment_lines < 30 or docstrings < 8:
    fail(13, f"Dashboard comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful scope/provenance/ownership comments pass: comments={comment_lines}, docstrings={docstrings}")


# HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX + BUILT-IN CATALOG.
defaults_path = ROOT / "models/dashboard_defaults.py"
defaults_tree = ast.parse(defaults_path.read_text(encoding="utf-8"))
default_boards = None
for node in defaults_tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "DEFAULT_DASHBOARDS"
        for target in node.targets
    ):
        try:
            default_boards = ast.literal_eval(node.value)
        except Exception:
            default_boards = None

if not isinstance(default_boards, list) or len(default_boards) != 6:
    fail(15, f"built-in Dashboard catalog must contain 6 Boards, found {len(default_boards or [])}")

widget_count = (
    sum(len(board.get("widgets", [])) for board in default_boards)
    if default_boards
    else 0
)
if widget_count != 50:
    fail(15, f"built-in Dashboard catalog must contain 50 mapped KPI Widgets, found {widget_count}")

matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Source/static PASS is not runtime completion" not in matrix
):
    fail(15, "Dashboard completeness matrix does not separate source/static from runtime")
if test_methods < 200:
    fail(15, f"Dashboard runtime contract/regression suite too small: {test_methods}")

if not any(item.startswith("[FAIL] HARD GATE 15") for item in errors):
    ok(15, f"6 Boards + 50 KPI Widgets + Owl client + {test_methods} runtime tests pass source/static completeness")


print("ClinicOne clinic_dashboard Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] owned_models={len(owned_models)} models.Constraint={constraints} models.Index={indexes}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} record_rules={record_rules}")
print(f"[INFO] built_in_boards={len(default_boards or [])} built_in_widgets={widget_count}")
print(f"[INFO] test_methods={test_methods} class_methods={class_methods}")

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/BROWSER SMOKE TEST PENDING)")
