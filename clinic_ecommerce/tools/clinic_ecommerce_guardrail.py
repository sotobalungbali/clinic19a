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
# HARD GATE 0 - Project Identity Preflight
# ---------------------------------------------------------------------------
if manifest.get("version") != "19.0.1.0.0":
    fail(0, "authoritative version must be 19.0.1.0.0")

required = {
    "website_sale",
    "payment",
    "clinic_base",
    "clinic_branch",
    "clinic_patient",
    "clinic_treatment_catalog",
    "clinic_booking",
    "clinic_package",
    "clinic_membership",
}
missing = sorted(required - depends)
if missing:
    fail(0, f"required eCommerce dependencies missing: {missing}")

future = {
    "clinic_portal",
    "clinic_marketing",
    "clinic_telemedicine_secure_messaging",
    "clinic_incident_event",
    "clinic_quality",
    "clinic_integration_api",
    "clinic_audit",
    "clinic_analytics",
}
found_future = sorted(future.intersection(depends))
if found_future:
    fail(0, f"future ClinicOne dependencies forbidden: {found_future}")

build = (ROOT / "BUILD_ID.txt").read_text(encoding="utf-8")
if "CLINIC_ECOMMERCE_BUILD_20260821_V19.0.1.0.0" not in build:
    fail(0, "authoritative eCommerce build marker missing")

preflight = (ROOT / "docs/PROJECT_IDENTITY_PREFLIGHT.md").read_text(encoding="utf-8")
if "Odoo 19 Website Sale" not in preflight:
    fail(0, "Website Sale ownership boundary is not locked")

if not any(x.startswith("[FAIL] HARD GATE 0") for x in errors):
    ok(0, "ClinicOne addon 30 identity and Odoo Website Sale ownership boundary locked")

# ---------------------------------------------------------------------------
# HARD GATE 1 + 14 - Codex governance
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
if not any(x.startswith("[FAIL] HARD GATE 1") for x in errors):
    ok(1, "Codex remains bounded implementation worker, never commerce architect/simplifier")
if not any(x.startswith("[FAIL] HARD GATE 14") for x in errors):
    ok(14, "Codex retry limit = maximum two bounded attempts / one same-root-cause repeat")

# ---------------------------------------------------------------------------
# Source inventory
# ---------------------------------------------------------------------------
python_files = list(ROOT.rglob("*.py"))
xml_files = list(ROOT.rglob("*.xml"))
model_files = [p for p in ROOT.glob("models/*.py") if p.name != "__init__.py"]

python_errors = []
defined_models = set()
technical_fields = {}
constraints = 0
indexes = 0
dangerous_inherit = []
comment_lines = 0
docstrings = 0
test_methods = 0
class_methods = 0

for path in python_files:
    source = path.read_text(encoding="utf-8")
    comment_lines += sum(1 for line in source.splitlines() if line.strip().startswith("#"))
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
                    fn = stmt.value.func
                    if (
                        isinstance(fn, ast.Attribute)
                        and isinstance(fn.value, ast.Name)
                        and fn.value.id == "models"
                    ):
                        if fn.attr == "Constraint":
                            constraints += 1
                        elif fn.attr == "Index":
                            indexes += 1
        if model_name:
            defined_models.add(model_name)
        technical_model = model_name or (
            inherit_value if isinstance(inherit_value, str) else None
        )
        if technical_model:
            fmap = technical_fields.setdefault(technical_model, {})
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
                    continue
                fn = stmt.value.func
                if not (
                    isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == "fields"
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
                    fmap[target.id] = {
                        "computed": computed,
                        "store": stored,
                        "search": searchable,
                    }
        if isinstance(inherit_value, list) and not explicit_name:
            dangerous_inherit.append(f"{path.relative_to(ROOT)}::{node.name}")

if python_errors:
    fail(12, "Python syntax errors: " + " | ".join(python_errors))

model_source = "\n".join(p.read_text(encoding="utf-8") for p in model_files)
controller_source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "controllers").glob("*.py"))

# ---------------------------------------------------------------------------
# HARD GATE 2 - Existing Function Preservation
# ---------------------------------------------------------------------------
for forbidden in (
    '_name = "sale.order"',
    '_name = "sale.order.line"',
    '_name = "payment.transaction"',
    '_name = "booking.booking"',
    '_name = "clinic.package.allocation"',
    '_name = "membership.contract"',
    '_name = "clinic.treatment"',
    '_name = "clinic.package"',
    '_name = "membership.plan"',
):
    if forbidden in model_source:
        fail(2, f"upstream owner model duplicated: {forbidden}")

for expected in (
    '_inherit = "sale.order"',
    '_inherit = "sale.order.line"',
    '_inherit = "payment.transaction"',
    '_inherit = "booking.booking"',
    '_inherit = "clinic.package.allocation"',
    '_inherit = "membership.contract"',
):
    if expected not in model_source:
        fail(2, f"expected additive owner bridge missing: {expected}")

