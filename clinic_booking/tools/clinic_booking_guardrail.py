

#!/usr/bin/env python3
"""Machine-checkable static enterprise hard gate for ClinicOne clinic_booking.

The validator intentionally does not import Odoo.  It checks the preserved
source contract, Odoo 19 migration patterns, custom model/view consistency,
security coverage and the owner-defined enterprise artifacts before a real
Windows Odoo runtime gate is attempted.
"""
from __future__ import annotations

from pathlib import Path
import ast
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "CLINIC_BOOKING_BASELINE_CONTRACT.json"

REQUIRED_DOCS = {
    "AGENTS.md",
    "docs/CLINIC_BOOKING_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "docs/CLINIC_BOOKING_BASELINE_CONTRACT.json",
    "docs/CLINIC_BOOKING_STRUCTURAL_INVENTORY.md",
    "docs/CLINIC_BOOKING_UI_UX_MATRIX.md",
    "docs/CLINIC_BOOKING_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/CLINIC_BOOKING_ODOO19_REVIEW.md",
}
REQUIRED_VIEW_FILES = {
    "views/booking_core_views.xml",
    "views/booking_master_views.xml",
    "views/booking_schedule_views.xml",
    "views/booking_feedback_views.xml",
    "views/booking_menus.xml",
}
COMMON_ORM_FIELDS = {
    "id", "display_name", "create_date", "write_date", "create_uid", "write_uid",
    "message_follower_ids", "message_partner_ids", "message_ids", "message_unread",
    "message_unread_counter", "message_needaction", "message_needaction_counter",
    "message_has_error", "message_has_error_counter", "message_attachment_count",
    "activity_ids", "activity_state", "activity_user_id", "activity_type_id",
    "activity_date_deadline", "activity_summary", "activity_exception_decoration",
    "activity_exception_icon",
}
FORBIDDEN_ACTIVE_PATTERNS = {
    "_sql_constraints": "legacy _sql_constraints",
    ".mapped(\"qty_done\")": "legacy stock.move.line qty_done",
    ".mapped('qty_done')": "legacy stock.move.line qty_done",
    ".quantity_done": "legacy stock move quantity_done",
}


def emit(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}: {label}" + (f" — {detail}" if detail else ""))
    return ok


def load_manifest() -> dict:
    text = (ROOT / "__manifest__.py").read_text(encoding="utf-8")
    return ast.literal_eval(text[text.index("{"):])


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def active_model_files(contract: dict) -> list[Path]:
    return [ROOT / "models" / f"{name}.py" for name in contract["active_model_imports"]]


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def is_field_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "fields"
    )


def class_descriptor(path: Path, node: ast.ClassDef) -> dict:
    name = None
    inherit = None
    inherits = {}
    abstract = False
    fields = {}
    methods = set()
    constraints = 0

    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == "_name":
                    value = literal(item.value)
                    if isinstance(value, str):
                        name = value
                elif target.id == "_inherit":
                    inherit = literal(item.value)
                elif target.id == "_inherits":
                    value = literal(item.value)
                    if isinstance(value, dict):
                        inherits = value
                elif target.id == "_abstract":
                    abstract = bool(literal(item.value))
                elif is_field_call(item.value):
                    call = item.value
                    field_type = call.func.attr
                    comodel = None
                    if call.args:
                        first = literal(call.args[0])
                        if isinstance(first, str):
                            comodel = first
                    props = {"type": field_type, "comodel": comodel, "compute": None, "inverse": None, "search": None, "store": None, "related": None, "selection": None}
                    for kw in call.keywords:
                        if kw.arg in {"compute", "inverse", "search", "store", "related", "selection"}:
                            props[kw.arg] = literal(kw.value)
                    fields[target.id] = props
                elif isinstance(item.value, ast.Call):
                    call = item.value
                    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                        if call.func.value.id == "models" and call.func.attr == "Constraint":
                            constraints += 1
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.add(item.name)

    return {
        "file": str(path.relative_to(ROOT)),
        "class": node.name,
        "name": name,
        "inherit": inherit,
        "inherits": inherits,
        "abstract": abstract,
        "fields": fields,
        "methods": methods,
        "constraints": constraints,
    }


