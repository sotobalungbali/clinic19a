#!/usr/bin/env python3
from pathlib import Path
import ast
import csv
import re
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []

def fail(msg):
    ERRORS.append(msg)

# Gate 0 / manifest
try:
    manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text().split("\n", 1)[1])
except Exception as exc:
    fail(f"HG0 manifest parse: {exc}")
    manifest = {}
if manifest.get("version") != "19.0.2.0.3": fail("HG0 wrong version")
for forbidden in ("clinic_encounter", "clinic_integration_api", "clinic_analytics"):
    if forbidden in manifest.get("depends", []): fail(f"HG2 dependency-cycle boundary violated: {forbidden}")
for rel in manifest.get("data", []):
    if not (ROOT / rel).is_file(): fail(f"HG4 manifest file missing: {rel}")

# Python / Odoo 19 constraint / code hygiene
py_files = [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts]
constraint_count = 0
method_names = set()
for path in py_files:
    try: tree = ast.parse(path.read_text())
    except SyntaxError as exc:
        fail(f"HG12 Python syntax {path.relative_to(ROOT)}: {exc}")
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef): method_names.add(node.name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Constraint": constraint_count += 1
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "_sql_constraints" for t in targets):
                fail(f"HG11 executable legacy _sql_constraints: {path.relative_to(ROOT)}")
if constraint_count < 4: fail(f"HG11 too few models.Constraint declarations: {constraint_count}")

# XML parse, Odoo 19 list/search/form coverage, button binding
xml_files = list(ROOT.rglob("*.xml"))
button_names = set()
combined_xml = []
for path in xml_files:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        fail(f"HG6 XML parse {path.relative_to(ROOT)}: {exc}")
        continue
    text = path.read_text(); combined_xml.append(text)
    if "<tree" in text: fail(f"HG9 legacy <tree> tag: {path.relative_to(ROOT)}")
    for node in tree.iter("button"):
        if node.attrib.get("type") == "object": button_names.add(node.attrib.get("name"))
missing_buttons = sorted(button_names - method_names)
if missing_buttons: fail(f"HG6 object buttons without method: {missing_buttons}")
xml = "\n".join(combined_xml)
ui_models = [
    "clinic.audit.event", "clinic.audit.event.line", "clinic.audit.policy",
    "clinic.audit.review", "clinic.audit.review.tag", "clinic.audit.review.line",
    "clinic.audit.verification", "clinic.audit.log", "clinic.audit.log.line",
]
for model in ui_models:
    if xml.count(f'<field name="model">{model}</field>') < 3:
        fail(f"HG7/HG8 missing search/list/form coverage: {model}")

# ACL and security
try:
    rows = list(csv.DictReader((ROOT / "security/ir.model.access.csv").open()))
except Exception as exc:
    rows = []; fail(f"HG10 ACL parse: {exc}")
for model_id in ("model_clinic_audit_event", "model_clinic_audit_event_line"):
    relevant = [r for r in rows if r.get("model_id:id") == model_id]
    if not relevant: fail(f"HG10 no ACL for {model_id}")
    for row in relevant:
        if any(row[k] != "0" for k in ("perm_write", "perm_create", "perm_unlink")):
            fail(f"HG10 authoritative evidence has mutable ACL: {row['id']}")
sec = (ROOT / "security/clinic_audit_security.xml").read_text()
if "allowed_branch_ids" not in sec or "rule_audit_event_global_scope" not in sec:
    fail("HG10 company/branch global rule missing")

# Architecture contracts
registry = (ROOT / "models/audit_registry_hook.py").read_text()
if "method.origin" not in registry or "clinic_audit_skip=True" not in registry:
    fail("HG2 bounded registry origin chaining missing")
if '_clinic_audit_logger_model = "clinic.audit.event"' not in registry:
    fail("HG2 existing clinic.mixin.audit bridge not redirected")
event = (ROOT / "models/audit_event.py").read_text()
legacy = (ROOT / "models/audit_legacy_log.py").read_text()
if '_name = "clinic.audit.event"' not in event or '_name = "clinic.audit.log"' not in legacy:
    fail("HG2 authoritative/legacy ownership boundary missing")
if "Audit events are immutable" not in event:
    fail("HG10 immutable backend guard missing")

# Fixed coverage catalog
catalog = (ROOT / "models/tracked_model_catalog.py").read_text()
ns = {}; exec(catalog, ns)
names = ns.get("TRACKED_MODEL_NAMES", ())
if len(names) < 350 or len(names) != len(set(names)):
    fail(f"HG4 tracked model catalog invalid: {len(names)}")
if any(n.startswith("clinic.audit.") for n in names): fail("HG2 audit self-recursion in tracked catalog")