fulfillment_source = (ROOT / "models/fulfillment.py").read_text(encoding="utf-8")
if "membership_contract_id" not in fulfillment_source:
    fail(2, "Membership provenance missing")
if "contract.action_confirm()" in fulfillment_source:
    fail(2, "eCommerce must not call Membership action_confirm() and create a duplicate invoice")
if "run.action_generate" in model_source:
    fail(2, "eCommerce must not become a reporting engine")
if not any(x.startswith("[FAIL] HARD GATE 2") for x in errors):
    ok(2, "Odoo Sale/Payment and Clinic owner workflows preserved; no duplicate Membership invoice workflow")

# ---------------------------------------------------------------------------
# HARD GATE 3 - Enterprise completeness
# ---------------------------------------------------------------------------
required_files = {
    "models/catalog_item.py",
    "models/fulfillment.py",
    "models/sale_order.py",
    "models/sale_order_line.py",
    "models/payment_transaction.py",
    "models/settings.py",
    "models/source_bridges.py",
    "controllers/main.py",
    "wizard/catalog_discovery_wizard.py",
    "security/clinic_ecommerce_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "views/catalog_item_views.xml",
    "views/fulfillment_views.xml",
    "views/sale_order_views.xml",
    "views/res_config_settings_views.xml",
    "views/website_templates.xml",
    "views/menu_views.xml",
    "wizard/catalog_discovery_wizard_views.xml",
    "static/src/scss/clinic_shop.scss",
    "tests/test_ecommerce_enterprise.py",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
}
missing_files = sorted(rel for rel in required_files if not (ROOT / rel).exists())
if missing_files:
    fail(3, f"enterprise eCommerce deliverables missing: {missing_files}")
else:
    ok(3, "catalog + storefront + native cart/checkout integration + fulfillment queue + source bridges + tests/docs present")

# ---------------------------------------------------------------------------
# HARD GATE 4 - Full structural inventory
# ---------------------------------------------------------------------------
owned = {"clinic.ecommerce.catalog.item", "clinic.ecommerce.fulfillment"}
missing_owned = owned - defined_models
if missing_owned:
    fail(4, f"owned persistent model inventory incomplete: {sorted(missing_owned)}")
if "clinic.ecommerce.catalog.discovery.wizard" not in defined_models:
    fail(4, "Catalog Discovery transient model missing")
if not any(x.startswith("[FAIL] HARD GATE 4") for x in errors):
    ok(4, "2 persistent owner models + discovery wizard + Odoo/Clinic additive bridges inventoried")

# ---------------------------------------------------------------------------
# HARD GATE 5 - Human-friendly structure
# ---------------------------------------------------------------------------
expected_model_files = {
    "catalog_item.py", "fulfillment.py", "sale_order.py", "sale_order_line.py",
    "payment_transaction.py", "settings.py", "source_bridges.py",
}
actual = {p.name for p in model_files}
missing = sorted(expected_model_files - actual)
if missing:
    fail(5, f"focused model-file structure incomplete: {missing}")
else:
    ok(5, f"responsibilities split across {len(model_files)} focused model files + controller + wizard")

# ---------------------------------------------------------------------------
# XML aggregate
# ---------------------------------------------------------------------------
xml_errors = []
all_xml_parts = []
for path in xml_files:
    text = path.read_text(encoding="utf-8")
    all_xml_parts.append(text)
    try:
        ET.parse(path)
    except Exception as exc:
        xml_errors.append(f"{path.relative_to(ROOT)}: {exc}")
all_xml = "\n".join(all_xml_parts)
if xml_errors:
    fail(12, "XML/QWeb parse errors: " + " | ".join(xml_errors))

# ---------------------------------------------------------------------------
# HARD GATE 6 - Professional form/storefront design
# ---------------------------------------------------------------------------
for token in (
    'widget="statusbar"',
    "oe_stat_button",
    "btn-primary",
    'class="d-flex gap-2',
    "alert alert-warning",
    "action_open_website",
    "action_process",
    "action_open_booking",
):
    if token not in all_xml:
        fail(6, f"professional eCommerce UI token missing: {token}")
for token in (
    "/clinic/shop",
    "/clinic/shop/item/",
    "/clinic/shop/add/",
    "_cart_add(",
):
    if token not in controller_source:
        fail(6, f"governed storefront contract missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 6") for x in errors):
    ok(6, "statusbars/smart/body/O2M actions plus governed public storefront and native cart delegation present")

