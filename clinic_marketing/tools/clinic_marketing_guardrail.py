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
    fail(0, "authoritative repair version must be 19.0.1.0.1")

required_dependencies = {
    "mass_mailing",
    "website",
    "clinic_base",
    "clinic_branch",
    "clinic_patient",
    "clinic_treatment_catalog",
    "clinic_booking",
    "clinic_package",
    "clinic_membership",
    "clinic_billing",
    "clinic_feedback",
    "clinic_ecommerce",
    "clinic_portal",
}
missing_dependencies = sorted(required_dependencies - depends)
if missing_dependencies:
    fail(0, f"required Marketing dependencies missing: {missing_dependencies}")

future_dependencies = {
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
if "CLINIC_MARKETING_BUILD_20260821_V19.0.1.0.1" not in build:
    fail(0, "authoritative Marketing build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
official = "Manages campaigns, promotions, and communication with patients via email/WhatsApp."
if official not in preflight:
    fail(0, "official addon-32 blueprint responsibility is not locked")

if not any(line.startswith("[FAIL] HARD GATE 0") for line in errors):
    ok(0, "ClinicOne addon 32 Marketing identity and official Email/WhatsApp scope locked")


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
    fail(14, "same-root-cause retry limit missing")

if not any(line.startswith("[FAIL] HARD GATE 1") for line in errors):
    ok(1, "Codex is bounded implementation worker, not patient/pricing/email/gateway architect")
if not any(line.startswith("[FAIL] HARD GATE 14") for line in errors):
    ok(14, "Codex retry limit locked to two bounded attempts / one repeated root cause")


# Python inventory.
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

defined_models = set()
owned_models = set()
technical_fields = {}
constraints = []
indexes = []
dangerous_inherit = []
field_method_collisions = []
env_proxy_isinstance = []
python_errors = []
load_time_symbol_issues = []
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

    # Python syntax compilation does not evaluate class decorators. A file can
    # therefore compile successfully yet fail during Odoo import, e.g. using
    # `@api.model` without importing `api`. Validate load-time Odoo symbols.
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

    def _root_name(expr):
        current = expr
        while isinstance(current, (ast.Attribute, ast.Call, ast.Subscript)):
            if isinstance(current, ast.Attribute):
                current = current.value
            elif isinstance(current, ast.Call):
                current = current.func
            else:
                current = current.value
        return current.id if isinstance(current, ast.Name) else None

    required_odoo_symbols = {"api", "fields", "models", "_"}
    for top in tree.body:
        if not isinstance(top, ast.ClassDef):
            continue

        for expression in list(top.bases) + list(top.decorator_list):
            root_name = _root_name(expression)
            if (
                root_name in required_odoo_symbols
                and root_name not in imported_names
            ):
                load_time_symbol_issues.append(
                    f"{path.relative_to(ROOT)}:{top.lineno}:"
                    f"class {top.name} requires missing import `{root_name}`"
                )

        for member in top.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in member.decorator_list:
                    root_name = _root_name(decorator)
                    if (
                        root_name in required_odoo_symbols
                        and root_name not in imported_names
                    ):
                        load_time_symbol_issues.append(
                            f"{path.relative_to(ROOT)}:{member.lineno}:"
                            f"{top.name}.{member.name} decorator requires "
                            f"missing import `{root_name}`"
                        )
            elif isinstance(member, ast.Assign) and isinstance(member.value, ast.Call):
                root_name = _root_name(member.value.func)
                if (
                    root_name in required_odoo_symbols
                    and root_name not in imported_names
                ):
                    load_time_symbol_issues.append(
                        f"{path.relative_to(ROOT)}:{member.lineno}:"
                        f"class assignment requires missing import `{root_name}`"
                    )

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        if ast.get_docstring(node):
            docstrings += 1

        model_name = None
        inherit_value = None
        explicit_name = False
        class_fields = set()
        method_names = set()

        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods += 1
                method_names.add(stmt.name)
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
                        if value.startswith("clinic.marketing."):
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

        collision = class_fields.intersection(method_names)
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

    # Detect the Odoo anti-pattern self.env["model"] -> variable -> isinstance(..., variable).
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
                and value.value.value.id == "self"
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
                    f"{path.relative_to(ROOT)}:{function.name}:{node.lineno}:{second.id}"
                )

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))
if load_time_symbol_issues:
    fail(
        12,
        "Python class-load symbol/import errors: "
        + " | ".join(load_time_symbol_issues),
    )