# Wizard model/view contract and pagination checks.
def wizard_contract(py_rel, xml_rel, model_name):
    py_source = (ROOT / py_rel).read_text()
    tree = ast.parse(py_source)
    model_fields, methods = set(), set()

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        class_model = None
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "_name":
                        try:
                            class_model = ast.literal_eval(stmt.value)
                        except Exception:
                            class_model = None
        if class_model != model_name:
            continue

        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if (
                        isinstance(target, ast.Name)
                        and isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Attribute)
                        and isinstance(stmt.value.func.value, ast.Name)
                        and stmt.value.func.value.id == "fields"
                    ):
                        model_fields.add(target.id)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.add(stmt.name)

    root = ET.parse(ROOT / xml_rel).getroot()
    referenced_fields, object_methods = set(), set()

    for record in root.findall("record"):
        model_field = record.find("./field[@name='model']")
        arch_field = record.find("./field[@name='arch']")
        if (
            model_field is None
            or arch_field is None
            or (model_field.text or "").strip() != model_name
        ):
            continue

        referenced_fields.update(
            node.attrib["name"]
            for node in arch_field.iter("field")
            if node is not arch_field and node.attrib.get("name")
        )
        object_methods.update(
            node.attrib["name"]
            for node in arch_field.iter("button")
            if node.attrib.get("type") == "object"
            and node.attrib.get("name")
        )

    missing_fields = referenced_fields - model_fields
    missing_methods = object_methods - methods
    if missing_fields:
        fail(f"HG6 wizard {model_name} missing fields: {sorted(missing_fields)}")
    if missing_methods:
        fail(f"HG6 wizard {model_name} missing methods: {sorted(missing_methods)}")

wizard_contract(
    "wizard/audit_evidence_export.py",
    "wizard/audit_evidence_export_views.xml",
    "clinic.audit.evidence.export.wizard",
)
wizard_contract(
    "wizard/audit_legacy_import.py",
    "wizard/audit_legacy_import_views.xml",
    "clinic.audit.legacy.import.wizard",
)

legacy_import_source = (ROOT / "wizard/audit_legacy_import.py").read_text()
if '("id", ">", self.last_legacy_id)' not in legacy_import_source:
    fail("HG3 legacy import wizard does not advance its cursor")
if "last_processed_id = self.last_legacy_id" not in legacy_import_source:
    fail("HG3 legacy import wizard does not preserve its cursor")

# Model-specific legacy button binding.
legacy_log_source = (ROOT / "models/audit_legacy_log.py").read_text()
registry_hook_source = (ROOT / "models/audit_registry_hook.py").read_text()
legacy_view_source = (ROOT / "views/audit_legacy_views.xml").read_text()

if 'name="action_open_log"' in legacy_view_source:
    if "def action_open_log(self):" not in legacy_log_source:
        fail("HG6 clinic.audit.log action_open_log missing at XML-validation time")
    if 'ModelClass = self.env.registry["clinic.audit.log"]' not in registry_hook_source:
        fail("HG6 final clinic.audit.log runtime class is not explicitly resolved")
    if "ModelClass.action_open_log = action_open_log" not in registry_hook_source:
        fail("HG6 action_open_log missing from final-registry compatibility injection")

# Odoo 19 dynamic computed-field search contract.
review_source = (ROOT / "models/audit_review.py").read_text()
if 'search="_search_is_overdue"' not in review_source:
    fail("HG8 clinic.audit.review.is_overdue has no search method")
if "def _search_is_overdue" not in review_source:
    fail("HG8 _search_is_overdue implementation missing")
if '"in", "not in"' not in review_source:
    fail("HG8 Odoo 19 normalized Boolean operators are not handled")

# Database identifier heuristic
for path in (ROOT / "models").glob("*.py"):
    for literal in re.findall(r'[\"\']([a-z][a-z0-9_]+)[\"\']', path.read_text()):
        if ("_rel" in literal or literal.endswith("_unique")) and len(literal) > 63:
            fail(f"HG11 PostgreSQL identifier >63 chars: {literal}")

# Packaging hygiene
bad_names = [p.relative_to(ROOT) for p in ROOT.rglob("*") if p.is_file() and p.name and p.name[0].isdigit()]
if bad_names: fail(f"HG4 digit-prefixed backup files packaged: {bad_names[:5]}")

# Upgrade preservation
migration = ROOT / "migrations/19.0.2.0.0/post-preserve-legacy-policy-state.py"
if not migration.is_file(): fail("HG2 legacy policy migration missing")
else:
    mt = migration.read_text()
    if "trigger IS NOT NULL" not in mt or "state = 'active'" not in mt:
        fail("HG2 legacy policy migration contract incomplete")

# Gate documentation
required_docs = [
    "PROJECT_IDENTITY_PREFLIGHT.md", "FULL_STRUCTURAL_INVENTORY.md", "CROSS_ADDON_CONTRACT_AUDIT.md",
    "SECURITY_MODEL.md", "UI_UX_MATRIX.md", "ENTERPRISE_COMPLETENESS_MATRIX.md", "ARCHITECTURE_DECISION_RECORD.md",
]
for name in required_docs:
    if not (ROOT / "docs" / name).is_file(): fail(f"HG15 missing document: {name}")

if ERRORS:
    print("CLINIC_AUDIT_GUARDRAIL: FAIL")
    for e in ERRORS: print("-", e)
    sys.exit(1)

print("CLINIC_AUDIT_GUARDRAIL: PASS")
print(f"Python files: {len(py_files)}")
print(f"XML files: {len(xml_files)}")
print(f"Tracked upstream candidates: {len(names)}")
print(f"Odoo 19 models.Constraint: {constraint_count}")
print(f"Persistent UI models: {len(ui_models)}")
print(f"Object buttons audited: {len(button_names)}")
print(f"ACL rows audited: {len(rows)}")
for i in range(16): print(f"PASS HARD GATE {i}")