# ---------------------------------------------------------------------------
# HARD GATE 7 - UI/UX matrix
# ---------------------------------------------------------------------------
view_matrix = {model: {"search": False, "list": False, "form": False} for model in owned}
for path in xml_files:
    root = ET.parse(path).getroot()
    for rec in root.iter("record"):
        if rec.attrib.get("model") != "ir.ui.view":
            continue
        model_node = rec.find("./field[@name='model']")
        arch_node = rec.find("./field[@name='arch']")
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
    ok(7, "Search/List/Form complete for both persistent eCommerce owner models; Fulfillment also has Pivot/Graph")

# ---------------------------------------------------------------------------
# HARD GATE 8 - Search View mandatory and searchable domains
# ---------------------------------------------------------------------------
search_count = 0
search_violations = []
unsearchable = []
for path in xml_files:
    root = ET.parse(path).getroot()
    for rec in root.iter("record"):
        if rec.attrib.get("model") != "ir.ui.view":
            continue
        model_node = rec.find("./field[@name='model']")
        model = (model_node.text or "").strip() if model_node is not None else ""
        for search in rec.findall(".//search"):
            search_count += 1
            if search.attrib:
                search_violations.append(f"{path.relative_to(ROOT)} search attrs={dict(search.attrib)}")
            for child in list(search):
                if child.tag == "group" and child.attrib:
                    search_violations.append(f"{path.relative_to(ROOT)} group attrs={dict(child.attrib)}")
            for flt in search.findall(".//filter[@domain]"):
                try:
                    domain = ast.literal_eval(flt.attrib.get("domain", ""))
                except Exception:
                    domain = []
                def walk(obj):
                    if isinstance(obj, tuple) and len(obj) >= 3 and isinstance(obj[0], str):
                        yield obj[0]
                    elif isinstance(obj, (list, tuple)):
                        for item in obj:
                            yield from walk(item)
                for dotted in walk(domain):
                    base = dotted.split(".", 1)[0]
                    meta = technical_fields.get(model, {}).get(base)
                    if meta and meta["computed"] and not meta["store"] and not meta["search"]:
                        unsearchable.append(f"{model}.{base}:{flt.attrib.get('name')}")
if search_violations:
    fail(8, "Odoo19 search architecture violations: " + " | ".join(search_violations))
if unsearchable:
    fail(8, "computed non-searchable fields used in search domains: " + " | ".join(unsearchable))
if search_count < 2:
    fail(8, f"search-view coverage too low: {search_count}")
if not any(x.startswith("[FAIL] HARD GATE 8") for x in errors):
    ok(8, f"{search_count} eCommerce search views pass Odoo19 architecture/searchability gates")

# ---------------------------------------------------------------------------
# HARD GATE 9 - Enterprise list quality
# ---------------------------------------------------------------------------
if "<tree" in all_xml or "</tree>" in all_xml:
    fail(9, "legacy <tree> architecture found")
else:
    list_count = all_xml.count("<list")
    object_buttons = len(re.findall(r'<button[^>]+type="object"', all_xml))
    if list_count < 4:
        fail(9, f"list coverage too low: {list_count}")
    if object_buttons < 30:
        fail(9, f"object-button coverage too low: {object_buttons}")
    if not any(x.startswith("[FAIL] HARD GATE 9") for x in errors):
        ok(9, f"{list_count} list tags and {object_buttons} object buttons pass enterprise quality")

# ---------------------------------------------------------------------------
# HARD GATE 10 - Security cannot be defeated by UI
# ---------------------------------------------------------------------------
security = (ROOT / "security/clinic_ecommerce_security.xml").read_text(encoding="utf-8")
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
    acls = list(csv.DictReader(handle))

group_blocks = re.findall(r'<record[^>]*model="res.groups">(.*?)</record>', security, flags=re.S)
if any('name="category_id"' in block for block in group_blocks):
    fail(10, "legacy category_id found directly on res.groups")
if 'model="res.groups.privilege"' not in security or 'name="privilege_id"' not in security:
    fail(10, "Odoo19 privilege hierarchy missing")
if security.count('model="ir.rule"') < 2:
    fail(10, "company record-rule coverage incomplete")
if any(row["group_id:id"] in ("base.group_public", "base.group_portal") for row in acls):
    fail(10, "public/portal backend ACL is forbidden; website route must use narrow sudo only")
for row in acls:
    if row["model_id:id"] == "model_clinic_ecommerce_fulfillment" and row["perm_unlink"] != "0":
        fail(10, f"Fulfillment evidence may not be deleted: {row['id']}")
for guard in (
    "ecommerce_catalog_transition",
    "ecommerce_fulfillment_transition",
    "group_ecommerce_operator",
    "group_ecommerce_manager",
    "policy_branch_scope_ecommerce",
):
    if guard not in model_source + controller_source:
        fail(10, f"backend security/governance guard missing: {guard}")
