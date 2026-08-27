from pathlib import Path, PurePosixPath
import ast
import re
import sys
from collections import defaultdict
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]

if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: python clinic_incident_latest_bundle_audit.py "
        "<clinic19a-latest.md>"
    )

SOURCE = Path(sys.argv[1]).resolve()
raw = SOURCE.read_text(encoding="utf-8", errors="replace")

header_re = re.compile(
    r"=== Begin File , Folder: (.*?), File Name: (.*?) ===\r?\n"
)
sections = []
for match in header_re.finditer(raw):
    end = raw.find("=== End File ===", match.end())
    if end >= 0:
        sections.append(
            (
                match.group(1),
                match.group(2),
                raw[match.end():end].lstrip("\r\n"),
            )
        )


def addon_from(folder):
    if "/clinic19a/" not in folder:
        return None
    return folder.split(
        "/clinic19a/",
        1,
    )[1].split("/", 1)[0]


addon_files = defaultdict(dict)
manifests = {}

for folder, name, content in sections:
    addon = addon_from(folder)
    if not addon:
        continue

    suffix = folder.split(
        f"/clinic19a/{addon}",
        1,
    )[1].lstrip("/")
    rel = f"{suffix}/{name}" if suffix else name
    addon_files[addon][rel] = content

    if rel == "__manifest__.py":
        try:
            manifests[addon] = ast.literal_eval(content)
        except Exception:
            pass


if len(sections) != 1562:
    raise RuntimeError(
        f"Expected 1562 authoritative sections, got {len(sections)}"
    )
if len(manifests) != 37:
    raise RuntimeError(
        f"Expected 37 ClinicOne manifests, got {len(manifests)}"
    )
if (
    manifests.get(
        "clinic_telemedicine_secure_messaging",
        {},
    ).get("version")
    != "19.0.1.0.1"
):
    raise RuntimeError(
        "Frozen addon 33 must be "
        "clinic_telemedicine_secure_messaging 19.0.1.0.1"
    )
if "clinic_incident_event" in manifests:
    raise RuntimeError(
        "clinic_incident_event must be absent in the baseline "
        "because addon 34 is a new owner"
    )


def live_model_files(addon):
    """Recursively follow only Python modules imported by models/__init__.py."""
    files = addon_files[addon]
    live = set()
    visited = set()

    def walk(rel):
        if (
            rel in live
            or rel not in files
            or PurePosixPath(rel).name.startswith("0")
        ):
            return

        live.add(rel)

        if (
            PurePosixPath(rel).name != "__init__.py"
            or rel in visited
        ):
            return

        visited.add(rel)

        try:
            tree = ast.parse(files[rel])
        except SyntaxError:
            return

        base = str(PurePosixPath(rel).parent)
        if base == ".":
            base = ""

        for node in tree.body:
            if not (
                isinstance(node, ast.ImportFrom)
                and node.level == 1
            ):
                continue

            if node.module is None:
                for alias in node.names:
                    candidates = [
                        (
                            f"{base}/{alias.name}.py"
                            if base
                            else f"{alias.name}.py"
                        ),
                        (
                            f"{base}/{alias.name}/__init__.py"
                            if base
                            else f"{alias.name}/__init__.py"
                        ),
                    ]
                    for candidate in candidates:
                        if candidate in files:
                            walk(candidate)
                            break
            else:
                subbase = (
                    f"{base}/{node.module}"
                    if base
                    else node.module
                )

                init_rel = f"{subbase}/__init__.py"
                if init_rel in files:
                    walk(init_rel)

                for alias in node.names:
                    candidates = [
                        f"{subbase}/{alias.name}.py",
                        f"{subbase}/{alias.name}/__init__.py",
                    ]
                    for candidate in candidates:
                        if candidate in files:
                            walk(candidate)
                            break

    walk("models/__init__.py")
    return live


live_files = {
    addon: live_model_files(addon)
    for addon in addon_files
}

if (
    "models/core/emar_administration.py"
    not in live_files["clinic_emar"]
):
    raise RuntimeError(
        "Recursive live-import graph failed to reach "
        "clinic_emar Administration owner"
    )


fields = defaultdict(dict)
methods = defaultdict(set)
parents = defaultdict(set)
delegates = defaultdict(set)
selections = defaultdict(dict)


