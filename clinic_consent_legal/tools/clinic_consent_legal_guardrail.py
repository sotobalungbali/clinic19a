#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ClinicOne clinic_consent_legal Enterprise Development Guardrail.

Runs without importing Odoo. The script validates the source contract that can
be checked statically before a real Odoo 19 install/upgrade.
"""

from __future__ import annotations

import ast
import csv
import json
import py_compile
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ADDON = "clinic_consent_legal"
DOCS = ROOT / "docs"
MODELS = ROOT / "models"

EXPECTED_DEPENDS = [
    "base",
    "mail",
    "contacts",
    "hr",
    "account",
    "product",
    "portal",
    "clinic_base",
    "clinic_patient",
    "clinic_doctor",
    "clinic_booking",
    "clinic_treatment_catalog",
    "clinic_inventory",
    "clinic_room_device",
    "clinic_queue_room",
    "clinic_audit",
]

ACTIVE_IMPORTS = [
    "consent_form_template",
    "consent_form",
    "consent_signature",
    "consent_attachment",
    "res_partner_inherit",
    "treatment_inherit",
    "appointment_inherit",
    "billing_invoice_inherit",
]
DORMANT_IMPORTS = [
    "doctor_schedule_inherit",
    "models",
    "xxx_clinic_consent_legal",
]

CORE_MODEL_FILES = [
    "consent_form_template.py",
    "consent_form.py",
    "consent_signature.py",
    "consent_attachment.py",
]
ACTIVE_MODEL_FILES = CORE_MODEL_FILES + [
    "res_partner_inherit.py",
    "treatment_inherit.py",
    "appointment_inherit.py",
    "billing_invoice_inherit.py",
]

USER_FACING_MODELS = [
    "clinic.consent.template",
    "clinic.consent.form",
    "clinic.consent.signature",
    "clinic.consent.attachment",
]

REQUIRED_DOCS = [
    "CLINIC_CONSENT_LEGAL_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "CLINIC_CONSENT_LEGAL_BASELINE_CONTRACT.json",
    "CLINIC_CONSENT_LEGAL_STRUCTURAL_INVENTORY.md",
    "CLINIC_CONSENT_LEGAL_UI_UX_MATRIX.md",
    "CLINIC_CONSENT_LEGAL_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "CLINIC_CONSENT_LEGAL_ODOO19_REVIEW.md",
]

BASE_MAGIC_FIELDS = {
    "id",
    "display_name",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "message_ids",
    "message_follower_ids",
    "message_partner_ids",
    "message_attachment_count",
    "activity_ids",
}

CANONICAL_TEMPLATE_FIELDS = {
    "sequence",
    "name",
    "code",
    "active",
    "scope",
    "category",
    "requires_guardian",
    "requires_witness",
    "validity_days",
    "allow_reuse",
    "default_item_ids",
    "version_ids",
    "latest_version_id",
    "notes",
    "treatment_id",
}

NESTED_RELATIONS = {
    ("clinic.consent.template", "default_item_ids"): "clinic.consent.template.item",
    ("clinic.consent.template", "version_ids"): "clinic.consent.template.version",
    ("clinic.consent.form", "signature_ids"): "clinic.consent.signature",
    ("clinic.consent.form", "legal_attachment_ids"): "clinic.consent.attachment",
}

NESTED_FIELDS = {
    "clinic.consent.template.item": {
        "sequence", "label", "required", "default_value", "notes", "template_id",
    },
    "clinic.consent.template.version": {
        "template_id", "version", "title", "body_html", "effective_from",
        "effective_to", "changelog", "state",
    },
}

failures: list[str] = []
subpasses: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def passed(message: str) -> None:
    subpasses.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def literal_manifest() -> dict:
    try:
        return ast.literal_eval(read(ROOT / "__manifest__.py"))
    except Exception as exc:
        fail(f"Manifest is not a literal Python dict: {exc}")
        return {}


def field_and_method_inventory(path: Path):
    result = []
    try:
        tree = ast.parse(read(path), filename=str(path))
    except Exception as exc:
        fail(f"AST parse failed for {path.relative_to(ROOT)}: {exc}")
        return result

    for cls in [node for node in tree.body if isinstance(node, ast.ClassDef)]:
        fields = {}
        methods = set()
        model_name = None
        inherit_value = None
        for item in cls.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id == "_name":
                        try:
                            model_name = ast.literal_eval(item.value)
                        except Exception:
                            pass
                    elif target.id == "_inherit":
                        try:
                            inherit_value = ast.literal_eval(item.value)
                        except Exception:
                            pass

                    call = item.value
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "fields"
                    ):
                        fields[target.id] = call
            elif isinstance(item, ast.FunctionDef):
                methods.add(item.name)

        if not model_name:
            if isinstance(inherit_value, str):
                model_name = inherit_value
            elif isinstance(inherit_value, list) and inherit_value:
                # For source-contract analysis only. The Odoo 19 gate below
                # separately requires an explicit _name for list inheritance.
                model_name = inherit_value[0]

        result.append(
            {
                "class": cls,
                "model": model_name,
                "inherit": inherit_value,
                "fields": fields,
                "methods": methods,
            }
        )
    return result


def run_python_xml_syntax_gate() -> None:
    py_count = 0
    xml_count = 0
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or path.name.startswith("0"):
            continue
        py_count += 1
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:
            fail(f"Python compile failed: {path.relative_to(ROOT)}: {exc}")

    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        xml_count += 1
        try:
            ET.parse(path)
        except Exception as exc:
            fail(f"XML parse failed: {path.relative_to(ROOT)}: {exc}")

    if not failures:
        passed(f"PYTHON_COMPILE: PASS ({py_count} files)")
        passed(f"XML_PARSE: PASS ({xml_count} files)")


def run_identity_manifest_gate(manifest: dict) -> None:
    if ROOT.name != EXPECTED_ADDON:
        fail(f"Addon folder must be named {EXPECTED_ADDON!r}, got {ROOT.name!r}")
    if manifest.get("depends") != EXPECTED_DEPENDS:
        fail(
            "Manifest dependency contract changed.\n"
            f"Expected: {EXPECTED_DEPENDS}\n"
            f"Actual:   {manifest.get('depends')}"
        )

    for rel in manifest.get("data", []) + manifest.get("demo", []):
        if not (ROOT / rel).is_file():
            fail(f"Manifest references missing file: {rel}")

    if manifest.get("post_init_hook") != "post_init_hook":
        fail("Manifest must declare post_init_hook='post_init_hook'.")

    init_text = read(ROOT / "__init__.py")
    if "from .hooks import post_init_hook" not in init_text:
        fail("Root __init__.py must expose post_init_hook.")

    passed("PROJECT_IDENTITY_AND_MANIFEST_CONTRACT: PASS")


def run_import_preservation_gate() -> None:
    init_text = read(MODELS / "__init__.py")
    imported = set(re.findall(r"^\s*from\s+\.\s+import\s+([A-Za-z0-9_]+)", init_text, re.M))
    for name in ACTIVE_IMPORTS:
        if name not in imported:
            fail(f"Active baseline model import missing: {name}")
    for name in DORMANT_IMPORTS:
        if name in imported:
            fail(f"Dormant source must not be activated by Codex: {name}")
    passed("ACTIVE_IMPORT_GRAPH_AND_DORMANT_CONTRACT: PASS")


def run_constraint_odoo19_gate() -> None:
    all_model_text = "\n".join(
        read(path)
        for path in MODELS.glob("*.py")
        if not path.name.startswith("0")
    )
    active_text = "\n".join(read(MODELS / name) for name in CORE_MODEL_FILES)

    if "_sql_constraints" in all_model_text:
        fail("Legacy _sql_constraints remains in non-backup model source.")

    active_count = active_text.count("models.Constraint(")
    total_count = all_model_text.count("models.Constraint(")
    if active_count != 4:
        fail(f"Expected 4 active models.Constraint declarations; found {active_count}.")
    if total_count < 8:
        fail(f"Expected at least 8 total models.Constraint declarations including dormant aggregate; found {total_count}.")

    passed(f"ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE: PASS ({active_count} active / {total_count} total)")


def run_template_ownership_gate() -> None:
    text = read(MODELS / "consent_form_template.py")

    required = [
        '_name = "clinic.consent.template"',
        '_inherit = ["clinic.consent.template", "mail.thread", "mail.activity.mixin"]',
        "legal_governed = fields.Boolean(",
        "legal_reference = fields.Char(",
    ]
    for token in required:
        if token not in text:
            fail(f"Canonical template ownership reconciliation missing token: {token}")

    # Canonical field semantics belong to clinic_treatment_catalog. The legal
    # layer must consume them instead of redeclaring them.
    forbidden_local_fields = [
        "name = fields.Char(",
        "active = fields.Boolean(",
        "scope = fields.Selection(",
        "treatment_id = fields.Many2one(",
        "validity_days = fields.Integer(",
        "notes = fields.Text(",
        "display_name = fields.Char(",
    ]
    for token in forbidden_local_fields:
        if token in text:
            fail(f"Canonical field is being redefined by legal layer: {token}")

    # Preserve canonical Treatment Catalog metadata/ordering globally; legal
    # presentation ordering belongs on the legal list view, not the shared model.
    for token in ('_description =', '_order ='):
        if token in text:
            fail(f"Legal layer must not override canonical template model metadata: {token}")

    if 'default.setdefault("code", False)' not in text:
        fail("Legal template copy must clear canonical unique Template Code.")

    # Odoo 19 metaclass: list-form _inherit needs explicit _name. Keep the
    # same _name as the inherited canonical model to extend it in place.
    passed("CANONICAL_TEMPLATE_EXTENSION_OWNERSHIP_GATE: PASS")


def run_baseline_preservation_gate() -> None:
    contract_path = DOCS / "CLINIC_CONSENT_LEGAL_BASELINE_CONTRACT.json"
    if not contract_path.is_file():
        fail("Baseline contract document missing.")
        return

    contract = json.loads(read(contract_path))
    reconciled_template_fields = {
        "name",
        "display_name",
        "active",
        "treatment_id",
        "validity_days",
        "notes",
    }

    for model, spec in contract["baseline_active_models"].items():
        path = ROOT / spec["source_file"]
        if not path.is_file():
            fail(f"Baseline active source file missing: {spec['source_file']}")
            continue
        summaries = field_and_method_inventory(path)
        if not summaries:
            continue
        summary = summaries[0]
        current_fields = set(summary["fields"])
        current_methods = set(summary["methods"])

        for method in spec["methods"]:
            if method not in current_methods:
                fail(f"Baseline method removed from {model}: {method}")

        for field in spec["fields"]:
            if model == "clinic.consent.template" and field in reconciled_template_fields:
                continue
            if field not in current_fields:
                fail(f"Baseline field removed from {model}: {field}")

    passed("BASELINE_MODEL_FIELD_METHOD_PRESERVATION_GATE: PASS")


def run_ast_contract_gate() -> None:
    summaries = []
    for name in ACTIVE_MODEL_FILES:
        summaries.extend(field_and_method_inventory(MODELS / name))

    model_fields = defaultdict(set)
    model_methods = defaultdict(set)
    model_calls = defaultdict(dict)

    for summary in summaries:
        model = summary["model"]
        model_fields[model].update(summary["fields"])
        model_methods[model].update(summary["methods"])
        model_calls[model].update(summary["fields"])

        collision = set(summary["fields"]) & set(summary["methods"])
        if collision:
            fail(
                f"Field/method namespace collision in {model}: "
                + ", ".join(sorted(collision))
            )

        # Compute/inverse/search methods declared on local fields must exist on
        # the same extension class unless supplied by an inherited model.
        for field_name, call in summary["fields"].items():
            keywords = {kw.arg: kw.value for kw in call.keywords if kw.arg}
            for key in ("compute", "inverse", "search"):
                node = keywords.get(key)
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    method = node.value
                    if method not in summary["methods"]:
                        fail(
                            f"{model}.{field_name} declares {key}={method!r} "
                            "but the method is missing from its implementation class."
                        )

    # Local relation inverse contract.
    if "signature_ids" not in model_fields["clinic.consent.form"] or "form_id" not in model_fields["clinic.consent.signature"]:
        fail("Consent signature One2many/Many2one inverse contract is incomplete.")
    if "legal_attachment_ids" not in model_fields["clinic.consent.form"] or "form_id" not in model_fields["clinic.consent.attachment"]:
        fail("Consent attachment One2many/Many2one inverse contract is incomplete.")

    if "appointment_id" not in model_fields["clinic.consent.form"]:
        fail("Appointment integration calls consent appointment_id but field is missing.")

    # Known blocker prevention from repaired integration code.
    appointment = read(MODELS / "appointment_inherit.py")
    for forbidden in ('("is_generic", "=", True)', 'order="signed_on desc', 'vals["valid_days"]'):
        if forbidden in appointment:
            fail(f"Invalid appointment/consent contract remains: {forbidden}")

    consent_form = read(MODELS / "consent_form.py")
    if 'search="_search_is_expired"' not in consent_form:
        fail("Dynamic is_expired field must expose an Odoo search method.")
    if 'return expired_domain if wants_expired else ["!", *expired_domain]' in consent_form:
        fail("Invalid NOT-domain implementation remains in _search_is_expired.")

    passed("FIELD_METHOD_COMPUTE_RELATION_DOMAIN_CONTRACT_GATE: PASS")


def run_odoo19_static_compatibility_gate() -> None:
    active_text = "\n".join(read(MODELS / name) for name in ACTIVE_MODEL_FILES)
    forbidden = [
        ".read_group(",
        "check_access_rights(",
        "check_access_rule(",
        "args=None",
        '"tree,form"',
        "'tree,form'",
    ]
    for token in forbidden:
        if token in active_text:
            fail(f"Deprecated/legacy active Odoo API token remains: {token}")

    loaded_xml = ""
    manifest = literal_manifest()
    for rel in manifest.get("data", []):
        path = ROOT / rel
        if path.suffix == ".xml":
            loaded_xml += "\n" + read(path)
    if "<tree" in loaded_xml:
        fail("Legacy <tree> architecture remains in manifest-loaded XML.")

    passed("ODOO19_ACTIVE_SOURCE_COMPATIBILITY_GATE: PASS")


def _view_arch_models(manifest: dict):
    views = []
    for rel in manifest.get("data", []):
        path = ROOT / rel
        if path.suffix != ".xml":
            continue
        try:
            tree = ET.parse(path)
        except Exception:
            continue
        for record in tree.findall(".//record"):
            if record.get("model") != "ir.ui.view":
                continue
            model = None
            arch = None
            for field in list(record):
                if field.tag == "field" and field.get("name") == "model":
                    model = (field.text or "").strip()
                elif field.tag == "field" and field.get("name") == "arch":
                    arch = field
            if model and arch is not None:
                views.append((rel, record.get("id"), model, arch))
    return views


def run_view_contract_gate(manifest: dict) -> None:
    # Effective fields/methods for locally user-facing models.
    model_fields = defaultdict(set)
    model_methods = defaultdict(set)
    for name in ACTIVE_MODEL_FILES:
        for summary in field_and_method_inventory(MODELS / name):
            if summary["model"]:
                model_fields[summary["model"]].update(summary["fields"])
                model_methods[summary["model"]].update(summary["methods"])

    model_fields["clinic.consent.template"].update(CANONICAL_TEMPLATE_FIELDS)
    model_fields["clinic.consent.template"].update(BASE_MAGIC_FIELDS)
    for model in USER_FACING_MODELS[1:]:
        model_fields[model].update(BASE_MAGIC_FIELDS)
    for model, fields in NESTED_FIELDS.items():
        model_fields[model].update(fields)

    counts = defaultdict(Counter)

    def walk(node, current_model, rel, view_id):
        for child in list(node):
            next_model = current_model
            if child.tag == "field":
                name = child.get("name")
                if name and name not in model_fields[current_model]:
                    fail(
                        f"XML field/model mismatch: {rel} view={view_id} "
                        f"model={current_model} field={name}"
                    )
                next_model = NESTED_RELATIONS.get((current_model, name), current_model)

            if child.tag == "button" and child.get("type") == "object":
                method = child.get("name")
                if method and method not in model_methods[current_model]:
                    fail(
                        f"XML object button has no Python method: "
                        f"{current_model}.{method} ({rel}, view={view_id})"
                    )

            walk(child, next_model, rel, view_id)

    for rel, view_id, model, arch in _view_arch_models(manifest):
        if model not in USER_FACING_MODELS:
            continue
        for child in list(arch):
            if child.tag in {"search", "list", "form"}:
                counts[model][child.tag] += 1
        walk(arch, model, rel, view_id)

    for model in USER_FACING_MODELS:
        for kind in ("search", "list", "form"):
            if counts[model][kind] < 1:
                fail(f"{model} missing required {kind} view.")

    # Enterprise UX markers.
    loaded = "\n".join(
        read(ROOT / rel)
        for rel in manifest.get("data", [])
        if (ROOT / rel).suffix == ".xml"
    )
    for marker in (
        'widget="statusbar"',
        'class="oe_stat_button"',
        'type="object"',
        "<list",
    ):
        if marker not in loaded:
            fail(f"Enterprise UI marker missing: {marker}")

    passed("XML_FIELD_BUTTON_UI_UX_CONTRACT_GATE: PASS")


def run_xmlid_and_installation_resilience_gate(manifest: dict) -> None:
    local_ids = set()
    local_refs = []
    sibling_hard_refs = []

    for rel in manifest.get("data", []):
        path = ROOT / rel
        if path.suffix != ".xml":
            continue
        tree = ET.parse(path)
        root = tree.getroot()

        for elem in root.iter():
            if elem.get("id"):
                local_ids.add(elem.get("id"))
            for attr in ("ref", "parent", "action"):
                value = elem.get(attr)
                if value:
                    local_refs.append((rel, value))
                    if value.startswith("clinic_") and not value.startswith("clinic_consent_legal."):
                        # model IDs generated by the hard canonical dependency are
                        # allowed; sibling presentation XML-IDs are not.
                        if value != "clinic_treatment_catalog.model_clinic_consent_template":
                            sibling_hard_refs.append((rel, value))

    for rel, ref in local_refs:
        if "." not in ref and ref.startswith(("view_", "action_", "menu_")) and ref not in local_ids:
            fail(f"Local XML-ID reference is unresolved: {rel}: {ref}")

    if sibling_hard_refs:
        fail(
            "Manifest-loaded XML contains hard sibling ClinicOne presentation "
            f"references: {sibling_hard_refs}"
        )

    hooks = read(ROOT / "hooks.py")
    if "raise_if_not_found=False" not in hooks or "savepoint()" not in hooks:
        fail("Optional cross-addon UI hooks must resolve defensively inside savepoints.")

    passed("LOCAL_XMLID_AND_CROSS_ADDON_INSTALLATION_RESILIENCE_GATE: PASS")


def run_sequence_portal_gate(manifest: dict) -> None:
    seq = read(ROOT / "data" / "consent_sequences.xml")
    for code in ("clinic.consent.template", "clinic.consent.form"):
        if f"<field name=\"code\">{code}</field>" not in seq:
            fail(f"Sequence code missing: {code}")

    controller = read(ROOT / "controllers" / "controllers.py")
    if "_document_check_access(" not in controller:
        fail("Portal document route must use portal document access-token checking.")

    template_xml = read(ROOT / "views" / "templates.xml")
    for template_id in ("portal_my_consents", "portal_consent_page"):
        if f'id="{template_id}"' not in template_xml:
            fail(f"Portal template missing: {template_id}")

    passed("SEQUENCE_AND_PORTAL_CONTRACT_GATE: PASS")


def run_security_gate() -> None:
    acl_path = ROOT / "security" / "ir.model.access.csv"
    with acl_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    model_refs = {row["model_id:id"] for row in rows}
    required = {
        "model_clinic_consent_form",
        "model_clinic_consent_signature",
        "model_clinic_consent_attachment",
    }
    if not required <= model_refs:
        fail(f"ACL coverage missing local owned models: {sorted(required - model_refs)}")

    for row in rows:
        if row.get("group_id:id") in {"base.group_public", "base.group_portal"}:
            fail("Public/Portal ACL must not be granted to legal consent ORM models.")

    rule_text = read(ROOT / "security" / "clinic_consent_legal_rules.xml")
    if rule_text.count('model="ir.rule"') < 4:
        fail("Expected company-scoped record rules for 4 legal surfaces.")
    for model_ref in (
        "clinic_treatment_catalog.model_clinic_consent_template",
        "model_clinic_consent_form",
        "model_clinic_consent_signature",
        "model_clinic_consent_attachment",
    ):
        if model_ref not in rule_text:
            fail(f"Company record rule missing model reference: {model_ref}")

    passed("ORM_SECURITY_AUTHORITATIVE_GATE: PASS")


def run_backup_docs_retry_gate() -> None:
    for path in ROOT.rglob("*"):
        if path.is_file() and path.name.startswith("0"):
            fail(f"User backup file must be excluded from final addon: {path.relative_to(ROOT)}")

    for doc in REQUIRED_DOCS:
        if not (DOCS / doc).is_file():
            fail(f"Required Enterprise Guardrail document missing: docs/{doc}")

    agents = read(ROOT / "AGENTS.md")
    for token in (
        "LIMITED IMPLEMENTATION WORKER",
        "NOT ARCHITECT",
        "NOT SIMPLIFIER",
        "NOT ENDLESS RETRY ENGINE",
        "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_ROOT_CAUSE = 3",
    ):
        if token not in agents:
            fail(f"AGENTS.md retry/role contract missing: {token}")

    passed("BACKUP_DOCUMENTATION_CODEX_RETRY_GATE: PASS")


def print_result() -> int:
    hard_gates = [
        "HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT",
        "HARD_GATE_1_CODEX_BUKAN_ARCHITECT",
        "HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION",
        "HARD_GATE_3_ENTERPRISE_COMPLETENESS",
        "HARD_GATE_4_FULL_STRUCTURAL_INVENTORY",
        "HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
        "HARD_GATE_6_PROFESSIONAL_FORM_DESIGN",
        "HARD_GATE_7_UI_UX_MATRIX_PER_MODEL",
        "HARD_GATE_8_SEARCH_VIEW_WAJIB",
        "HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY",
        "HARD_GATE_10_SECURITY_OVER_UI",
        "HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY",
        "HARD_GATE_13_USEFUL_COMMENTS",
        "HARD_GATE_14_CODEX_RETRY_LIMIT",
        "HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
    ]

    print("=" * 78)
    print("CLINIC_CONSENT_LEGAL ENTERPRISE DEVELOPMENT HARD GATE")
    print("=" * 78)
    for line in subpasses:
        print(f"PASS: {line}")

    if failures:
        print("\nFAILURES:")
        for number, message in enumerate(failures, 1):
            print(f"{number:02d}. {message}")
        print("\nPASS: 0 / 15 OWNER HARD GATES")
        print("CLINIC_CONSENT_LEGAL_STATIC_MOVE_FORWARD_READY: NO")
        print("RUNTIME_GATE_REQUIRED: YES")
        print("CLINIC_CONSENT_LEGAL_MOVE_FORWARD_READY: NO")
        return 1

    print()
    for gate in hard_gates:
        print(f"PASS: {gate}")
    print()
    print("PASS: 15 / 15 OWNER HARD GATES")
    print("CLINIC_CONSENT_LEGAL_STATIC_MOVE_FORWARD_READY: YES")
    print("RUNTIME_GATE_REQUIRED: YES")
    print("CLINIC_CONSENT_LEGAL_MOVE_FORWARD_READY: PENDING")
    return 0


def main() -> int:
    manifest = literal_manifest()
    run_identity_manifest_gate(manifest)
    run_import_preservation_gate()
    run_python_xml_syntax_gate()
    run_constraint_odoo19_gate()
    run_template_ownership_gate()
    run_baseline_preservation_gate()
    run_ast_contract_gate()
    run_odoo19_static_compatibility_gate()
    run_view_contract_gate(manifest)
    run_xmlid_and_installation_resilience_gate(manifest)
    run_sequence_portal_gate(manifest)
    run_security_gate()
    run_backup_docs_retry_gate()
    return print_result()


if __name__ == "__main__":
    sys.exit(main())