# HARD GATE 2 — EXISTING FUNCTION PRESERVATION.
model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in model_files
)

for forbidden in (
    '_name = "clinic.patient"',
    '_name = "clinic.branch"',
    '_name = "booking.booking"',
    '_name = "membership.contract"',
    '_name = "clinic.feedback"',
    '_name = "clinic.billing.voucher.program"',
    '_name = "clinic.package.voucher.batch"',
    '_name = "clinic.treatment.pricelist.item"',
    '_name = "clinic.ecommerce.catalog.item"',
    '_name = "mailing.mailing"',
    '_name = "mailing.trace"',
):
    if forbidden in model_source:
        fail(2, f"upstream owner model duplicated: {forbidden}")

for extension in (
    '_inherit = "res.company"',
    '_inherit = "res.config.settings"',
    '_inherit = "res.partner"',
    '_inherit = "clinic.patient"',
    '_inherit = "clinic.branch"',
    '_inherit = "mailing.mailing"',
    '_inherit = "clinic.ecommerce.catalog.item"',
):
    if extension not in model_source:
        fail(2, f"expected additive extension missing: {extension}")

campaign_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "models").glob("campaign*.py"))
    if not path.name.startswith("0")
)
if 'self.env["mailing.mailing"].create' not in campaign_source:
    fail(2, "native mailing.mailing delegation is missing")
if "mailing.action_put_in_queue()" not in campaign_source:
    fail(2, "native Email Marketing queue action is not used")
if "mailing.trace" not in campaign_source:
    fail(2, "native mailing.trace synchronization is missing")

for forbidden_mutation in (
    'self.env["booking.booking"].write',
    'self.env["membership.contract"].write',
    'self.env["clinic.feedback"].write',
    'self.env["clinic.billing.voucher.program"].write',
    'self.env["clinic.package.voucher.batch"].write',
    'self.env["clinic.treatment.pricelist.item"].write',
    'self.env["clinic.ecommerce.catalog.item"].write',
):
    if forbidden_mutation in model_source:
        fail(2, f"Marketing directly mutates an owner workflow: {forbidden_mutation}")

if not any(line.startswith("[FAIL] HARD GATE 2") for line in errors):
    ok(2, "patient/pricing/voucher/Booking/Feedback ownership preserved; Odoo mass_mailing remains Email engine")


# HARD GATE 3 — ENTERPRISE COMPLETENESS.
required_files = {
    "models/preference.py",
    "models/segment.py",
    "models/promotion.py",
    "models/campaign.py",
    "models/campaign_audience.py",
    "models/campaign_delivery.py",
    "models/recipient.py",
    "models/message.py",
    "models/settings.py",
    "models/integration_bridge.py",
    "security/clinic_marketing_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/cron_data.xml",
    "views/marketing_preference_views.xml",
    "views/marketing_segment_views.xml",
    "views/marketing_promotion_views.xml",
    "views/marketing_campaign_views.xml",
    "views/marketing_recipient_views.xml",
    "views/marketing_message_views.xml",
    "views/res_config_settings_views.xml",
    "views/menu_views.xml",
    "tests/test_marketing_enterprise.py",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/DATABASE_IDENTIFIER_ORM_NAMING_SAFETY.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/RUNTIME_REPAIR_20260821_01.md",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise Marketing deliverables missing: {missing_files}")
else:
    ok(3, "consent + segmentation + promotions + campaign + recipients + Email delegation + WhatsApp queue + tests/docs present")


