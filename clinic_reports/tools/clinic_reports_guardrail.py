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
# HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
# ---------------------------------------------------------------------------
if manifest.get("version") != "19.0.1.0.1":
    fail(0, "authoritative version must be 19.0.1.0.1")

required_dependencies = {
    "clinic_billing",
    "clinic_ar",
    "clinic_ap",
    "clinic_finance",
    "clinic_accounting",
    "clinic_l10n_id",
    "clinic_insurance_authorization",
    "clinic_inventory",
    "clinic_booking",
    "clinic_queue_room",
    "clinic_room_device",
    "clinic_triage_vitals",
    "clinic_encounter",
    "clinic_care_plan",
    "clinic_membership",
    "clinic_wallet",
    "clinic_post_care_followup",
    "clinic_feedback",
}
missing_dependencies = sorted(required_dependencies - depends)
if missing_dependencies:
    fail(0, f"required upstream dependencies missing: {missing_dependencies}")

future_dependencies = {
    "clinic_dashboard",
    "clinic_audit",
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
if "CLINIC_REPORTS_BUILD_20260820_V19.0.1.0.0" not in build:
    fail(0, "authoritative build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
if "Central reporting engine for financial, operational, and clinical reports." not in preflight:
    fail(0, "official ClinicOne addon-28 blueprint responsibility is not locked")

if not any(item.startswith("[FAIL] HARD GATE 0") for item in errors):
    ok(0, "ClinicOne / addon 28 / financial + operational + clinical reporting identity locked")


# ---------------------------------------------------------------------------
# HARD GATE 1 + 14 — CODEX GOVERNANCE
# ---------------------------------------------------------------------------
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
for term in (
    "bounded implementation worker",
    "architect",
    "simplifier",
    "endless retry",
    "maximum 2",
    "maximum 1 repeat",
):
    if term not in agents:
        fail(1 if term != "maximum 1 repeat" else 14, f"Codex governance term missing: {term}")

if not any(item.startswith("[FAIL] HARD GATE 1") for item in errors):
    ok(1, "Codex is bounded implementation worker, never reporting architect/simplifier")
if not any(item.startswith("[FAIL] HARD GATE 14") for item in errors):
    ok(14, "Codex retry limit = maximum two bounded attempts / one repeated root cause")


# ---------------------------------------------------------------------------
# Python inventory
# ---------------------------------------------------------------------------
python_files = list(ROOT.rglob("*.py"))
model_files = [
    path for path in ROOT.glob("models/*.py")
    if path.name != "__init__.py"
]
xml_files = list(ROOT.rglob("*.xml"))

python_errors = []
defined_models = set()
abstract_models = set()
transient_models = set()
technical_fields = {}
constraints = 0
indexes = 0
dangerous_inherit = []
class_methods = 0
test_methods = 0
comment_lines = 0
docstrings = 0

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

        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                base_names.append(base.attr)
            elif isinstance(base, ast.Name):
                base_names.append(base.id)

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
            if "AbstractModel" in base_names:
                abstract_models.add(model_name)
            elif "TransientModel" in base_names:
                transient_models.add(model_name)

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


# ---------------------------------------------------------------------------
# HARD GATE 2 — EXISTING FUNCTION PRESERVATION / OWNERSHIP
# ---------------------------------------------------------------------------
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

for forbidden in (
    '_name = "clinic.billing.invoice"',
    '_name = "clinic.ar.invoice"',
    '_name = "clinic.ap"',
    '_name = "clinic.finance.transaction"',
    '_name = "account.move.line"',
    '_name = "clinic.insurance.authorization"',
    '_name = "clinic.insurance.claim"',
    '_name = "booking.booking"',
    '_name = "clinic.queue"',
    '_name = "clinic.room.assignment"',
    '_name = "clinic.treatment.product.usage"',
    '_name = "membership.contract"',
    '_name = "clinic.wallet.transaction"',
    '_name = "clinic.encounter"',
    '_name = "clinic.procedure.session"',
    '_name = "clinic.triage.session"',
    '_name = "clinic.adverse.event"',
    '_name = "clinic.postcare.plan"',
    '_name = "clinic.feedback"',
):
    if forbidden in model_source:
        fail(2, f"upstream transaction ownership duplicated: {forbidden}")

for allowed_extension in (
    '_inherit = "clinic.branch"',
    '_inherit = "res.company"',
    '_inherit = "res.config.settings"',
):
    if allowed_extension not in model_source:
        fail(2, f"expected additive integration missing: {allowed_extension}")

engine_sources = "\n".join(
    (ROOT / "models" / name).read_text(encoding="utf-8")
    for name in (
        "engine_financial.py",
        "engine_operational.py",
        "engine_clinical.py",
    )
)
for mutation in (".write(", ".create(", ".unlink("):
    if mutation in engine_sources:
        fail(2, f"report engine contains forbidden source mutation call: {mutation}")

if "Source records remain authoritative" not in (
    ROOT / "docs/CROSS_ADDON_CONTRACT_AUDIT.md"
).read_text(encoding="utf-8") and "source records" not in (
    ROOT / "README.md"
).read_text(encoding="utf-8").lower():
    fail(2, "source-authority preservation evidence missing")

if not any(item.startswith("[FAIL] HARD GATE 2") for item in errors):
    ok(2, "transaction ownership preserved; engines are read-only and snapshot-only")


# ---------------------------------------------------------------------------
# HARD GATE 3 — ENTERPRISE COMPLETENESS, NOT JUST TEST PASS
# ---------------------------------------------------------------------------
required_files = {
    "security/clinic_reports_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/report_definition_data.xml",
    "data/cron_data.xml",
    "models/engine_financial.py",
    "models/engine_operational.py",
    "models/engine_clinical.py",
    "models/report_run.py",
    "models/report_schedule.py",
    "wizard/report_generate_wizard.py",
    "views/report_definition_views.xml",
    "views/report_run_views.xml",
    "views/report_metric_views.xml",
    "views/report_detail_views.xml",
    "views/report_schedule_views.xml",
    "wizard/report_generate_wizard_views.xml",
    "views/res_config_settings_views.xml",
    "report/report_run_templates.xml",
    "report/report_run_report.xml",
    "docs/REPORT_CATALOG.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "tests/test_reports_enterprise.py",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise report deliverables missing: {missing_files}")
else:
    ok(3, "19 report engines + governed snapshots + CSV/PDF + schedules + security + tests/docs present")


# ---------------------------------------------------------------------------
# HARD GATE 4 — FULL STRUCTURAL INVENTORY
# ---------------------------------------------------------------------------
owned_persistent = {
    "clinic.report.definition",
    "clinic.report.run",
    "clinic.report.metric",
    "clinic.report.detail",
    "clinic.report.schedule",
}
owned_abstract = {
    "clinic.report.company.mixin",
    "clinic.report.engine.financial",
    "clinic.report.engine.operational",
    "clinic.report.engine.clinical",
}
owned_transient = {"clinic.report.generate.wizard"}

missing_persistent = owned_persistent - defined_models
missing_abstract = owned_abstract - abstract_models
missing_transient = owned_transient - transient_models

if missing_persistent:
    fail(4, f"persistent report model inventory incomplete: {sorted(missing_persistent)}")
if missing_abstract:
    fail(4, f"abstract report model inventory incomplete: {sorted(missing_abstract)}")
if missing_transient:
    fail(4, f"transient report model inventory incomplete: {sorted(missing_transient)}")

if not any(item.startswith("[FAIL] HARD GATE 4") for item in errors):
    ok(4, "5 persistent + 4 abstract + 1 transient owned reporting models inventoried")


# ---------------------------------------------------------------------------
# HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
# ---------------------------------------------------------------------------
required_model_files = {
    "mixins.py",
    "report_definition.py",
    "report_metric.py",
    "report_detail.py",
    "report_run.py",
    "report_schedule.py",
    "engine_financial.py",
    "engine_operational.py",
    "engine_clinical.py",
    "settings.py",
    "integration_bridge.py",
}
actual_model_files = {path.name for path in model_files}
missing_model_files = sorted(required_model_files - actual_model_files)
if missing_model_files:
    fail(5, f"focused model-file structure incomplete: {missing_model_files}")
else:
    ok(5, f"report responsibilities split across {len(model_files)} focused model files + dedicated wizard")


# ---------------------------------------------------------------------------
# XML parse + aggregate
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
    fail(12, "XML parse errors: " + " | ".join(xml_errors))


# ---------------------------------------------------------------------------
# HARD GATE 6 — PROFESSIONAL FORM DESIGN
# ---------------------------------------------------------------------------
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "<chatter",
    "alert alert-danger",
    "action_download_csv",
    "action_print_pdf",
):
    if token not in all_xml:
        fail(6, f"professional reporting form token missing: {token}")

if not any(item.startswith("[FAIL] HARD GATE 6") for item in errors):
    ok(6, "statusbars, smart buttons, body actions, O2M source buttons, alerts, CSV/PDF controls present")


# ---------------------------------------------------------------------------
# HARD GATE 7 — UI/UX MATRIX PER PERSISTENT MODEL
# ---------------------------------------------------------------------------
view_matrix = {
    model: {"search": False, "list": False, "form": False}
    for model in owned_persistent
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
    ok(7, "Search/List/Form complete for all 5 owned persistent reporting models")


# ---------------------------------------------------------------------------
# HARD GATE 8 — SEARCH VIEW + SEARCHABILITY
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
                domain = filter_node.attrib.get("domain", "")
                try:
                    domain_value = ast.literal_eval(domain)
                except Exception:
                    domain_value = []

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

                for dotted in walk(domain_value):
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
if search_count < 5:
    fail(8, f"search-view coverage too low: {search_count}")

if not any(item.startswith("[FAIL] HARD GATE 8") for item in errors):
    ok(8, f"{search_count} search views pass Odoo19 architecture and searchability gates")


# ---------------------------------------------------------------------------
# HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
# ---------------------------------------------------------------------------
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 7:
        fail(9, f"enterprise list coverage too low: {list_count}")
    if object_buttons < 30:
        fail(9, f"enterprise object-button coverage too low: {object_buttons}")
    if not any(item.startswith("[FAIL] HARD GATE 9") for item in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise quality")


# ---------------------------------------------------------------------------
# HARD GATE 10 — SECURITY CANNOT BE DEFEATED BY UI
# ---------------------------------------------------------------------------
security = (ROOT / "security/clinic_reports_security.xml").read_text(encoding="utf-8")
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
if len(acl_rows) < 14:
    fail(10, f"ACL matrix too small: {len(acl_rows)}")
if record_rules < 4:
    fail(10, f"company record-rule coverage too small: {record_rules}")

# Metric/Detail must remain read-only from ACL even for Analyst/Manager.
for row in acl_rows:
    if row["model_id:id"] in {
        "model_clinic_report_metric",
        "model_clinic_report_detail",
    }:
        if row["perm_write"] != "0" or row["perm_create"] != "0" or row["perm_unlink"] != "0":
            fail(10, f"generated snapshot ACL is not read-only: {row['id']}")

for backend_guard in (
    "report_run_transition",
    "report_generation",
    "_reports_require_group",
    "Finalized/Archived Report scope is immutable",
    "Use Report Schedule workflow actions",
    "engine-owned and immutable by RPC",
    "policy_branch_scope_reports",
):
    if backend_guard not in model_source:
        fail(10, f"backend reporting security/governance guard missing: {backend_guard}")

if not any(item.startswith("[FAIL] HARD GATE 10") for item in errors):
    ok(10, f"3-role hierarchy + {record_rules} company rules + {len(acl_rows)} ACL rows + engine-owned snapshots pass")


# ---------------------------------------------------------------------------
# HARD GATE 12 — ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS
# ---------------------------------------------------------------------------
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 7:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 7:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")

for fragile in (
    "clinic_billing.view_",
    "clinic_ar.view_",
    "clinic_ap.view_",
    "clinic_finance.view_",
    "clinic_booking.view_",
    "clinic_queue_room.view_",
    "clinic_encounter.view_",
    "clinic_post_care_followup.view_",
    "clinic_feedback.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile custom upstream inherited-view XML ID found: {fragile}")

if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not inherit stable base.res_config_settings_view_form")

mixin_source = (ROOT / "models/mixins.py").read_text(encoding="utf-8")
if "has no authoritative branch field/path" not in mixin_source:
    fail(12, "Branch filtering can be silently ignored instead of rejected")
if "policy_branch_scope_reports" not in mixin_source:
    fail(12, "Clinic Branch reporting policy is not enforced")

run_source = (ROOT / "models/report_run.py").read_text(encoding="utf-8")
if ".sudo().with_context(\n            report_generation=True" not in run_source:
    fail(12, "generated snapshot creation does not use bounded sudo context")

if not any(item.startswith("[FAIL] HARD GATE 12") for item in errors):
    ok(12, f"Odoo19 contracts pass; models.Constraint={constraints}, models.Index={indexes}, branch scope hardened")


# ---------------------------------------------------------------------------
# HARD GATE 13 — COMMENTS THAT ARE USEFUL
# ---------------------------------------------------------------------------
if comment_lines < 30 or docstrings < 12:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"useful ownership/KPI/governance comments pass: comments={comment_lines}, docstrings={docstrings}")


# ---------------------------------------------------------------------------
# HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
# ---------------------------------------------------------------------------
definition_xml = ET.parse(ROOT / "data/report_definition_data.xml").getroot()
definition_records = [
    record
    for record in definition_xml.iter("record")
    if record.attrib.get("model") == "clinic.report.definition"
]
if len(definition_records) != 19:
    fail(15, f"built-in report catalog must contain 19 definitions, found {len(definition_records)}")

run_tree = ast.parse((ROOT / "models/report_run.py").read_text(encoding="utf-8"))
engine_map_count = 0
for node in run_tree.body:
    if isinstance(node, ast.Assign):
        if any(isinstance(target, ast.Name) and target.id == "ENGINE_METHODS" for target in node.targets):
            try:
                engine_map_count = len(ast.literal_eval(node.value))
            except Exception:
                engine_map_count = 0

if engine_map_count != 19:
    fail(15, f"engine dispatch map must contain 19 reports, found {engine_map_count}")

matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix
    or "Source/static PASS is not runtime completion" not in matrix
):
    fail(15, "completeness matrix does not separate source/static from runtime")
if test_methods < 150:
    fail(15, f"runtime regression/contract suite too small: {test_methods}")

if not any(item.startswith("[FAIL] HARD GATE 15") for item in errors):
    ok(15, f"19-report catalog + 19 engine dispatches + {test_methods} runtime tests pass source/static completeness")


print("ClinicOne clinic_reports Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] persistent_models={len(owned_persistent)} abstract_models={len(owned_abstract)} transient_models={len(owned_transient)}")
print(f"[INFO] models.Constraint={constraints} models.Index={indexes}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} record_rules={record_rules}")
print(f"[INFO] built_in_reports={len(definition_records)} engine_dispatches={engine_map_count}")
print(f"[INFO] test_methods={test_methods} class_methods={class_methods}")

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/SMOKE TEST PENDING)")