if 'auth="public"' not in controller_source or ".sudo().search" not in controller_source:
    fail(10, "public storefront narrow-sudo implementation missing")
if not any(x.startswith("[FAIL] HARD GATE 10") for x in errors):
    ok(10, f"3-role hierarchy + 2 company rules + {len(acls)} ACL rows + no public backend ACL + immutable fulfillment evidence pass")

# ---------------------------------------------------------------------------
# HARD GATE 12 - Odoo 19 / human-friendly code contracts
# ---------------------------------------------------------------------------
if "_sql_constraints" in model_source:
    fail(12, "legacy executable _sql_constraints found")
if dangerous_inherit:
    fail(12, f"list-valued _inherit without explicit _name: {dangerous_inherit}")
if constraints < 3:
    fail(12, f"too few models.Constraint declarations: {constraints}")
if indexes < 3:
    fail(12, f"too few models.Index declarations: {indexes}")
if 'attrs="' in all_xml or 'states="' in all_xml:
    fail(12, "legacy attrs/states XML syntax found")
if 'ref="base.res_config_settings_view_form"' not in all_xml:
    fail(12, "Settings does not inherit stable base Settings view")
if 'ref="sale.view_order_form"' not in all_xml:
    fail(12, "Sale Order extension does not inherit stable Sale owner form")
for fragile in (
    "clinic_booking.view_",
    "clinic_package.view_",
    "clinic_membership.view_",
    "clinic_patient.view_",
):
    if fragile in all_xml:
        fail(12, f"fragile upstream Clinic view XML ID found: {fragile}")
for asset in manifest.get("assets", {}).get("web.assets_frontend", []):
    prefix = "clinic_ecommerce/"
    if not asset.startswith(prefix):
        fail(12, f"unexpected asset namespace: {asset}")
        continue
    rel = asset[len(prefix):]
    if not (ROOT / rel).exists():
        fail(12, f"manifest asset missing: {asset}")
# Exact current Odoo 19 Website Sale extension signatures.
sale_source = (ROOT / "models/sale_order.py").read_text(encoding="utf-8")
for signature_token in (
    "def _cart_find_product_line(",
    "def _prepare_order_line_values(",
    "def _verify_updated_quantity(",
):
    if signature_token not in sale_source:
        fail(12, f"Odoo Website Sale extension point missing: {signature_token}")
payment_source = (ROOT / "models/payment_transaction.py").read_text(encoding="utf-8")
if payment_source.find("super()._post_process()") > payment_source.find("_clinic_ecommerce_process_fulfillments"):
    fail(12, "payment post-process must call super before Clinic fulfillment")
if not any(x.startswith("[FAIL] HARD GATE 12") for x in errors):
    ok(12, f"Odoo19 source/view/website_sale contracts pass; models.Constraint={constraints}, models.Index={indexes}")

# ---------------------------------------------------------------------------
# HARD GATE 13 - Useful comments
# ---------------------------------------------------------------------------
if comment_lines < 30 or docstrings < 12:
    fail(13, f"useful comment/docstring coverage too low: comments={comment_lines}, docstrings={docstrings}")
else:
    ok(13, f"ownership/security/lifecycle comments pass: comments={comment_lines}, docstrings={docstrings}")

# ---------------------------------------------------------------------------
# HARD GATE 15 - Enterprise completeness matrix
# ---------------------------------------------------------------------------
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
for capability in (
    "Treatment offering | PASS",
    "Package offering | PASS",
    "Membership offering | PASS",
    "Duplicate Membership invoice creation | ABSENT",
    "Odoo 19 runtime installation | PENDING",
    "Source/static PASS is not runtime completion",
):
    if capability not in matrix:
        fail(15, f"completeness evidence missing: {capability}")
if test_methods < 200:
    fail(15, f"runtime contract/regression suite too small: {test_methods}")
if not any(x.startswith("[FAIL] HARD GATE 15") for x in errors):
    ok(15, f"treatment/package/membership/native-sale fulfillment + governed storefront + {test_methods} runtime tests pass source/static completeness")

print("ClinicOne clinic_ecommerce Enterprise Development Guardrail")
print(f"[INFO] model_files={len(model_files)} python_files={len(python_files)} xml_files={len(xml_files)}")
print(f"[INFO] owned_models={len(owned)} models.Constraint={constraints} models.Index={indexes}")
print(f"[INFO] search_views={search_count} acl_rows={len(acls)} record_rules={security.count('model=\"ir.rule\"')}")
print(f"[INFO] test_methods={test_methods} class_methods={class_methods}")
for line in passes:
    print(line)
for line in errors:
    print(line)
if errors:
    print("RESULT: FAIL")
    sys.exit(1)
print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME WEBSITE/CHECKOUT/FULFILLMENT SMOKE TEST PENDING)")