# HARD GATE 4 — FULL STRUCTURAL INVENTORY.
expected_owned = {
    "clinic.marketing.preference",
    "clinic.marketing.segment",
    "clinic.marketing.promotion",
    "clinic.marketing.campaign",
    "clinic.marketing.recipient",
    "clinic.marketing.message",
}
if owned_models != expected_owned:
    fail(
        4,
        f"owned model inventory mismatch: expected={sorted(expected_owned)}, found={sorted(owned_models)}",
    )
else:
    ok(4, "6 owned Marketing models plus 7 additive integrations inventoried")


# HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE.
required_model_files = {
    "preference.py",
    "segment.py",
    "promotion.py",
    "campaign.py",
    "recipient.py",
    "message.py",
    "settings.py",
    "integration_bridge.py",
}
actual_model_files = {path.name for path in model_files}
missing_model_files = sorted(required_model_files - actual_model_files)
if missing_model_files:
    fail(5, f"focused Marketing model structure incomplete: {missing_model_files}")

max_lines = max(
    (
        len(path.read_text(encoding="utf-8").splitlines()),
        path.name,
    )
    for path in model_files
)
if max_lines[0] > 650:
    fail(5, f"single Marketing model file exceeds manual-maintenance threshold: {max_lines}")

if not any(line.startswith("[FAIL] HARD GATE 5") for line in errors):
    ok(5, f"Marketing responsibilities split across {len(model_files)} focused model files; largest={max_lines[1]}:{max_lines[0]} lines")


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
    "alert alert-info",
    "action_prepare_audience",
    "action_launch",
    "action_open_whatsapp",
    "action_open_source",
):
    if token not in all_xml:
        fail(6, f"professional Marketing UI token missing: {token}")

if "view_marketing_campaign_kanban" not in all_xml:
    fail(6, "Campaign Kanban is missing")
if "view_marketing_recipient_pivot" not in all_xml or "view_marketing_recipient_graph" not in all_xml:
    fail(6, "Recipient Pivot/Graph analysis is missing")

if not any(line.startswith("[FAIL] HARD GATE 6") for line in errors):
    ok(6, "statusbars, smart/body/O2M actions, Campaign Kanban, Recipient Pivot/Graph are present")


# HARD GATE 7 — UI/UX MATRIX.
view_matrix = {
    model: {"search": False, "list": False, "form": False}
    for model in expected_owned
}
for path in xml_files:
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue
        model_node = record.find("./field[@name='model']")
        arch = record.find("./field[@name='arch']")
        if model_node is None or arch is None:
            continue
        model = (model_node.text or "").strip()
        if model not in view_matrix:
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
    ok(7, "Search/List/Form complete for all 6 owned Marketing models")


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
                    meta = technical_fields.get(model, {}).get(base)
                    if meta and meta["computed"] and not meta["store"] and not meta["search"]:
                        unsearchable.append(
                            f"{path.relative_to(ROOT)}:{model}.{base}:{filter_node.attrib.get('name')}"
                        )

if search_violations:
    fail(8, "Odoo19 Search architecture violation: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable field used in Search domain: " + " | ".join(unsearchable))
if search_count < 6:
    fail(8, f"Marketing Search View coverage too low: {search_count}")

if not any(line.startswith("[FAIL] HARD GATE 8") for line in errors):
    ok(8, f"{search_count} Marketing Search Views pass Odoo19 architecture/searchability gates")


# HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY.
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 8:
        fail(9, f"enterprise Marketing list coverage too low: {list_count}")
    if object_buttons < 45:
        fail(9, f"enterprise Marketing action-button coverage too low: {object_buttons}")
    if not any(line.startswith("[FAIL] HARD GATE 9") for line in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise quality")


# HARD GATE 10 — SECURITY CANNOT BE DEFEATED BY UI.
security = (ROOT / "security/clinic_marketing_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acl_rows = list(csv.DictReader(handle))

group_blocks = re.findall(
    r'<record[^>]*model="res.groups">(.*?)</record>',
    security,
    flags=re.S,
)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on Marketing res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo19 Marketing privilege hierarchy missing")

record_rules = security.count('model="ir.rule"')
if record_rules < 6:
    fail(10, f"company record-rule coverage too small: {record_rules}")
if len(acl_rows) < 17:
    fail(10, f"Marketing ACL matrix too small: {len(acl_rows)}")

for row in acl_rows:
    if row["group_id:id"] in {"base.group_public", "base.group_portal"}:
        fail(10, f"external/public backend ACL is forbidden: {row['id']}")

for backend_guard in (
    "marketing_segment_transition",
    "marketing_promotion_transition",
    "marketing_campaign_transition",
    "marketing_audience_build",
    "marketing_delivery_sync",
    "marketing_message_build",
    "marketing_message_transition",
    "_require_coordinator",
    "_require_manager",
    "policy_branch_scope_marketing",
):
    if backend_guard not in model_source:
        fail(10, f"backend Marketing security/governance guard missing: {backend_guard}")

if "clinic_marketing_require_explicit_consent" not in model_source:
    fail(10, "explicit patient channel-consent policy is missing")
if 'default=True' not in (ROOT / "models/settings.py").read_text(encoding="utf-8").split(
    "clinic_marketing_require_explicit_consent", 1
)[1].split(")", 1)[0]:
    fail(10, "explicit marketing consent must default to enabled")

if "mass_mailing.group_mass_mailing_user" not in security:
    fail(10, "Marketing Coordinator does not imply Odoo Email Marketing User")
if "mass_mailing.group_mass_mailing_campaign" not in security:
    fail(10, "Marketing Manager does not imply Odoo Email Marketing Campaign group")

if not any(line.startswith("[FAIL] HARD GATE 10") for line in errors):
    ok(10, f"3-role hierarchy + explicit consent + branch guard + {record_rules} company rules + {len(acl_rows)} ACL rows pass")


# HARD GATE 11 — DATABASE IDENTIFIER & ORM NAMING SAFETY.
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

for model_name in sorted(expected_owned):
    if not model_re.match(model_name):
        identifier_issues.append(f"unsafe model _name: {model_name}")
    table = model_name.replace(".", "_")
    if len(table.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"table exceeds PostgreSQL 63 bytes: {table}")

    for field_name in technical_fields.get(model_name, {}):
        if not snake_re.match(field_name):
            identifier_issues.append(f"unsafe field name: {model_name}.{field_name}")
        if len(field_name.encode("ascii", errors="ignore")) > 63:
            identifier_issues.append(f"field exceeds 63 bytes: {model_name}.{field_name}")
        if field_name.lower() in reserved_sql:
            identifier_issues.append(f"reserved SQL field name: {model_name}.{field_name}")

for model_name, attr_name in constraints + indexes:
    if model_name not in expected_owned:
        continue
    table = model_name.replace(".", "_")
    generated = f"{table}_{attr_name.lstrip('_')}"
    if len(attr_name.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"Constraint/Index Python attr too long: {attr_name}")
    if len(generated.encode("ascii", errors="ignore")) > 63:
        identifier_issues.append(f"generated identifier exceeds 63 bytes: {generated}")

# Explicit M2M relation identifiers.
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
        relation = None
        # Odoo Many2many positional arg #2 is relation.
        if len(node.args) >= 2:
            try:
                candidate = ast.literal_eval(node.args[1])
            except Exception:
                candidate = None
            if isinstance(candidate, str):
                relation = candidate
        for kw in node.keywords:
            if kw.arg == "relation":
                try:
                    candidate = ast.literal_eval(kw.value)
                except Exception:
                    candidate = None
                if isinstance(candidate, str):
                    relation = candidate
        if relation and len(relation.encode("ascii", errors="ignore")) > 63:
            identifier_issues.append(f"Many2many relation exceeds 63 bytes: {relation}")

if field_method_collisions:
    identifier_issues.extend(
        f"field/method collision: {item}" for item in field_method_collisions
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
    ok(11, "6 model/table namespaces, fields, constraints/indexes, M2M relations and ORM method namespaces pass safety")


# HARD GATE 12 — ODOO 19 / HUMAN-FRIENDLY SOURCE CONTRACTS.
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
if dangerous_inherit:
    fail(12, f"dangerous list-valued _inherit classes: {dangerous_inherit}")
if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not inherit stable base.res_config_settings_view_form")

for fragile in (
    "clinic_patient.view_",
    "clinic_booking.view_",
    "clinic_billing.view_",
    "clinic_ecommerce.view_",
    "mass_mailing.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile upstream custom inherited-view XML ID found: {fragile}")

# Odoo 19 Email Marketing delegation contracts.
for token in (
    "mailing.mailing",
    "mailing.trace",
    "action_put_in_queue",
    "action_cancel",
    "use_exclusion_list",
    "mailing_model_id",
    "mailing_domain",
    "utm.campaign",
):
    if token not in campaign_source:
        fail(12, f"native Odoo Email Marketing contract missing: {token}")

# Odoo 19 CE Contact compatibility: this ClinicOne baseline deliberately keeps
# mobile on clinic.patient; direct res.partner.mobile access is unsafe.
if ".partner_id.mobile" in model_source or "partner.mobile" in model_source:
    fail(12, "unsafe res.partner.mobile access found; use clinic.patient.mobile / partner.phone")

if "https://wa.me/" not in (ROOT / "models/message.py").read_text(encoding="utf-8"):
    fail(12, "manual WhatsApp handoff contract is missing")
if "_dispatch_via_gateway" not in (ROOT / "models/message.py").read_text(encoding="utf-8"):
    fail(12, "provider-neutral WhatsApp extension hook is missing")

if len(constraints) < 7 or len(indexes) < 6:
    fail(12, f"models.Constraint/Index coverage insufficient: constraints={len(constraints)}, indexes={len(indexes)}")

if not any(line.startswith("[FAIL] HARD GATE 12") for line in errors):
    ok(12, f"Odoo19 source/view/email contracts pass; models.Constraint={len(constraints)}, models.Index={len(indexes)}")


# HARD GATE 13 — COMMENTS THAT ARE USEFUL.
if comment_lines < 35 or docstrings < 10:
    fail(13, f"comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"ownership/consent/security comments pass: comments={comment_lines}, docstrings={docstrings}")


# HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX.
matrix_doc = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
if (
    "Odoo 19 runtime installation | PENDING" not in matrix_doc
    or "Source/static PASS is not runtime completion" not in matrix_doc
):
    fail(15, "completeness matrix does not separate source/static and runtime")

if test_methods < 300:
    fail(15, f"runtime contract/regression suite too small: {test_methods}")

if "record_count" not in (ROOT / "models/recipient.py").read_text(encoding="utf-8"):
    fail(15, "Recipient robust Pivot/Graph measure field missing")

for owner_source in (
    "clinic.billing.voucher.program",
    "clinic.package.voucher.batch",
    "clinic.treatment.pricelist.item",
    "clinic.ecommerce.catalog.item",
):
    if owner_source not in (ROOT / "models/promotion.py").read_text(encoding="utf-8"):
        fail(15, f"Promotion provenance source missing: {owner_source}")

if not any(line.startswith("[FAIL] HARD GATE 15") for line in errors):
    ok(15, f"6-model Marketing suite + native Email + governed WhatsApp + {test_methods} tests pass source/static completeness")


print("ClinicOne clinic_marketing Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] owned_models={len(expected_owned)} models.Constraint={len(constraints)} models.Index={len(indexes)}")
print(f"[INFO] search_views={search_count} acl_rows={len(acl_rows)} record_rules={record_rules}")
print(f"[INFO] test_methods={test_methods} class_methods={class_methods} comments={comment_lines} docstrings={docstrings}")

for line in passes:
    print(line)
for line in errors:
    print(line)

if errors:
    print("RESULT: FAIL")
    sys.exit(1)

print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/EMAIL-WHATSAPP SMOKE TEST PENDING)")

