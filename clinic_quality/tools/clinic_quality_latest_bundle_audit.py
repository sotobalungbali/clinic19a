from pathlib import Path, PurePosixPath
import ast
import re
import sys
from collections import defaultdict
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]

if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: python clinic_quality_latest_bundle_audit.py "
        "<clinic19a-latest.md>"
    )

SOURCE = Path(sys.argv[1]).resolve()
raw = SOURCE.read_text(
    encoding="utf-8",
    errors="replace",
)

header_re = re.compile(
    r"=== Begin File , Folder: (.*?), File Name: (.*?) ===\r?\n"
)

sections = []
for match in header_re.finditer(raw):
    end = raw.find(
        "=== End File ===",
        match.end(),
    )
    if end >= 0:
        sections.append(
            (
                match.group(1),
                match.group(2),
                raw[
                    match.end():end
                ].lstrip("\r\n"),
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
    rel = (
        f"{suffix}/{name}"
        if suffix
        else name
    )
    addon_files[addon][rel] = content

    if rel == "__manifest__.py":
        try:
            manifests[addon] = ast.literal_eval(
                content
            )
        except Exception:
            pass


if len(sections) != 1608:
    raise RuntimeError(
        f"Expected 1608 authoritative sections, got {len(sections)}"
    )

if len(manifests) != 38:
    raise RuntimeError(
        f"Expected 38 ClinicOne manifests, got {len(manifests)}"
    )

if (
    manifests.get(
        "clinic_incident_event",
        {},
    ).get("version")
    != "19.0.1.0.0"
):
    raise RuntimeError(
        "Latest installed upstream must contain "
        "clinic_incident_event 19.0.1.0.0"
    )

if "clinic_quality" in manifests:
    raise RuntimeError(
        "clinic_quality must be absent in the baseline because addon 35 "
        "is a new owner"
    )


def live_model_files(addon):
    """Recursively follow only model modules imported by models/__init__.py."""
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

        base = str(
            PurePosixPath(rel).parent
        )
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

                init_rel = (
                    f"{subbase}/__init__.py"
                )
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
    not in live_files.get(
        "clinic_emar",
        set(),
    )
):
    raise RuntimeError(
        "Recursive import walk failed to reach current eMAR owner."
    )


fields = defaultdict(dict)
methods = defaultdict(set)
parents = defaultdict(set)
delegates = defaultdict(set)
selections = defaultdict(dict)


def parse_models(
    addon,
    module,
    content,
):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return

    constants = {}
    for stmt in tree.body:
        if not isinstance(
            stmt,
            ast.Assign,
        ):
            continue

        for target in stmt.targets:
            if not isinstance(
                target,
                ast.Name,
            ):
                continue

            try:
                constants[
                    target.id
                ] = ast.literal_eval(
                    stmt.value
                )
            except Exception:
                pass

    for cls in (
        node
        for node in tree.body
        if isinstance(
            node,
            ast.ClassDef,
        )
    ):
        model_name = None
        inherit = None
        inherits = None

        for stmt in cls.body:
            if not isinstance(
                stmt,
                ast.Assign,
            ):
                continue

            for target in stmt.targets:
                if not isinstance(
                    target,
                    ast.Name,
                ):
                    continue

                try:
                    value = ast.literal_eval(
                        stmt.value
                    )
                except Exception:
                    value = None

                if (
                    target.id == "_name"
                    and isinstance(
                        value,
                        str,
                    )
                ):
                    model_name = value

                elif target.id == "_inherit":
                    inherit = value

                elif target.id == "_inherits":
                    inherits = value

        model = (
            model_name
            if isinstance(
                model_name,
                str,
            )
            else inherit
            if isinstance(
                inherit,
                str,
            )
            else None
        )

        if not model:
            continue

        if (
            isinstance(
                inherit,
                str,
            )
            and model_name
            and inherit != model_name
        ):
            parents[model].add(
                inherit
            )

        elif isinstance(
            inherit,
            list,
        ):
            parents[model].update(
                value
                for value in inherit
                if isinstance(
                    value,
                    str,
                )
            )

        if isinstance(
            inherits,
            dict,
        ):
            delegates[model].update(
                value
                for value in inherits
                if isinstance(
                    value,
                    str,
                )
            )

        for stmt in cls.body:
            if isinstance(
                stmt,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                methods[model].add(
                    stmt.name
                )

            if not (
                isinstance(
                    stmt,
                    ast.Assign,
                )
                and isinstance(
                    stmt.value,
                    ast.Call,
                )
            ):
                continue

            func = stmt.value.func
            if not (
                isinstance(
                    func,
                    ast.Attribute,
                )
                and isinstance(
                    func.value,
                    ast.Name,
                )
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
                first_node = (
                    stmt.value.args[0]
                )

                try:
                    first = ast.literal_eval(
                        first_node
                    )
                except Exception:
                    first = (
                        constants.get(
                            first_node.id
                        )
                        if isinstance(
                            first_node,
                            ast.Name,
                        )
                        else None
                    )

                if (
                    field_type
                    in (
                        "Many2one",
                        "One2many",
                        "Many2many",
                    )
                    and isinstance(
                        first,
                        str,
                    )
                ):
                    comodel = first

                elif field_type == "Selection":
                    selection = first

            for kw in stmt.value.keywords:
                if kw.arg == "comodel_name":
                    try:
                        value = ast.literal_eval(
                            kw.value
                        )
                    except Exception:
                        value = None

                    if isinstance(
                        value,
                        str,
                    ):
                        comodel = value

                elif kw.arg == "selection":
                    try:
                        selection = ast.literal_eval(
                            kw.value
                        )
                    except Exception:
                        selection = (
                            constants.get(
                                kw.value.id
                            )
                            if isinstance(
                                kw.value,
                                ast.Name,
                            )
                            else None
                        )

                elif kw.arg == "related":
                    try:
                        related = ast.literal_eval(
                            kw.value
                        )
                    except Exception:
                        related = None

                elif kw.arg == "compute":
                    computed = True

                elif kw.arg == "store":
                    try:
                        stored = bool(
                            ast.literal_eval(
                                kw.value
                            )
                        )
                    except Exception:
                        pass

                elif kw.arg == "search":
                    searchable = True

            for target in stmt.targets:
                if not isinstance(
                    target,
                    ast.Name,
                ):
                    continue

                fields[model][
                    target.id
                ] = {
                    "type": field_type,
                    "comodel": comodel,
                    "related": related,
                    "computed": computed,
                    "store": stored,
                    "search": searchable,
                    "addon": addon,
                    "module": module,
                }

                if isinstance(
                    selection,
                    (list, tuple),
                ):
                    selections[
                        model
                    ][target.id] = [
                        item[0]
                        for item in selection
                        if isinstance(
                            item,
                            (list, tuple),
                        )
                        and item
                    ]


for addon, rels in live_files.items():
    for rel in rels:
        if rel.endswith(
            "__init__.py"
        ):
            continue

        parse_models(
            addon,
            rel,
            addon_files[addon][rel],
        )


for path in sorted(
    (ROOT / "models").glob("*.py")
):
    if (
        path.name == "__init__.py"
        or path.name.startswith("0")
    ):
        continue

    parse_models(
        "clinic_quality",
        f"models/{path.name}",
        path.read_text(
            encoding="utf-8"
        ),
    )


def field_info(
    model,
    name,
    trail=None,
):
    if name == "id":
        return {
            "type": "integer",
            "comodel": None,
            "related": None,
            "computed": False,
            "store": True,
            "search": True,
        }

    trail = set(
        trail
        or ()
    )
    key = (
        model,
        name,
    )

    if key in trail:
        return None

    trail.add(key)

    if name in fields.get(
        model,
        {},
    ):
        return fields[
            model
        ][name]

    for parent in (
        parents.get(
            model,
            set(),
        )
        | delegates.get(
            model,
            set(),
        )
    ):
        found = field_info(
            parent,
            name,
            trail,
        )
        if found:
            return found

    return None


def resolved_field_info(
    model,
    name,
    trail=None,
):
    trail = set(
        trail
        or ()
    )
    key = (
        model,
        name,
    )

    if key in trail:
        return None

    trail.add(key)

    info = field_info(
        model,
        name,
    )
    if not info:
        return None

    if (
        info.get("comodel")
        or not info.get("related")
    ):
        return info

    current_model = model
    final_info = info

    for part in info[
        "related"
    ].split("."):
        target = field_info(
            current_model,
            part,
        )
        if not target:
            return info

        final_info = target

        if target.get(
            "comodel"
        ):
            current_model = target[
                "comodel"
            ]

        elif target.get(
            "related"
        ):
            nested = resolved_field_info(
                current_model,
                part,
                trail,
            )
            if (
                nested
                and nested.get(
                    "comodel"
                )
            ):
                current_model = nested[
                    "comodel"
                ]

    merged = dict(info)
    merged[
        "comodel"
    ] = final_info.get(
        "comodel"
    )
    return merged


def method_exists(
    model,
    name,
    trail=None,
):
    trail = set(
        trail
        or ()
    )

    if model in trail:
        return False

    trail.add(model)

    if name in methods.get(
        model,
        set(),
    ):
        return True

    return any(
        method_exists(
            parent,
            name,
            trail,
        )
        for parent in (
            parents.get(
                model,
                set(),
            )
            | delegates.get(
                model,
                set(),
            )
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
    "clinic.branch": [
        "company_id",
        "name",
        "code",
    ],
    "clinic.room": [
        "company_id",
        "name",
        "code",
    ],
    "clinic.staff": [
        "company_id",
        "branch_id",
        "partner_id",
        "name",
    ],
    "clinic.doctor": [
        "company_id",
        "partner_id",
        "user_id",
        "name",
    ],
    "clinic.treatment": [
        "company_id",
        "name",
        "code",
    ],
    "stock.lot": [
        "clinic_quality_state",
        "clinic_quarantine_reason",
    ],
    "clinic.incident.category": [
        "incident_type",
        "default_severity",
        "requires_investigation",
        "requires_capa",
    ],
    "clinic.incident": [
        "company_id",
        "branch_id",
        "incident_type",
        "classification",
        "severity",
        "harm_level",
        "recurrence_risk",
        "occurred_at",
        "involved_staff_ids",
        "doctor_id",
        "room_id",
        "state",
    ],
}

missing = {
    model: [
        name
        for name in required
        if not field_info(
            model,
            name,
        )
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
        f"Live cross-addon Quality contract missing: {missing}"
    )


type_contracts = {
    ("res.users", "allowed_branch_ids"): "clinic.branch",
    ("res.users", "working_branch_id"): "clinic.branch",
    ("clinic.branch", "company_id"): "res.company",
    ("clinic.room", "company_id"): "res.company",
    ("clinic.staff", "branch_id"): "clinic.branch",
    ("clinic.staff", "partner_id"): "res.partner",
    ("clinic.doctor", "partner_id"): "res.partner",
    ("clinic.treatment", "company_id"): "res.company",
    ("clinic.incident", "involved_staff_ids"): "clinic.staff",
    ("clinic.incident", "doctor_id"): "clinic.doctor",
    ("clinic.incident", "room_id"): "clinic.room",
}

for (
    model,
    field,
), expected in type_contracts.items():
    info = resolved_field_info(
        model,
        field,
    )
    actual = (
        info.get(
            "comodel"
        )
        if info
        else None
    )

    if actual != expected:
        raise RuntimeError(
            f"{model}.{field}: expected {expected}, got {actual}"
        )


inventory_states = set(
    selections.get(
        "stock.lot",
        {},
    ).get(
        "clinic_quality_state",
        [],
    )
)

if inventory_states != {
    "released",
    "on_hold",
    "rejected",
}:
    raise RuntimeError(
        "Inventory Lot Quality State changed unexpectedly: "
        f"{sorted(inventory_states)}"
    )


incident_types = set(
    selections.get(
        "clinic.incident.category",
        {},
    ).get(
        "incident_type",
        [],
    )
)

quality_incident_types = set(
    selections.get(
        "clinic.quality.check.template",
        {},
    ).get(
        "failure_incident_type",
        [],
    )
)

if quality_incident_types != incident_types:
    raise RuntimeError(
        "Quality failure Incident Type selection is not exactly compatible "
        "with addon-34 Incident types."
    )


incident_states = set(
    selections.get(
        "clinic.incident",
        {},
    ).get(
        "state",
        [],
    )
)

expected_incident_states = {
    "draft",
    "reported",
    "triage",
    "investigation",
    "action_plan",
    "verification",
    "closed",
    "cancelled",
}

if not expected_incident_states.issubset(
    incident_states
):
    raise RuntimeError(
        "Addon-34 Incident workflow contract changed unexpectedly."
    )


for method in (
    "_category_for_type",
    "_log_timeline",
):
    if not method_exists(
        "clinic.incident",
        method,
    ):
        raise RuntimeError(
            f"Required addon-34 Incident helper missing: {method}"
        )


# Ownership preservation.
addon_model_source = "\n".join(
    path.read_text(
        encoding="utf-8"
    )
    for path in sorted(
        (ROOT / "models").glob("*.py")
    )
)

for owner in (
    "clinic.incident",
    "clinic.incident.action",
    "clinic.incident.investigation",
    "clinic.room",
    "clinic.staff",
    "clinic.doctor",
    "clinic.treatment",
    "stock.lot",
):
    if (
        f'_name = "{owner}"'
        in addon_model_source
        or f"_name = '{owner}'"
        in addon_model_source
    ):
        raise RuntimeError(
            f"Addon 35 duplicates upstream owner: {owner}"
        )


# Combined View / Model / Object-button audit, including nested x2many model
# switching.
view_errors = []


def validate_node(
    node,
    model,
    path,
):
    if node.tag == "field":
        name = node.attrib.get(
            "name"
        )

        if name:
            info = resolved_field_info(
                model,
                name,
            )

            if not info:
                view_errors.append(
                    f"{path.name}: unknown field {model}.{name}"
                )
                info = None

            if (
                list(node)
                and info
                and info.get(
                    "comodel"
                )
            ):
                for child in list(node):
                    validate_node(
                        child,
                        info[
                            "comodel"
                        ],
                        path,
                    )
                return

    if (
        node.tag == "button"
        and node.attrib.get(
            "type"
        ) == "object"
    ):
        method = node.attrib.get(
            "name"
        )

        if (
            method
            and not method_exists(
                model,
                method,
            )
        ):
            view_errors.append(
                f"{path.name}: unknown object method "
                f"{model}.{method}"
            )

    for child in list(node):
        validate_node(
            child,
            model,
            path,
        )


for path in sorted(
    (ROOT / "views").glob("*.xml")
):
    root = ET.parse(
        path
    ).getroot()

    for record in root.iter(
        "record"
    ):
        if (
            record.attrib.get(
                "model"
            )
            != "ir.ui.view"
        ):
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

        model = (
            model_node.text
            or ""
        ).strip()

        for child in list(
            arch_node
        ):
            validate_node(
                child,
                model,
                path,
            )


if view_errors:
    raise RuntimeError(
        "Combined View/Model/Object-button audit failed:\n"
        + "\n".join(
            sorted(
                set(
                    view_errors
                )
            )
        )
    )


# Search-domain searchability.
search_errors = []

for path in sorted(
    (ROOT / "views").glob("*.xml")
):
    root = ET.parse(
        path
    ).getroot()

    for record in root.iter(
        "record"
    ):
        if (
            record.attrib.get(
                "model"
            )
            != "ir.ui.view"
        ):
            continue

        model_node = record.find(
            "./field[@name='model']"
        )
        if model_node is None:
            continue

        model = (
            model_node.text
            or ""
        ).strip()

        for filter_node in record.findall(
            ".//filter[@domain]"
        ):
            try:
                domain = ast.literal_eval(
                    filter_node.attrib[
                        "domain"
                    ]
                )
            except Exception:
                continue

            def names(value):
                if (
                    isinstance(
                        value,
                        tuple,
                    )
                    and len(value) >= 3
                    and isinstance(
                        value[0],
                        str,
                    )
                ):
                    yield value[0]

                elif isinstance(
                    value,
                    (list, tuple),
                ):
                    for item in value:
                        yield from names(
                            item
                        )

            for dotted in names(
                domain
            ):
                base = dotted.split(
                    ".",
                    1,
                )[0]

                info = field_info(
                    model,
                    base,
                )

                if not info:
                    search_errors.append(
                        f"{path.name}: unknown Search field "
                        f"{model}.{base}"
                    )

                elif (
                    info[
                        "computed"
                    ]
                    and not info[
                        "store"
                    ]
                    and not info[
                        "search"
                    ]
                ):
                    search_errors.append(
                        f"{path.name}: non-searchable computed "
                        f"{model}.{base}"
                    )


if search_errors:
    raise RuntimeError(
        "Search-domain audit failed:\n"
        + "\n".join(
            sorted(
                set(
                    search_errors
                )
            )
        )
    )


# Quality deliberately inherits no custom upstream operational views.
views_text = "\n".join(
    path.read_text(
        encoding="utf-8"
    )
    for path in (
        ROOT / "views"
    ).glob("*.xml")
)

inherit_refs = set(
    re.findall(
        r'<field name="inherit_id" ref="([^"]+)"',
        views_text,
    )
)

if inherit_refs != {
    "base.res_config_settings_view_form",
}:
    raise RuntimeError(
        "Unexpected inherited-view refs: "
        f"{sorted(inherit_refs)}"
    )


# QWeb report contracts.
report_text = "\n".join(
    path.read_text(
        encoding="utf-8"
    )
    for path in (
        ROOT / "report"
    ).glob("*.xml")
)

for token in (
    'id="action_report_quality_sop"',
    'id="report_quality_sop_document"',
    'id="action_report_quality_check"',
    'id="report_quality_check_document"',
    "web.external_layout",
):
    if token not in report_text:
        raise RuntimeError(
            f"Quality QWeb report contract missing: {token}"
        )


# Inventory disposition must remain read-only from Quality bridge logic.
quality_python = "\n".join(
    path.read_text(
        encoding="utf-8"
    )
    for path in (
        ROOT / "models"
    ).glob("*.py")
)

for forbidden in (
    'write({"clinic_quality_state"',
    '"clinic_quality_state":',
    "'clinic_quality_state':",
    "action_suggest_quarantine_transfer(",
):
    if forbidden in quality_python:
        raise RuntimeError(
            "Quality illegally mutates Inventory disposition: "
            f"{forbidden}"
        )


manifest = ast.literal_eval(
    (
        ROOT / "__manifest__.py"
    ).read_text(
        encoding="utf-8"
    )
)

custom_deps = [
    dep
    for dep in manifest[
        "depends"
    ]
    if dep.startswith(
        "clinic_"
    )
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
    "clinic_integration_api",
    "clinic_audit",
    "clinic_analytics",
}

future_found = sorted(
    future.intersection(
        custom_deps
    )
)

if future_found:
    raise RuntimeError(
        f"Future ClinicOne dependency found: {future_found}"
    )


print(
    "LATEST COMBINED CLINIC_QUALITY CONTRACT AUDIT: PASS"
)
print(
    "Bundle sections                         :",
    len(sections),
)
print(
    "ClinicOne manifests                     :",
    len(manifests),
)
print(
    "Recursive live-import packages audited  :",
    sum(
        bool(value)
        for value in live_files.values()
    ),
)
print(
    "clinic_incident_event                   : 19.0.1.0.0"
)
print(
    "clinic_quality baseline                 : ABSENT / NEW OWNER"
)
print(
    "Direct custom dependencies              :",
    f"{len(custom_deps)}/{len(custom_deps)} AVAILABLE",
)
print(
    "Live upstream models checked            :",
    len(contracts),
)
print(
    "Incident type compatibility             : EXACT / PASS"
)
print(
    "Inventory Lot quality states            : released/on_hold/rejected / PASS"
)
print(
    "Incident/CAPA ownership                 : PRESERVED"
)
print(
    "Inventory disposition ownership         : PRESERVED / NON-MUTATING"
)
print(
    "View/Model/Object-button audit          : PASS"
)
print(
    "Nested One2many model switching         : PASS"
)
print(
    "Search-domain searchability             : PASS"
)
print(
    "Stable inherited-view policy            : PASS"
)
print(
    "SOP + Quality Check QWeb contracts      : PASS"
)
print(
    "Future API/Audit/Analytics dependency   : ABSENT"
)