def parse_classes(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                row = class_descriptor(path, node)
                if row["name"] or row["inherit"]:
                    rows.append(row)
    return rows


def normalize_inherit(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [x for x in value if isinstance(x, str)]
    return []


def build_registry(classes: list[dict]) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for row in classes:
        model = row["name"]
        if model:
            bucket = registry.setdefault(model, {"fields": {}, "methods": set(), "inherits": [], "delegates": {}, "classes": []})
            bucket["fields"].update(row["fields"])
            bucket["methods"].update(row["methods"])
            bucket["inherits"].extend(normalize_inherit(row["inherit"]))
            bucket["delegates"].update(row["inherits"])
            bucket["classes"].append(row)
        elif isinstance(row["inherit"], str):
            model = row["inherit"]
            bucket = registry.setdefault(model, {"fields": {}, "methods": set(), "inherits": [], "delegates": {}, "classes": []})
            bucket["fields"].update(row["fields"])
            bucket["methods"].update(row["methods"])
            bucket["classes"].append(row)
    return registry


def effective_fields(registry: dict, model: str, seen=None) -> dict:
    seen = set(seen or ())
    if model in seen:
        return {}
    seen.add(model)
    bucket = registry.get(model)
    if not bucket:
        return {}
    out = dict(bucket["fields"])
    for parent in bucket["inherits"]:
        if parent in registry:
            inherited = effective_fields(registry, parent, seen)
            inherited.update(out)
            out = inherited
    return out


def effective_methods(registry: dict, model: str, seen=None) -> set[str]:
    seen = set(seen or ())
    if model in seen:
        return set()
    seen.add(model)
    bucket = registry.get(model)
    if not bucket:
        return set()
    out = set(bucket["methods"])
    for parent in bucket["inherits"]:
        if parent in registry:
            out |= effective_methods(registry, parent, seen)
    return out


def baseline_preservation_issues(contract: dict, classes: list[dict]) -> list[str]:
    lookup = {(row["file"], row["class"]): row for row in classes}
    issues = []
    for model, base in contract["baseline_models"].items():
        now = lookup.get((base["file"], base["class"]))
        if not now:
            issues.append(f"{model}:missing class {base['file']}:{base['class']}")
            continue
        for field in base["fields"]:
            if field not in now["fields"]:
                issues.append(f"{model}:missing field:{field}")
        for method in base["methods"]:
            if method not in now["methods"]:
                issues.append(f"{model}:missing method:{method}")
    for ext in contract["baseline_extensions"]:
        now = lookup.get((ext["file"], ext["class"]))
        if not now:
            issues.append(f"{ext['model']}:missing extension {ext['file']}:{ext['class']}")
            continue
        for field in ext["fields"]:
            if field not in now["fields"]:
                issues.append(f"{ext['model']}:missing field:{field}")
        for method in ext["methods"]:
            if method not in now["methods"]:
                issues.append(f"{ext['model']}:missing method:{method}")
    return issues


def namespace_collision_issues(paths: list[Path]) -> list[str]:
    issues = []
    for row in parse_classes(paths):
        collisions = set(row["fields"]) & row["methods"]
        for name in sorted(collisions):
            issues.append(f"{row['file']}:{row['class']}:{name}")
    return issues


def decorator_dependency_issues(paths: list[Path], registry: dict) -> list[str]:
    issues = []
    local_map = {(row["file"], row["class"]): row for row in parse_classes(paths)}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            row = local_map.get((str(path.relative_to(ROOT)), cls.name))
            if not row:
                continue
            model = row["name"] or (row["inherit"] if isinstance(row["inherit"], str) else None)
            if not model:
                continue
            known = set(effective_fields(registry, model)) | COMMON_ORM_FIELDS
            for method in [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for deco in method.decorator_list:
                    if not (
                        isinstance(deco, ast.Call)
                        and isinstance(deco.func, ast.Attribute)
                        and isinstance(deco.func.value, ast.Name)
                        and deco.func.value.id == "api"
                        and deco.func.attr in {"depends", "constrains", "onchange"}
                    ):
                        continue
                    for arg in deco.args:
                        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                            continue
                        root = arg.value.split(".", 1)[0]
                        # For Odoo-native extensions, unknown native fields cannot be
                        # proven statically.  Custom booking_* and local roots can.
                        strict = model.startswith("booking.") or root.startswith("booking_") or root in set(row["fields"])
                        if strict and root not in known:
                            issues.append(f"{row['file']}:{cls.name}:{method.name}:{deco.func.attr}:{arg.value}")
    return issues


def iter_loaded_view_files(manifest: dict) -> list[Path]:
    return [ROOT / item for item in manifest.get("data", []) if item.startswith("views/") and item.endswith(".xml")]


def view_records(paths: list[Path]):
    for path in paths:
        root = ET.parse(path).getroot()
        for rec in root.findall(".//record"):
            if rec.get("model") != "ir.ui.view":
                continue
            mf = rec.find("./field[@name='model']")
            af = rec.find("./field[@name='arch']")
            if mf is None or af is None or len(af) == 0:
                continue
            yield path, rec, (mf.text or "").strip(), af[0]


def view_coverage(paths: list[Path], models: list[str]) -> dict[str, set[str]]:
    coverage = {m: set() for m in models}
    for _path, _rec, model, arch in view_records(paths):
        if model in coverage and arch.tag in {"search", "list", "form", "calendar", "kanban"}:
            coverage[model].add(arch.tag)
    return coverage


def searchability_issues(paths: list[Path], registry: dict, persistent: set[str]) -> list[str]:
    issues = []
    domain_field_re = re.compile(r"\(\s*['\"]([A-Za-z_][A-Za-z0-9_\.]*)['\"]\s*,")
    for path, rec, model, arch in view_records(paths):
        if model not in persistent or arch.tag != "search":
            continue
        fields = effective_fields(registry, model)
        candidates = []
        for node in arch.iter("filter"):
            for match in domain_field_re.finditer(node.get("domain") or ""):
                candidates.append((match.group(1).split(".", 1)[0], f"filter:{node.get('name') or node.get('string')}"))
        for node in arch.findall(".//field"):
            if node.get("name"):
                candidates.append((node.get("name"), "search-field"))
        for fname, where in candidates:
            meta = fields.get(fname)
            if not meta:
                continue
            if meta.get("compute") and meta.get("store") is not True and not meta.get("search"):
                issues.append(f"{path.relative_to(ROOT)}:{rec.get('id')}:{model}:{fname}:{where}")
    return issues


def custom_view_contract_issues(paths: list[Path], registry: dict, persistent: set[str]) -> list[str]:
    """Validate custom model XML fields/buttons, including nested relational rows."""
    issues = []

    def walk(node: ET.Element, model: str, path: Path, view_id: str):
        fields = effective_fields(registry, model)
        methods = effective_methods(registry, model)
        delegated = bool(registry.get(model, {}).get("delegates"))
        for child in list(node):
            if child.tag == "field":
                fname = child.get("name")
                meta = fields.get(fname) if fname else None
                if fname and fname not in fields and fname not in COMMON_ORM_FIELDS and not delegated:
                    issues.append(f"{path.relative_to(ROOT)}:{view_id}:{model}:missing-field:{fname}")
                next_model = meta.get("comodel") if meta else None
                for grand in list(child):
                    if grand.tag in {"list", "form", "kanban"} and next_model and next_model in registry:
                        walk(grand, next_model, path, view_id)
                    else:
                        walk(grand, model, path, view_id)
                continue
            if child.tag == "button" and child.get("type") == "object":
                method = child.get("name")
                if method and method not in methods:
                    issues.append(f"{path.relative_to(ROOT)}:{view_id}:{model}:missing-button-method:{method}")
            walk(child, model, path, view_id)

    for path, rec, model, arch in view_records(paths):
        if model in persistent:
            walk(arch, model, path, rec.get("id") or "<view>")
    return sorted(set(issues))


def search_architecture_issues(paths: list[Path]) -> list[str]:
    issues = []
    for path, rec, model, arch in view_records(paths):
        if arch.tag == "tree" or any(n.tag == "tree" for n in arch.iter()):
            issues.append(f"{path.relative_to(ROOT)}:{rec.get('id')}:legacy-tree-tag")
        if arch.tag == "search":
            for group in arch.findall(".//group"):
                if "expand" in group.attrib:
                    issues.append(f"{path.relative_to(ROOT)}:{rec.get('id')}:search-group-expand")
    return issues


def name_display_contract_issues(paths: list[Path]) -> list[str]:
    issues = []
    for row in parse_classes(paths):
        if "name_get" in row["methods"] and "_compute_display_name" not in row["methods"]:
            issues.append(f"{row['file']}:{row['class']}:name_get-without-_compute_display_name")
    return issues



def field_callable_contract_issues(registry: dict, persistent: set[str]) -> list[str]:
    """Ensure string compute/inverse/search/selection methods exist."""
    issues = []
    for model in sorted(persistent):
        fields = effective_fields(registry, model)
        methods = effective_methods(registry, model)
        for fname, meta in fields.items():
            for prop in ("compute", "inverse", "search"):
                method = meta.get(prop)
                if isinstance(method, str) and method and method not in methods:
                    issues.append(f"{model}:{fname}:{prop}:{method}")
            selection = meta.get("selection")
            if isinstance(selection, str) and selection and selection not in methods:
                issues.append(f"{model}:{fname}:selection:{selection}")
    return issues


def relational_contract_issues(registry: dict, persistent: set[str]) -> list[str]:
    """Validate ClinicOne booking-model relations and One2many inverses."""
    issues = []
    for model in sorted(persistent):
        fields = effective_fields(registry, model)
        for fname, meta in fields.items():
            comodel = meta.get("comodel")
            ftype = meta.get("type")
            if not isinstance(comodel, str) or not comodel.startswith("booking."):
                continue
            if comodel not in registry:
                issues.append(f"{model}:{fname}:{ftype}:missing-comodel:{comodel}")
                continue
            if ftype == "One2many":
                # Re-read defining field AST to obtain inverse_name (2nd positional arg).
                inverse = None
                for bucket_class in registry.get(model, {}).get("classes", []):
                    if fname not in bucket_class["fields"]:
                        continue
                    path = ROOT / bucket_class["file"]
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == bucket_class["class"]]:
                        for item in cls.body:
                            if not isinstance(item, ast.Assign) or not is_field_call(item.value):
                                continue
                            if not any(isinstance(t, ast.Name) and t.id == fname for t in item.targets):
                                continue
                            if len(item.value.args) >= 2:
                                inv = literal(item.value.args[1])
                                if isinstance(inv, str):
                                    inverse = inv
                if inverse and inverse not in effective_fields(registry, comodel):
                    issues.append(f"{model}:{fname}:One2many:{comodel}:missing-inverse:{inverse}")
    return issues


def active_unknown_comodel_issues(paths: list[Path]) -> list[str]:
    """Reject known removed active comodels while ignoring comments/dormant source."""
    issues = []
    for row in parse_classes(paths):
        for fname, meta in row["fields"].items():
            if meta.get("comodel") == "account.analytic.tag":
                issues.append(f"{row['file']}:{row['class']}:{fname}:account.analytic.tag")
    return issues


def local_xmlid_contract_issues(manifest: dict, active_paths: list[Path]) -> list[str]:
    """Validate local clinic_booking XML IDs referenced by loaded XML/Python."""
    loaded = []
    for item in manifest.get("data", []) + manifest.get("demo", []):
        path = ROOT / item
        if path.suffix == ".xml" and path.exists():
            loaded.append(path)
    ids = set()
    roots = []
    for path in loaded:
        root = ET.parse(path).getroot()
        roots.append((path, root))
        for node in root.iter():
            xid = node.get("id")
            if xid:
                ids.add(xid)
    issues = []
    def check_ref(raw: str, where: str):
        if not raw:
            return
        if raw.startswith("clinic_booking."):
            local = raw.split(".", 1)[1]
            if local not in ids:
                issues.append(f"{where}:missing-local-xmlid:{raw}")
    for path, root in roots:
        for node in root.iter():
            check_ref(node.get("ref") or "", f"{path.relative_to(ROOT)}:{node.tag}:ref")
            action = node.get("action") or ""
            if action and "." not in action and action not in ids:
                issues.append(f"{path.relative_to(ROOT)}:{node.tag}:missing-local-action:{action}")
            check_ref(action, f"{path.relative_to(ROOT)}:{node.tag}:action")
            for attr in ("groups",):
                for token in (node.get(attr) or "").split(","):
                    check_ref(token.strip(), f"{path.relative_to(ROOT)}:{node.tag}:{attr}")
    env_ref_re = re.compile(r"env\.ref\(\s*['\"]clinic_booking\.([A-Za-z0-9_]+)['\"]")
    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        for m in env_ref_re.finditer(text):
            if m.group(1) not in ids:
                issues.append(f"{path.relative_to(ROOT)}:env.ref:missing-local-xmlid:clinic_booking.{m.group(1)}")
    return sorted(set(issues))


def odoo19_import_xml_structure_issues(manifest: dict) -> list[str]:
    """Check the loader-level XML shape described by Odoo 19 import_xml.rng.

    This is intentionally a local structural subset, not a replacement for the
    real Odoo converter/view validator. It catches malformed data wrappers and
    record/field/menu structures before the Windows runtime gate.
    """
    issues = []
    allowed_children = {"odoo", "openerp", "data", "menuitem", "record", "template", "asset", "delete", "function"}
    files = []
    for item in manifest.get("data", []) + manifest.get("demo", []):
        path = ROOT / item
        if path.suffix == ".xml" and path.exists():
            files.append(path)
    for path in files:
        root = ET.parse(path).getroot()
        if root.tag not in {"odoo", "openerp", "data"}:
            issues.append(f"{path.relative_to(ROOT)}:invalid-root:{root.tag}")
            continue
        for node in list(root):
            if not isinstance(node.tag, str):
                continue
            if node.tag not in allowed_children:
                issues.append(f"{path.relative_to(ROOT)}:invalid-top-level:{node.tag}")
            if node.tag == "record":
                if not node.get("model"):
                    issues.append(f"{path.relative_to(ROOT)}:record-missing-model:{node.get('id')}")
                for child in list(node):
                    if isinstance(child.tag, str) and child.tag != "field":
                        issues.append(f"{path.relative_to(ROOT)}:record-invalid-child:{child.tag}")
                    if child.tag == "field" and not child.get("name"):
                        issues.append(f"{path.relative_to(ROOT)}:field-missing-name:{node.get('id')}")
            if node.tag == "menuitem" and not node.get("id"):
                issues.append(f"{path.relative_to(ROOT)}:menuitem-missing-id")
    return issues


def manifest_file_reference_issues(manifest: dict) -> list[str]:
    issues = []
    for key in ("data", "demo", "images"):
        for item in manifest.get(key, []) or []:
            if not (ROOT / item).exists():
                issues.append(f"{key}:{item}:missing")
    return issues

def acl_models(path: Path) -> set[str]:
    models = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ref = row.get("model_id:id", "")
            if ref.startswith("model_"):
                models.add(ref[len("model_"):].replace("_", "."))
    return models


def main() -> int:
    contract = load_contract()
    manifest = load_manifest()
    active_paths = active_model_files(contract)
    active_classes = parse_classes(active_paths)
    registry = build_registry(active_classes)
    persistent = set(contract["persistent_custom_models"])
    loaded_views = iter_loaded_view_files(manifest)

    # Runtime regression guard: booking.feedback.link.booking_id has a
    # One2many inverse named feedback_link_ids. That inverse MUST be an
    # effective field of booking.booking, not only a dormant abstract mixin.
    booking_fields = effective_fields(registry, "booking.booking")
    booking_methods = effective_methods(registry, "booking.booking")
    feedback_inverse_ok = (
        "feedback_link_ids" in booking_fields
        and "action_new_feedback_link" in booking_methods
        and "booking.feedback.link.mixin" in registry.get("booking.booking", {}).get("inherits", [])
    )

    checks: list[tuple[str, bool, str]] = []

    checks.append(("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
                   ROOT.name == "clinic_booking" and contract.get("project") == "ClinicOne" and contract.get("addon") == "clinic_booking",
                   f"folder={ROOT.name}"))

    checks.append(("BOOKING_FEEDBACK_INVERSE_RUNTIME_CONTRACT",
                   feedback_inverse_ok,
                   "booking.booking must effectively own feedback_link_ids and action_new_feedback_link via booking.feedback.link.mixin"))

    channel_source = (ROOT / "models/booking_channel.py").read_text(encoding="utf-8")
    channel_create_multi_ok = (
        manifest.get("version") == "19.0.1.0.4"
        and "@api.model_create_multi" in channel_source
        and "def create(self, vals_list):" in channel_source
        and "for original in vals_list:" in channel_source
        and "def create(self, vals):" not in channel_source
    )
    checks.append(("ODOO19_BOOKING_CHANNEL_CREATE_MULTI_CONTRACT",
                   channel_create_multi_ok,
                   "booking.channel create must accept Odoo 19 vals_list without list.get failure"))

    doctor_bridge_source = (ROOT / "models/clinic_doctor_inherit.py").read_text(encoding="utf-8")
    booking_bridge_source = (ROOT / "models/booking_booking.py").read_text(encoding="utf-8")
    appointment_bridge_ok = (
        'start_field = "start" if "start" in app_fields' in doctor_bridge_source
        and 'end_field = "end" if "end" in app_fields' in doctor_bridge_source
        and '("state", "not in", ["canceled", "no_show"])' in doctor_bridge_source
        and 'if "start" in app_fields:' in booking_bridge_source
        and 'vals["start"] = rec.start_datetime' in booking_bridge_source
        and 'if "end" in app_fields:' in booking_bridge_source
        and 'vals["end"] = rec.end_datetime' in booking_bridge_source
        and 'if "partner_id" in app_fields:' in booking_bridge_source
    )
    checks.append(("CLINIC_APPOINTMENT_FIELD_COMPATIBILITY_CONTRACT",
                   appointment_bridge_ok,
                   "clinic_booking soft appointment bridge must use canonical start/end and field-aware domains"))

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    checks.append(("HARD_GATE_1_CODEX_BUKAN_ARCHITECT",
                   "LIMITED IMPLEMENTATION WORKER" in agents and "endless retry engine" in agents.lower(),
                   "bounded implementation role"))

    checks.append(("MANIFEST_DEPENDENCY_PRESERVATION",
                   manifest.get("depends") == contract["dependencies"],
                   "dependencies must remain exactly baseline"))

    missing_baseline_files = [p for p in contract["baseline_source_files"] if not (ROOT / p).exists()]
    checks.append(("BASELINE_SOURCE_FILE_PRESERVATION", not missing_baseline_files,
                   f"missing={missing_baseline_files[:5]}"))

    preservation = baseline_preservation_issues(contract, active_classes)
    checks.append(("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", not preservation,
                   f"missing={preservation[:8]}"))

    compile_errors = []
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0") or "__pycache__" in path.parts:
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            compile_errors.append(f"{path.relative_to(ROOT)}:{exc}")
    checks.append(("PYTHON_COMPILE", not compile_errors, str(compile_errors[:3])))

    xml_errors = []
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        try:
            ET.parse(path)
        except Exception as exc:
            xml_errors.append(f"{path.relative_to(ROOT)}:{exc}")
    checks.append(("XML_PARSE", not xml_errors, str(xml_errors[:3])))

    collisions = namespace_collision_issues(active_paths)
    checks.append(("FIELD_METHOD_NAMESPACE_COLLISION_GATE", not collisions, f"collisions={collisions}"))

    decorator_issues = decorator_dependency_issues(active_paths, registry)
    checks.append(("CUSTOM_DECORATOR_FIELD_CONTRACT_GATE", not decorator_issues,
                   f"missing={decorator_issues[:8]}"))

    callable_issues = field_callable_contract_issues(registry, persistent)
    checks.append(("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE", not callable_issues,
                   f"invalid={callable_issues[:8]}"))

    relation_issues = relational_contract_issues(registry, persistent)
    checks.append(("RELATIONAL_MODEL_INVERSE_CONTRACT_GATE", not relation_issues,
                   f"invalid={relation_issues[:8]}"))

    comodel_issues = active_unknown_comodel_issues(active_paths)
    checks.append(("ODOO19_ACTIVE_COMODEL_COMPATIBILITY_GATE", not comodel_issues,
                   f"invalid={comodel_issues}"))

    all_model_paths = [p for p in (ROOT / "models").glob("*.py") if not p.name.startswith("0")]
    all_comodel_issues = active_unknown_comodel_issues(all_model_paths)
    checks.append(("ODOO19_ALL_SOURCE_REMOVED_COMODEL_GATE", not all_comodel_issues,
                   f"invalid={all_comodel_issues}"))

    active_text = "\n".join(p.read_text(encoding="utf-8") for p in active_paths)
    compatibility = [label for pattern, label in FORBIDDEN_ACTIVE_PATTERNS.items() if pattern in active_text]
    checks.append(("ODOO19_STATIC_COMPATIBILITY", not compatibility, f"forbidden={compatibility}"))

    # Exact SQL migration contract: active runtime source had 19 legacy SQL
    # constraints; dormant aggregate is preserved but also migrated, yielding 37.
    active_constraint_count = sum(row["constraints"] for row in active_classes)
    total_constraint_count = 0
    for path in (ROOT / "models").glob("*.py"):
        if path.name.startswith("0"):
            continue
        total_constraint_count += sum(r["constraints"] for r in parse_classes([path]))
    legacy_sql = []
    for path in (ROOT / "models").glob("*.py"):
        if path.name.startswith("0"):
            continue
        if "_sql_constraints" in path.read_text(encoding="utf-8"):
            legacy_sql.append(str(path.relative_to(ROOT)))
    sql_ok = (
        not legacy_sql
        and active_constraint_count == contract["expected_active_models_constraint_count"]
        and total_constraint_count == contract["expected_total_models_constraint_count_after_hardening"]
    )
    checks.append(("ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE", sql_ok,
                   f"legacy={legacy_sql}, active={active_constraint_count}, total={total_constraint_count}"))

    display_issues = name_display_contract_issues(active_paths)
    checks.append(("ODOO19_DISPLAY_NAME_CONTRACT_GATE", not display_issues,
                   f"invalid={display_issues}"))

    search_arch = search_architecture_issues(loaded_views)
    checks.append(("ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE", not search_arch,
                   f"invalid={search_arch[:8]}"))

    view_contract = custom_view_contract_issues(loaded_views, registry, persistent)
    checks.append(("XML_CUSTOM_MODEL_FIELD_BUTTON_CONTRACT_GATE", not view_contract,
                   f"invalid={view_contract[:10]}"))

    searchability = searchability_issues(loaded_views, registry, persistent)
    checks.append(("ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE", not searchability,
                   f"invalid={searchability[:8]}"))

    backup_loaded = any(Path(x).name.startswith("0") for x in manifest.get("data", []) + manifest.get("demo", []))
    active_import_text = (ROOT / "models/__init__.py").read_text(encoding="utf-8")
    imports_match = all(f"from . import {name}" in active_import_text for name in contract["active_model_imports"])
    dormant_not_imported = "xxx_clinic_booking" not in active_import_text
    checks.append(("ACTIVE_IMPORT_AND_BACKUP_EXCLUSION_GATE",
                   not backup_loaded and imports_match and dormant_not_imported,
                   "0* backups excluded; dormant aggregate remains inactive"))

    xmlid_issues = local_xmlid_contract_issues(manifest, active_paths)
    checks.append(("LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE", not xmlid_issues,
                   f"invalid={xmlid_issues[:10]}"))

    import_xml_issues = odoo19_import_xml_structure_issues(manifest)
    checks.append(("ODOO19_IMPORT_XML_SCHEMA_STRUCTURE_GATE", not import_xml_issues,
                   f"invalid={import_xml_issues[:10]}"))

    manifest_file_issues = manifest_file_reference_issues(manifest)
    checks.append(("MANIFEST_FILE_REFERENCE_CONTRACT_GATE", not manifest_file_issues,
                   f"invalid={manifest_file_issues}"))

    missing_artifacts = [p for p in sorted(REQUIRED_DOCS | REQUIRED_VIEW_FILES) if not (ROOT / p).exists()]
    checks.append(("HARD_GATE_3_ENTERPRISE_COMPLETENESS", not missing_artifacts,
                   f"missing={missing_artifacts}"))
    checks.append(("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY",
                   (ROOT / "docs/CLINIC_BOOKING_STRUCTURAL_INVENTORY.md").exists(), "inventory document"))
    checks.append(("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
                   len([p for p in loaded_views if p.name.endswith("_views.xml")]) >= 4,
                   "views split by domain"))

    all_view_text = "\n".join(p.read_text(encoding="utf-8") for p in loaded_views)
    form_quality = (
        'widget="statusbar"' in all_view_text
        and "oe_button_box" in all_view_text
        and "action_confirm" in all_view_text
        and "action_create_invoice" in all_view_text
        and "action_view_booking" in all_view_text
    )
    checks.append(("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN", form_quality,
                   "workflow/statusbar/smart-button/one2many navigation"))

    coverage = view_coverage(loaded_views, sorted(persistent))
    expected = {"search", "list", "form"}
    missing_coverage = {m: sorted(expected - got) for m, got in coverage.items() if expected - got}
    checks.append(("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL",
                   (ROOT / "docs/CLINIC_BOOKING_UI_UX_MATRIX.md").exists() and not missing_coverage,
                   f"missing={missing_coverage}"))
    checks.append(("HARD_GATE_8_SEARCH_VIEW_WAJIB",
                   all("search" in coverage[m] for m in persistent), f"{sum('search' in coverage[m] for m in persistent)}/24"))
    checks.append(("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY",
                   all("list" in coverage[m] for m in persistent), f"{sum('list' in coverage[m] for m in persistent)}/24"))

    acl_path = ROOT / "security/ir.model.access.csv"
    acl_text = acl_path.read_text(encoding="utf-8") if acl_path.exists() else ""
    # CSV external ids convert dots to underscores, so compare explicit model refs.
    acl_refs = set()
    if acl_path.exists():
        with acl_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                acl_refs.add(row.get("model_id:id", ""))
    missing_acl = [m for m in persistent if f"model_{m.replace('.', '_')}" not in acl_refs]
    no_public_portal = "base.group_public" not in acl_text and "base.group_portal" not in acl_text
    rules_path = ROOT / "security/clinic_booking_rules.xml"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    missing_rules = [m for m in persistent if f"model_{m.replace('.', '_')}" not in rules_text]
    checks.append(("HARD_GATE_10_SECURITY_OVER_UI",
                   not missing_acl and not missing_rules and no_public_portal,
                   f"missing_acl={missing_acl[:5]}, missing_rules={missing_rules[:5]}"))

    checks.append(("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY",
                   len(list((ROOT / "models").glob("booking_*.py"))) >= 8 and len(loaded_views) >= 5,
                   "domain-split Python/XML files"))
    checks.append(("HARD_GATE_13_USEFUL_COMMENTS",
                   "Odoo 19" in active_text and "compat" in active_text.lower(),
                   "version/compatibility intent documented"))
    checks.append(("HARD_GATE_14_CODEX_RETRY_LIMIT",
                   contract.get("max_focused_repair_attempts_per_blocker") == 3
                   and "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3" in agents,
                   "3-attempt hard stop"))
    checks.append(("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
                   (ROOT / "docs/CLINIC_BOOKING_ENTERPRISE_COMPLETENESS_MATRIX.md").exists(),
                   "separate enterprise matrix"))

    failures = 0
    for label, ok, detail in checks:
        if not emit(label, ok, detail):
            failures += 1

    owner_pass = sum(1 for label, ok, _ in checks if label.startswith("HARD_GATE_") and ok)
    print("-" * 90)
    print(f"OWNER_HARD_GATES_PASS: {owner_pass} / 15")
    if failures:
        print("CLINIC_BOOKING_STATIC_MOVE_FORWARD_READY: NO")
        return 1
    print("CLINIC_BOOKING_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_BOOKING_MOVE_FORWARD_READY: PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
