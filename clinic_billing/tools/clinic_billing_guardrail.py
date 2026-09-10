#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ClinicOne clinic_billing static Enterprise Development Guardrail.

This checker intentionally does not claim Odoo runtime success.
Run from the addon root:
    python tools/clinic_billing_guardrail.py
"""
from __future__ import annotations

import ast
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PERSISTENT_MODELS = [
    "clinic.billing.invoice",
    "clinic.billing.line",
    "clinic.billing.payment",
    "clinic.billing.payment.line",
    "clinic.billing.discount.rule",
    "clinic.billing.discount.redemption",
    "clinic.billing.voucher.program",
    "clinic.billing.voucher",
    "clinic.billing.voucher.redemption",
    "clinic.insurance.claim",
    "clinic.insurance.claim.line",
    "clinic.billing.commission.rule",
    "clinic.billing.commission.line",
    "clinic.billing.commission.settlement",
    "clinic.billing.gateway.tx",
    "clinic.billing.gateway.event",
    "clinic.billing.membership.usage",
    "clinic.treatment.billing.link",
    "clinic.billing.integration.event",
]

REQUIRED_OWNER_DEPENDENCIES = {
    "clinic_patient",
    "clinic_doctor",
    "clinic_booking",
    "clinic_encounter",
    "clinic_care_plan",
    "clinic_package",
    "clinic_emar",
    "clinic_inventory",
    "clinic_room_device",
    "clinic_treatment_catalog",
    "account",
    "product",
    "stock",
    "uom",
    "hr",
    "mail",
}

FORBIDDEN_ACTIVE_STRINGS = {
    "clinic.booking.appointment": "historical booking model",
    "clinic.treatment.session": "historical treatment-session model",
    "clinic.membership.wallet": "historical wallet model",
    "move_ids_without_package": "pre-Odoo-19 stock picking API",
    "user_type_id": "pre-Odoo-19 account type access pattern",
}


def active_files(pattern="*"):
    return [
        p for p in ROOT.rglob(pattern)
        if p.is_file()
        and not p.name.startswith("0")
        and "__pycache__" not in p.parts
        and p.suffix != ".pyc"
    ]


def fail(message, failures):
    failures.append(message)
    print(f"[FAIL] {message}")


def main():
    failures = []
    py_files = active_files("*.py")
    xml_files = active_files("*.xml")

    # Python syntax without producing pycache.
    for path in py_files:
        try:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
        except Exception as exc:
            fail(f"Python syntax: {path.relative_to(ROOT)}: {exc}", failures)

    # XML syntax.
    for path in xml_files:
        try:
            ET.parse(path)
        except Exception as exc:
            fail(f"XML parse: {path.relative_to(ROOT)}: {exc}", failures)

    # Manifest.
    manifest_path = ROOT / "__manifest__.py"
    try:
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        fail(f"Manifest parse: {exc}", failures)
        manifest = {}

    for rel in manifest.get("data", []):
        if not (ROOT / rel).is_file():
            fail(f"Manifest data file missing: {rel}", failures)

    deps = set(manifest.get("depends", []))
    missing_deps = sorted(REQUIRED_OWNER_DEPENDENCIES - deps)
    if missing_deps:
        fail(f"Required owner dependencies missing: {missing_deps}", failures)

    # AST inventory, methods, constraints, unsafe inheritance.
    methods = set()
    persistent_found = set()
    constraint_count = 0
    sql_constraint_assignments = []
    invalid_sql_object_names = []
    unsafe_bases = []

    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.add(node.name)
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "models.Constraint":
                constraint_count += 1
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [ast.unparse(base) for base in node.bases]
            is_odoo_model = any(
                base in ("models.Model", "models.AbstractModel", "models.TransientModel")
                for base in bases
            )
            if is_odoo_model and len(bases) > 1:
                unsafe_bases.append((path.relative_to(ROOT).as_posix(), node.name, bases))
            model_name = None
            is_abstract = "models.AbstractModel" in bases
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                ):
                    key = stmt.targets[0].id
                    if key == "_sql_constraints":
                        sql_constraint_assignments.append(
                            (path.relative_to(ROOT).as_posix(), node.name)
                        )
                    if (
                        isinstance(stmt.value, ast.Call)
                        and ast.unparse(stmt.value.func) in {"models.Constraint", "models.Index", "models.UniqueIndex"}
                        and not key.startswith("_")
                    ):
                        invalid_sql_object_names.append(
                            (path.relative_to(ROOT).as_posix(), node.name, key)
                        )
                    if key == "_name":
                        try:
                            value = ast.literal_eval(stmt.value)
                        except Exception:
                            value = None
                        if isinstance(value, str):
                            model_name = value
            if model_name and not is_abstract:
                persistent_found.add(model_name)

    if sql_constraint_assignments:
        fail(f"Executable _sql_constraints found: {sql_constraint_assignments}", failures)
    if invalid_sql_object_names:
        fail(
            "Odoo 19 SQL table objects must use private class attributes: "
            f"{invalid_sql_object_names}",
            failures,
        )
    if unsafe_bases:
        fail(f"Unsafe Python/Odoo multiple bases: {unsafe_bases}", failures)

    missing_models = sorted(set(PERSISTENT_MODELS) - persistent_found)
    if missing_models:
        fail(f"Persistent owner models missing from source: {missing_models}", failures)

    # XML object buttons must resolve to a Python method somewhere in the addon.
    object_buttons = []
    for path in xml_files:
        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue
        for button in root.iter("button"):
            if button.get("type") == "object" and button.get("name"):
                object_buttons.append(button.get("name"))
    missing_methods = sorted(set(object_buttons) - methods)
    if missing_methods:
        fail(f"Object button methods missing: {missing_methods}", failures)

    # Context-aware inline relational button ownership.
    # A type="object" button inside an inline One2many/Many2many view executes on
    # the row comodel, not on the parent form model.
    model_methods = {}
    relational_fields = {}
    for path in py_files:
        if "tests" in path.parts or "tools" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            model_name = None
            inherited_name = None
            for stmt in cls.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for target in stmt.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id in {"_name", "_inherit"}:
                        try:
                            value = ast.literal_eval(stmt.value)
                        except Exception:
                            value = None
                        if target.id == "_name" and isinstance(value, str):
                            model_name = value
                        elif target.id == "_inherit" and isinstance(value, str):
                            inherited_name = value
            owner = model_name or inherited_name
            if not owner:
                continue
            model_methods.setdefault(owner, set())
            relational_fields.setdefault(owner, {})
            for stmt in cls.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    model_methods[owner].add(stmt.name)
                elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                    func_name = ast.unparse(stmt.value.func)
                    if func_name not in {"fields.One2many", "fields.Many2many", "fields.Many2one"}:
                        continue
                    comodel = None
                    if stmt.value.args:
                        try:
                            comodel = ast.literal_eval(stmt.value.args[0])
                        except Exception:
                            comodel = None
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            relational_fields[owner][target.id] = comodel

    context_button_errors = []
    for path in xml_files:
        try:
            view_root = ET.parse(path).getroot()
        except Exception:
            continue
        for record in view_root.iter("record"):
            if record.get("model") != "ir.ui.view":
                continue
            model_name = None
            arch = None
            for field in record.findall("field"):
                if field.get("name") == "model":
                    model_name = (field.text or "").strip()
                elif field.get("name") == "arch":
                    arch = field
            if not model_name or arch is None:
                continue

            def walk_view(element, current_model):
                if element.tag == "button" and element.get("type") == "object":
                    method_name = element.get("name")
                    if (
                        current_model in model_methods
                        and method_name
                        and method_name not in model_methods[current_model]
                    ):
                        context_button_errors.append(
                            (path.relative_to(ROOT).as_posix(), current_model, method_name)
                        )
                child_model = current_model
                if element.tag == "field" and element.get("name"):
                    field_name = element.get("name")
                    if any(child.tag in {"list", "form", "kanban"} for child in list(element)):
                        child_model = (
                            relational_fields.get(current_model, {}).get(field_name)
                            or current_model
                        )
                for child in list(element):
                    walk_view(child, child_model)

            for child in list(arch):
                walk_view(child, model_name)

    if context_button_errors:
        fail(f"Context-aware object button mismatch: {context_button_errors}", failures)

    # Search/List/Form matrix.
    matrix = {model: set() for model in PERSISTENT_MODELS}
    for path in xml_files:
        try:
            doc = ET.parse(path).getroot()
        except Exception:
            continue
        for record in doc.iter("record"):
            if record.get("model") != "ir.ui.view":
                continue
            model_name = None
            arch = None
            for field in record.findall("field"):
                if field.get("name") == "model":
                    model_name = (field.text or "").strip()
                elif field.get("name") == "arch":
                    arch = field
            if model_name not in matrix or arch is None:
                continue
            body = ET.tostring(arch, encoding="unicode")
            for view_type in ("search", "list", "form"):
                if f"<{view_type}" in body:
                    matrix[model_name].add(view_type)
    ui_missing = {
        model: sorted({"search", "list", "form"} - types)
        for model, types in matrix.items()
        if types != {"search", "list", "form"}
    }
    if ui_missing:
        fail(f"UI matrix incomplete: {ui_missing}", failures)

    # ACL coverage.
    access_path = ROOT / "security" / "ir.model.access.csv"
    try:
        raw_lines = [
            line for line in access_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        rows = list(csv.DictReader(raw_lines))
        acl_model_ids = {row["model_id:id"] for row in rows}
        expected = {f"model_{model.replace('.', '_')}" for model in PERSISTENT_MODELS}
        missing_acl = sorted(expected - acl_model_ids)
        if missing_acl:
            fail(f"ACL coverage missing: {missing_acl}", failures)
    except Exception as exc:
        fail(f"ACL parse failed: {exc}", failures)
        rows = []

    # Odoo 19 view syntax / historical contract regression.
    active_text_files = []
    for p in active_files():
        if p.suffix not in {".py", ".xml", ".csv"}:
            continue
        rel_parts = p.relative_to(ROOT).parts
        if (
            rel_parts[0] in {"models", "views", "data", "security"}
            or p.name in {"__init__.py", "__manifest__.py"}
        ):
            active_text_files.append(p)
    source_text = "\n".join(
        p.read_text(encoding="utf-8-sig", errors="ignore") for p in active_text_files
    )
    legacy_patterns = {
        r"<tree(?:\s|>)": "legacy <tree> view",
        r"view_mode[^\n]*\btree\b": "legacy tree view_mode",
        r"\sattrs\s*=": "legacy attrs view modifier",
        r"\sstates\s*=": "legacy states view modifier",
    }
    for pattern, description in legacy_patterns.items():
        if re.search(pattern, source_text):
            fail(description, failures)

    # Only inspect executable Python/XML, not preservation documentation/comments.
    executable_text = "\n".join(
        p.read_text(encoding="utf-8-sig", errors="ignore")
        for p in active_text_files
        if p.suffix in {".py", ".xml"}
    )
    for token, description in FORBIDDEN_ACTIVE_STRINGS.items():
        if token in executable_text:
            fail(f"{description} still active: {token}", failures)

    # Domains must not rely on the known non-stored billing flags.
    invoice_py = (ROOT / "models" / "billing_invoice.py").read_text(encoding="utf-8")
    for field_name in ("is_overdue", "is_paid"):
        field_match = re.search(
            rf"{field_name}\\s*=\\s*fields\\.Boolean\\((.*?)\\n\\s*\\)",
            invoice_py,
            re.S,
        )
        if field_match and 'search=' not in field_match.group(1):
            fail(f"{field_name} must remain searchable", failures)


    # Odoo 19 hard compatibility contracts proven by runtime failures.
    # 1) res.groups uses privilege_id; category_id belongs to res.groups.privilege.
    for path in xml_files:
        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue
        for record in root.iter("record"):
            if record.get("model") != "res.groups":
                continue
            fields_by_name = {field.get("name") for field in record.findall("field")}
            if "category_id" in fields_by_name:
                fail(
                    f"Odoo 19 res.groups.category_id used in {path.relative_to(ROOT)} "
                    f"record {record.get('id')}",
                    failures,
                )
            if record.get("id", "").startswith("group_clinic_billing_") and "privilege_id" not in fields_by_name:
                fail(
                    f"Billing group missing privilege_id: {record.get('id')}",
                    failures,
                )

    # 2) Odoo 19 search filters require technical names; legacy search-group
    # expand/string attributes are not accepted by the Relax NG schema.
    for path in xml_files:
        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue
        for search in root.iter("search"):
            filter_names = set()
            for element in search.iter():
                if element.tag == "filter":
                    name = element.get("name")
                    if not name:
                        fail(
                            f"Search filter without name in {path.relative_to(ROOT)}",
                            failures,
                        )
                    elif name in filter_names:
                        fail(
                            f"Duplicate search filter name {name!r} in {path.relative_to(ROOT)}",
                            failures,
                        )
                    else:
                        filter_names.add(name)
                elif element.tag == "group" and (
                    element.get("expand") is not None or element.get("string") is not None
                ):
                    fail(
                        f"Legacy search-group attributes in {path.relative_to(ROOT)}",
                        failures,
                    )

    # 3) account.account is company_ids-based in Odoo 19. Executable Billing
    # code must not query/domain/read account.account.company_id.
    account_company_patterns = [
        r'Account\.search\([^\]]*["\']company_id["\']',
        r'\bacc\.company_id\b',
        r'account\.company_id\b',
        r'domain\s*=\s*["\'][^"\']*company_id[^"\']*["\'][^\\n]*account_type',
    ]
    billing_exec = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="ignore")
        for path in py_files
        if "tests" not in path.parts and "tools" not in path.parts
    )
    for pattern in account_company_patterns:
        if re.search(pattern, billing_exec, re.S):
            fail(
                f"Odoo 19 account.account.company_id assumption detected: {pattern}",
                failures,
            )
    if "_check_company_domain" not in billing_exec:
        fail("Odoo 19 account.account company-domain helper is not used", failures)

    # 4) Odoo 19 owns res.partner.credit_limit in account as a
    # company-dependent Float. Clinic Billing must consume, not redeclare, it.
    patient_hook = ROOT / "models" / "patient_hook.py"
    if patient_hook.is_file():
        try:
            tree = ast.parse(patient_hook.read_text(encoding="utf-8-sig"))
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                inherit_partner = False
                for stmt in node.body:
                    if (
                        isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id == "_inherit"
                    ):
                        try:
                            inherit_partner = ast.literal_eval(stmt.value) == "res.partner"
                        except Exception:
                            pass
                if not inherit_partner:
                    continue
                for stmt in node.body:
                    if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                        continue
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    if any(isinstance(target, ast.Name) and target.id == "credit_limit" for target in targets):
                        fail(
                            "clinic_billing must not redeclare core res.partner.credit_limit",
                            failures,
                        )
        except Exception as exc:
            fail(f"credit_limit ownership AST check failed: {exc}", failures)

    migration = ROOT / "migrations" / "19.0.3.0.2" / "pre-migrate.py"
    if not migration.is_file():
        fail("Odoo 19 credit_limit JSONB pre-migration is missing", failures)
    else:
        migration_source = migration.read_text(encoding="utf-8-sig")
        for required in ("res_partner", "credit_limit", "jsonb", "res_company"):
            if required not in migration_source:
                fail(
                    f"credit_limit JSONB migration missing contract token: {required}",
                    failures,
                )

    # Prefix-0 and cache hygiene.
    bad_packaging = [
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file()
        and (p.name.startswith("0") or "__pycache__" in p.parts or p.suffix == ".pyc")
    ]
    if bad_packaging:
        fail(f"Backup/cache artifacts present: {bad_packaging}", failures)

    test_count = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        test_count += len(re.findall(r"\bdef\s+test_", path.read_text(encoding="utf-8")))

    print(f"[INFO] python_files={len(py_files)}")
    print(f"[INFO] xml_files={len(xml_files)}")
    print(f"[INFO] persistent_models={len(persistent_found & set(PERSISTENT_MODELS))}/{len(PERSISTENT_MODELS)}")
    print(f"[INFO] models.Constraint={constraint_count}")
    print(f"[INFO] object_buttons={len(object_buttons)}")
    print(f"[INFO] ui_matrix={sum(1 for v in matrix.values() if v == {'search','list','form'})}/{len(PERSISTENT_MODELS)}")
    print(f"[INFO] acl_rows={len(rows)}")
    print(f"[INFO] test_methods={test_count}")

    if failures:
        print(f"RESULT: FAIL ({len(failures)} static hard-gate defect(s))")
        return 1
    print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)")
    return 0


if __name__ == "__main__":
    sys.exit(main())