def parse_models(addon, module, content):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return

    constants = {}
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        for target in stmt.targets:
            if not isinstance(target, ast.Name):
                continue
            try:
                constants[target.id] = ast.literal_eval(stmt.value)
            except Exception:
                pass

    for cls in (
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
    ):
        model_name = None
        inherit = None
        inherits = None

        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign):
                continue

            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue

                try:
                    value = ast.literal_eval(stmt.value)
                except Exception:
                    value = None

                if target.id == "_name" and isinstance(value, str):
                    model_name = value
                elif target.id == "_inherit":
                    inherit = value
                elif target.id == "_inherits":
                    inherits = value

        model = (
            model_name
            if isinstance(model_name, str)
            else inherit
            if isinstance(inherit, str)
            else None
        )
        if not model:
            continue

        if (
            isinstance(inherit, str)
            and model_name
            and inherit != model_name
        ):
            parents[model].add(inherit)

        elif isinstance(inherit, list):
            parents[model].update(
                value
                for value in inherit
                if isinstance(value, str)
            )

        if isinstance(inherits, dict):
            delegates[model].update(
                value
                for value in inherits
                if isinstance(value, str)
            )

        for stmt in cls.body:
            if isinstance(
                stmt,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                methods[model].add(stmt.name)

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

            field_type = func.attr
            comodel = None
            selection = None
            related = None
            computed = False
            stored = False
            searchable = False

            if stmt.value.args:
                first_node = stmt.value.args[0]
                try:
                    first = ast.literal_eval(first_node)
                except Exception:
                    first = (
                        constants.get(first_node.id)
                        if isinstance(first_node, ast.Name)
                        else None
                    )

                if (
                    field_type in (
                        "Many2one",
                        "One2many",
                        "Many2many",
                    )
                    and isinstance(first, str)
                ):
                    comodel = first
                elif field_type == "Selection":
                    selection = first

            for kw in stmt.value.keywords:
                if kw.arg == "comodel_name":
                    try:
                        value = ast.literal_eval(kw.value)
                    except Exception:
                        value = None
                    if isinstance(value, str):
                        comodel = value

                elif kw.arg == "selection":
                    try:
                        selection = ast.literal_eval(kw.value)
                    except Exception:
                        selection = (
                            constants.get(kw.value.id)
                            if isinstance(kw.value, ast.Name)
                            else None
                        )

                elif kw.arg == "related":
                    try:
                        related = ast.literal_eval(kw.value)
                    except Exception:
                        related = None

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

                fields[model][target.id] = {
                    "type": field_type,
                    "comodel": comodel,
                    "related": related,
                    "computed": computed,
                    "store": stored,
                    "search": searchable,
                    "addon": addon,
                    "module": module,
                }

                if isinstance(selection, (list, tuple)):
                    selections[model][target.id] = [
                        item[0]
                        for item in selection
                        if isinstance(item, (list, tuple)) and item
                    ]


for addon, rels in live_files.items():
    for rel in rels:
        if rel.endswith("__init__.py"):
            continue
        parse_models(
            addon,
            rel,
            addon_files[addon][rel],
        )

for path in sorted((ROOT / "models").glob("*.py")):
    if (
        path.name == "__init__.py"
        or path.name.startswith("0")
    ):
        continue

    parse_models(
        "clinic_incident_event",
        f"models/{path.name}",
        path.read_text(encoding="utf-8"),
    )


def field_info(model, name, trail=None):
    if name == "id":
        return {
            "type": "integer",
            "comodel": None,
            "related": None,
            "computed": False,
            "store": True,
            "search": True,
        }

    trail = set(trail or ())
    key = (model, name)
    if key in trail:
        return None
    trail.add(key)

    if name in fields.get(model, {}):
        return fields[model][name]

    for parent in (
        parents.get(model, set())
        | delegates.get(model, set())
    ):
        found = field_info(parent, name, trail)
        if found:
            return found

    return None


def resolved_field_info(model, name, trail=None):
    trail = set(trail or ())
    key = (model, name)
    if key in trail:
        return None
    trail.add(key)

    info = field_info(model, name)
    if not info:
        return None

    if info.get("comodel") or not info.get("related"):
        return info

    current_model = model
    final_info = info

    for part in info["related"].split("."):
        target = field_info(current_model, part)
        if not target:
            return info

        final_info = target

        if target.get("comodel"):
            current_model = target["comodel"]
        elif target.get("related"):
            nested = resolved_field_info(
                current_model,
                part,
                trail,
            )
            if nested and nested.get("comodel"):
                current_model = nested["comodel"]

    merged = dict(info)
    merged["comodel"] = final_info.get("comodel")
    return merged


def method_exists(model, name, trail=None):
    trail = set(trail or ())
    if model in trail:
        return False
    trail.add(model)

    if name in methods.get(model, set()):
        return True

    return any(
        method_exists(parent, name, trail)
        for parent in (
            parents.get(model, set())
            | delegates.get(model, set())
        )
    )


contracts = {
    "res.company": [
        "default_branch_id",
        "policy_branch_scope_incident_event",
    ],
    "res.users": [
        "allowed_branch_ids",
        "working_branch_id",
    ],
    "res.partner": [
        "patient_id",
        "branch_id",
    ],
    "clinic.patient": [
        "partner_id",
        "company_id",
    ],
    "clinic.staff": [
        "partner_id",
        "company_id",
        "incident_count",
    ],
    "clinic.staff.kpi": [
        "staff_id",
        "company_id",
        "assignments_count",
        "incidents_count",
        "incidents_rate_per_100_assign",
    ],
    "clinic.doctor": [
        "company_id",
        "partner_id",
    ],
    "booking.booking": [
        "company_id",
        "patient_id",
        "doctor_id",
        "start_datetime",
        "state",
    ],
    "clinic.queue": [
        "company_id",
        "patient_id",
        "doctor_id",
        "room_id",
        "checkin_time",
        "state",
    ],
    "clinic.emar.administration": [
        "company_id",
        "patient_id",
        "doctor_id",
        "state",
    ],
    "clinic.feedback.escalation": [
        "company_id",
        "branch_id",
        "patient_id",
        "severity",
        "category",
        "state",
    ],
    "clinic.telemedicine.session": [
        "company_id",
        "branch_id",
        "patient_id",
        "doctor_id",
        "host_staff_id",
        "encounter_id",
        "booking_id",
        "state",
    ],
    "clinic.telemedicine.thread": [
        "company_id",
        "branch_id",
        "patient_id",
        "doctor_id",
        "handler_id",
        "session_id",
        "attention_required",
        "state",
    ],
    "clinic.adverse.event": [
        "company_id",
        "encounter_id",
        "patient_id",
        "partner_id",
        "doctor_id",
        "room_id",
        "date_occurred",
        "date_detected",
        "reported_by_id",
        "classification",
        "severity",
        "recurrence_risk",
        "description",
        "immediate_action",
        "patient_impact",
        "needs_reporting",
        "to_regulator",
        "regulator_body",
        "regulator_reference",
        "state",
        "action_ids",
        "followup_ids",
    ],
    "clinic.ae.action": [
        "ae_id",
        "company_id",
        "done",
        "effectiveness_note",
    ],
}

missing = {
    model: [
        name
        for name in required
        if not field_info(model, name)
    ]
    for model, required in contracts.items()
}
missing = {
    model: names
    for model, names in missing.items()
    if names
}
if missing:
    raise RuntimeError(
        f"Live cross-addon contract missing: {missing}"
    )


type_contracts = {
    ("res.partner", "patient_id"): "clinic.patient",
    ("clinic.patient", "partner_id"): "res.partner",
    ("clinic.staff", "partner_id"): "res.partner",
    ("booking.booking", "patient_id"): "res.partner",
    ("booking.booking", "doctor_id"): "clinic.doctor",
    ("clinic.queue", "patient_id"): "res.partner",
    ("clinic.queue", "doctor_id"): "hr.employee",
    ("clinic.queue", "room_id"): "clinic.room",
    ("clinic.emar.administration", "patient_id"): "clinic.patient",
    ("clinic.emar.administration", "doctor_id"): "clinic.doctor",
    ("clinic.feedback.escalation", "patient_id"): "res.partner",
    ("clinic.telemedicine.session", "patient_id"): "clinic.patient",
    ("clinic.telemedicine.session", "doctor_id"): "clinic.doctor",
    ("clinic.telemedicine.thread", "patient_id"): "clinic.patient",
    ("clinic.telemedicine.thread", "handler_id"): "clinic.staff",
    ("clinic.adverse.event", "patient_id"): "clinic.patient",
    ("clinic.adverse.event", "doctor_id"): "clinic.doctor",
    ("clinic.adverse.event", "action_ids"): "clinic.ae.action",
    ("clinic.ae.action", "ae_id"): "clinic.adverse.event",
    ("clinic.incident", "involved_staff_ids"): "clinic.staff",
}

for (model, field), expected in type_contracts.items():
    info = resolved_field_info(model, field)
    actual = info.get("comodel") if info else None
    if actual != expected:
        raise RuntimeError(
            f"{model}.{field}: expected {expected}, got {actual}"
        )


state_contracts = {
    ("clinic.adverse.event", "state"): {
        "draft",
        "under_review",
        "closed",
        "cancelled",
    },
    ("booking.booking", "state"): {
        "draft",
        "confirmed",
        "in_progress",
        "done",
        "cancelled",
    },
    ("clinic.emar.administration", "state"): {
        "draft",
        "confirmed",
        "in_progress",
        "done",
        "cancelled",
    },
    ("clinic.telemedicine.session", "state"): {
        "draft",
        "scheduled",
        "ready",
        "in_progress",
        "completed",
        "cancelled",
        "no_show",
    },
    ("clinic.telemedicine.thread", "state"): {
        "open",
        "closed",
        "archived",
    },
}

for key, required in state_contracts.items():
    actual = set(
        selections.get(key[0], {}).get(key[1], [])
    )
    missing_states = required - actual
    if missing_states:
        raise RuntimeError(
            f"{key[0]}.{key[1]} missing states "
            f"{sorted(missing_states)}, actual={sorted(actual)}"
        )


# Historical Staff contract must be live, not a file-system guess.
if not method_exists("clinic.staff", "action_open_incidents"):
    raise RuntimeError(
        "Live clinic.staff.action_open_incidents contract is missing"
    )
for field in (
    "incident_count",
    "incidents_count",
    "incidents_rate_per_100_assign",
):
    model = (
        "clinic.staff"
        if field == "incident_count"
        else "clinic.staff.kpi"
    )
    if not field_info(model, field):
        raise RuntimeError(
            f"Historical Staff Incident contract missing: {model}.{field}"
        )


# Addon 34 may extend but never own Adverse Event / AE CAPA.
addon_model_source = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "models").glob("*.py"))
)
for owner in (
    "clinic.adverse.event",
    "clinic.ae.action",
    "clinic.ae.followup",
):
    if (
        f'_name = "{owner}"' in addon_model_source
        or f"_name = '{owner}'" in addon_model_source
    ):
        raise RuntimeError(
            f"Addon 34 duplicates upstream owner: {owner}"
        )


# Combined view/model/object-button audit with nested x2many model switching.
view_errors = []


def validate_node(node, model, path):
    if node.tag == "field":
        name = node.attrib.get("name")
        if name:
            info = resolved_field_info(model, name)

            if not info:
                view_errors.append(
                    f"{path.name}: unknown field {model}.{name}"
                )
                info = None

            if (
                list(node)
                and info
                and info.get("comodel")
            ):
                for child in list(node):
                    validate_node(
                        child,
                        info["comodel"],
                        path,
                    )
                return

    if (
        node.tag == "button"
        and node.attrib.get("type") == "object"
    ):
        method = node.attrib.get("name")
        if method and not method_exists(model, method):
            view_errors.append(
                f"{path.name}: unknown object method "
                f"{model}.{method}"
            )

    for child in list(node):
        validate_node(child, model, path)


for path in sorted((ROOT / "views").glob("*.xml")):
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue

        model_node = record.find("./field[@name='model']")
        arch_node = record.find("./field[@name='arch']")
        if model_node is None or arch_node is None:
            continue

        model = (model_node.text or "").strip()
        for child in list(arch_node):
            validate_node(child, model, path)

if view_errors:
    raise RuntimeError(
        "Combined View/Model/Object-button audit failed:\n"
        + "\n".join(sorted(set(view_errors)))
    )


# Search-domain searchability.
search_errors = []

for path in sorted((ROOT / "views").glob("*.xml")):
    root = ET.parse(path).getroot()
    for record in root.iter("record"):
        if record.attrib.get("model") != "ir.ui.view":
            continue

        model_node = record.find("./field[@name='model']")
        if model_node is None:
            continue
        model = (model_node.text or "").strip()

        for filter_node in record.findall(".//filter[@domain]"):
            try:
                domain = ast.literal_eval(
                    filter_node.attrib["domain"]
                )
            except Exception:
                continue

            def names(value):
                if (
                    isinstance(value, tuple)
                    and len(value) >= 3
                    and isinstance(value[0], str)
                ):
                    yield value[0]
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        yield from names(item)

            for dotted in names(domain):
                base = dotted.split(".", 1)[0]
                info = field_info(model, base)

                if not info:
                    search_errors.append(
                        f"{path.name}: unknown Search field "
                        f"{model}.{base}"
                    )
                elif (
                    info["computed"]
                    and not info["store"]
                    and not info["search"]
                ):
                    search_errors.append(
                        f"{path.name}: non-searchable computed "
                        f"{model}.{base}"
                    )

if search_errors:
    raise RuntimeError(
        "Search-domain audit failed:\n"
        + "\n".join(sorted(set(search_errors)))
    )


# Stable inherited-view policy.
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
expected_inherits = {
    "base.view_partner_form",
    "base.res_config_settings_view_form",
}
if inherit_refs != expected_inherits:
    raise RuntimeError(
        f"Unexpected inherited-view refs: {sorted(inherit_refs)}"
    )


# QWeb/report contract.
report_text = (
    ROOT / "report/incident_report.xml"
).read_text(encoding="utf-8")
for token in (
    'id="action_report_incident_case"',
    'id="report_incident_case_document"',
    'ref="model_clinic_incident"',
    "web.external_layout",
):
    if token not in report_text:
        raise RuntimeError(
            f"QWeb Incident report contract missing: {token}"
        )


# Secure Telemedicine content must not cross the owner boundary.
integration_source = (
    (ROOT / "models/source_integration.py").read_text(encoding="utf-8")
    + (ROOT / "models/operational_integration.py").read_text(encoding="utf-8")
)
for forbidden in (
    ".message_ids",
    "message.body",
    "thread.internal_note",
):
    if forbidden in integration_source:
        raise RuntimeError(
            f"Secure Telemedicine content-copy regression: {forbidden}"
        )


manifest = ast.literal_eval(
    (ROOT / "__manifest__.py").read_text(encoding="utf-8")
)
custom_deps = [
    dep
    for dep in manifest["depends"]
    if dep.startswith("clinic_")
]

missing_deps = [
    dep
    for dep in custom_deps
    if dep not in manifests
]
if missing_deps:
    raise RuntimeError(
        f"Missing latest-bundle dependencies: {missing_deps}"
    )

future = {
    "clinic_quality",
    "clinic_integration_api",
    "clinic_audit",
    "clinic_analytics",
}
future_found = sorted(
    future.intersection(custom_deps)
)
if future_found:
    raise RuntimeError(
        f"Future ClinicOne dependency found: {future_found}"
    )


print("LATEST COMBINED CLINIC_INCIDENT_EVENT CONTRACT AUDIT: PASS")
print("Bundle sections                         :", len(sections))
print("ClinicOne manifests                     :", len(manifests))
print(
    "Recursive live-import packages audited  :",
    sum(bool(value) for value in live_files.values()),
)
print("clinic_telemedicine_secure_messaging    : 19.0.1.0.1")
print("clinic_incident_event baseline          : ABSENT / NEW OWNER")
print(
    "Direct custom dependencies              :",
    f"{len(custom_deps)}/{len(custom_deps)} AVAILABLE",
)
print("Live cross-addon models checked         :", len(contracts))
print("Nested eMAR import graph                : PASS")
print("Feedback related patient type           : res.partner / PASS")
print("Historical Staff incident contract      : PASS")
print("Adverse Event / AE CAPA ownership       : PRESERVED")
print("Queue doctor = hr.employee              : PRESERVED / NOT MIS-MAPPED")
print("View/Model/Object-button audit          : PASS")
print("Nested One2many model switching         : PASS")
print("Search-domain searchability             : PASS")
print("Stable inherited-view policy            : PASS")
print("QWeb Incident Case Summary              : PASS")
print("Telemedicine secure-content non-copy    : PASS")
