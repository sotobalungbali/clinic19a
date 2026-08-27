#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
PERSISTENT = {
    "clinic.ar.invoice", "clinic.ar.invoice.line", "clinic.ar.payment",
    "clinic.ar.allocation", "clinic.ar.allocation.line",
    "clinic.ar.followup.level", "clinic.ar.followup",
    "clinic.ar.statement", "clinic.ar.statement.line",
    "clinic.ar.integration.event",
}

errors: list[str] = []
infos: list[str] = []


def fail(msg: str):
    errors.append(msg)


def load_manifest():
    text = (ROOT / "__manifest__.py").read_text(encoding="utf-8")
    try:
        return ast.literal_eval(text[text.index("{"):])
    except Exception as exc:
        fail(f"manifest parse failed: {exc}")
        return {}


def python_inventory():
    model_fields: dict[str, set[str]] = {}
    model_methods: dict[str, set[str]] = {}
    relations: dict[str, dict[str, str]] = {}
    persistent: set[str] = set()
    constraint_count = 0
    sql_object_count = 0
    bad_sql_names = []
    legacy_sql = []
    bad_currency_check_company = []

    for path in sorted(ROOT.rglob("*.py")):
        if path.name.startswith("0") or "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if "_sql_constraints" in source and not path.name.endswith("guardrail.py"):
            legacy_sql.append(str(path.relative_to(ROOT)))
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            fail(f"python syntax: {path.relative_to(ROOT)}: {exc}")
            continue
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            model_name = None
            inherit = []
            for node in cls.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    key = node.targets[0].id
                    if key == "_name" and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        model_name = node.value.value
                    elif key == "_inherit":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            inherit = [node.value.value]
                        elif isinstance(node.value, (ast.List, ast.Tuple)):
                            inherit = [x.value for x in node.value.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)]
            target = model_name or (inherit[0] if len(inherit) == 1 else None)
            if model_name and not model_name.startswith("abstract."):
                persistent.add(model_name)
            if not target:
                continue
            model_fields.setdefault(target, set())
            model_methods.setdefault(target, set())
            relations.setdefault(target, {})
            for node in cls.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    model_methods[target].add(node.name)
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    attr = node.targets[0].id
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                        if isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "models" and node.value.func.attr in {"Constraint", "Index"}:
                            sql_object_count += 1
                            if node.value.func.attr == "Constraint":
                                constraint_count += 1
                            if not attr.startswith("_"):
                                bad_sql_names.append(f"{path.name}:{cls.name}.{attr}")
                        if isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "fields":
                            model_fields[target].add(attr)
                            if node.value.func.attr in {"Many2one", "One2many", "Many2many"} and node.value.args and isinstance(node.value.args[0], ast.Constant):
                                comodel = node.value.args[0].value
                                relations[target][attr] = comodel
                                if node.value.func.attr == "Many2one" and comodel == "res.currency":
                                    for keyword in node.value.keywords:
                                        if (
                                            keyword.arg == "check_company"
                                            and isinstance(keyword.value, ast.Constant)
                                            and keyword.value.value is True
                                        ):
                                            bad_currency_check_company.append(
                                                f"{path.name}:{cls.name}.{attr}"
                                            )
    if legacy_sql:
        fail("legacy _sql_constraints found: " + ", ".join(legacy_sql))
    if bad_sql_names:
        fail("SQL objects without private attribute names: " + ", ".join(bad_sql_names))
    if bad_currency_check_company:
        fail(
            "res.currency Many2one fields must not use check_company=True in Odoo 19: "
            + ", ".join(bad_currency_check_company)
        )
    return model_fields, model_methods, relations, persistent, constraint_count, sql_object_count


def xml_inventory(model_fields, model_methods, relations):
    ui = {m: set() for m in PERSISTENT}
    object_buttons = 0
    button_mismatch = []
    missing_fields = []
    unnamed_filters = []
    legacy_search_groups = []
    xml_ids = set()
    menu_actions = []
    bad_group_category = []
    privilege_records = 0
    group_privileges = 0
    hard_billing_view_inherits = []

    common = {"id", "display_name", "create_date", "write_date", "create_uid", "write_uid", "message_ids", "message_follower_ids", "activity_ids"}

    def walk(node, model):
        nonlocal object_buttons
        for child in node:
            if not isinstance(child.tag, str):
                continue
            if child.tag == "button" and child.get("type") == "object":
                object_buttons += 1
                method = child.get("name")
                if model in model_methods and method not in model_methods[model]:
                    button_mismatch.append(f"{model}.{method}")
            if child.tag == "field":
                fname = child.get("name")
                if model in PERSISTENT and fname not in model_fields.get(model, set()) and fname not in common:
                    missing_fields.append(f"{model}.{fname}")
                next_model = relations.get(model, {}).get(fname, model)
                for sub in child:
                    if isinstance(sub.tag, str) and sub.tag in {"list", "form"}:
                        walk(sub, next_model)
                continue
            walk(child, model)

    for path in sorted(ROOT.rglob("*.xml")):
        if path.name.startswith("0"):
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            fail(f"XML has UTF-8 BOM: {path.relative_to(ROOT)}")
        if not raw.startswith(b"<?xml"):
            fail(f"XML declaration is not first bytes: {path.relative_to(ROOT)}")
        try:
            doc = etree.parse(str(path))
        except Exception as exc:
            fail(f"XML parse failed {path.relative_to(ROOT)}: {exc}")
            continue
        for rec in doc.xpath("//record[@id]"):
            xml_ids.add(rec.get("id"))
            if rec.get("model") == "res.groups.privilege":
                privilege_records += 1
            if rec.get("model") == "res.groups":
                if rec.xpath("./field[@name='category_id']"):
                    bad_group_category.append(rec.get("id"))
                if rec.xpath("./field[@name='privilege_id']"):
                    group_privileges += 1
            if rec.get("model") == "ir.ui.view":
                for inherit_field in rec.xpath("./field[@name='inherit_id'][@ref]"):
                    ref = inherit_field.get("ref") or ""
                    if ref.startswith("clinic_billing."):
                        hard_billing_view_inherits.append(
                            f"{path.name}:{rec.get('id')}->{ref}"
                        )
        for menu in doc.xpath("//menuitem[@action]"):
            menu_actions.append(menu.get("action"))
        for rec in doc.xpath("//record[@model='ir.ui.view']"):
            modelf = rec.xpath("./field[@name='model']")
            archf = rec.xpath("./field[@name='arch']")
            if not modelf or not archf:
                continue
            model = (modelf[0].text or "").strip()
            arch = archf[0]
            roots = [c for c in arch if isinstance(c.tag, str)]
            if roots and model in ui:
                tag = roots[0].tag
                if tag in {"search", "list", "form"}:
                    ui[model].add(tag)
            for flt in arch.xpath(".//filter"):
                if not flt.get("name"):
                    unnamed_filters.append(f"{path.name}:{model}:{flt.get('string')}")
            for group in arch.xpath(".//search//group"):
                if group.get("expand") is not None or group.get("string") is not None:
                    legacy_search_groups.append(f"{path.name}:{model}")
            walk(arch, model)
    if bad_group_category:
        fail("res.groups.category_id is forbidden in Odoo 19: " + ", ".join(bad_group_category))
    if privilege_records < 1 or group_privileges < 2:
        fail("Odoo 19 privilege hierarchy incomplete")
    if hard_billing_view_inherits:
        fail(
            "Hard clinic_billing view inherit_id is forbidden; use the runtime-safe bridge: "
            + ", ".join(hard_billing_view_inherits)
        )
    if unnamed_filters:
        fail("Search filters without name: " + ", ".join(unnamed_filters))
    if legacy_search_groups:
        fail("Legacy search group attributes found: " + ", ".join(legacy_search_groups))
    if missing_fields:
        fail("View fields missing on owner model: " + ", ".join(sorted(set(missing_fields))))
    if button_mismatch:
        fail("type=object method ownership mismatch: " + ", ".join(sorted(set(button_mismatch))))
    for model, kinds in ui.items():
        missing = {"search", "list", "form"} - kinds
        if missing:
            fail(f"UI matrix incomplete for {model}: missing {sorted(missing)}")
    for action in menu_actions:
        if "." not in action and action not in xml_ids:
            fail(f"menu action not locally defined: {action}")
    return ui, object_buttons


def manifest_checks(manifest):
    for rel in manifest.get("data", []):
        if not (ROOT / rel).exists():
            fail(f"manifest data file missing: {rel}")
    depends = set(manifest.get("depends", []))
    for required in {"account", "clinic_billing", "clinic_membership", "clinic_booking", "clinic_treatment_session"}:
        if required not in depends:
            fail(f"required dependency missing: {required}")
    for forbidden in {"clinic_ap", "clinic_wallet"}:
        if forbidden in depends:
            fail(f"downstream dependency forbidden: {forbidden}")


def source_contract_checks():
    sources = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("models/*.py"))
    for old in ("clinic.booking", '"clinic.membership"', "'clinic.membership'"):
        if old in sources:
            fail(f"historical model contract still present: {old}")
    if "account.account.company_id" in sources:
        fail("forbidden account.account.company_id contract found")
    if "income_account_id" not in sources or "company_ids" not in sources or "check_company=True" not in sources:
        fail("Odoo 19 account company contract is incomplete")
    if "force_payment_move" not in sources or 'self.env["account.payment"]' not in sources:
        fail("standard account.payment receipt contract missing")
    if "create_from_billing" not in sources or 'self.env["account.move"]' not in sources:
        fail("billing/manual accounting invoice contract missing")
    if "MAX_ATTEMPTS = 3" not in sources:
        fail("bounded integration retry contract missing")
    if "_ensure_optional_billing_views" not in sources:
        fail("runtime-safe Billing view bridge contract missing")
    if "_upsert_optional_inherited_view" not in sources:
        fail("idempotent optional view upsert helper missing")


def acl_checks():
    path = ROOT / "security/ir.model.access.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    covered = {row["model_id:id"].removeprefix("model_").replace("_", ".") for row in rows}
    # model-id normalization isn't bijective; verify by expected XML ids instead.
    expected_ids = {"model_" + m.replace(".", "_") for m in PERSISTENT}
    actual_ids = {row["model_id:id"] for row in rows}
    missing = expected_ids - actual_ids
    if missing:
        fail("ACL missing persistent models: " + ", ".join(sorted(missing)))
    return len(rows)


def main():
    manifest = load_manifest()
    manifest_checks(manifest)
    model_fields, model_methods, relations, persistent, constraint_count, sql_objects = python_inventory()
    owner_persistent = persistent & PERSISTENT
    if owner_persistent != PERSISTENT:
        fail(f"persistent owner model inventory mismatch: {sorted(owner_persistent)}")
    ui, buttons = xml_inventory(model_fields, model_methods, relations)
    source_contract_checks()
    acl_rows = acl_checks()
    test_methods = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        test_methods += sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.walk(tree))
    prefix0 = [p for p in ROOT.rglob("*") if p.is_file() and p.name.startswith("0")]
    caches = [p for p in ROOT.rglob("*") if "__pycache__" in p.parts or p.suffix == ".pyc"]
    if prefix0:
        fail("numeric-prefix backup files packaged")
    if caches:
        fail("cache files present in release tree")

    print("clinic_ar Enterprise Development Guardrail")
    print(f"[INFO] python_files={len([p for p in ROOT.rglob('*.py') if '__pycache__' not in p.parts])}")
    print(f"[INFO] xml_files={len(list(ROOT.rglob('*.xml')))}")
    print(f"[INFO] persistent_models={len(PERSISTENT)}/{len(PERSISTENT)}")
    print(f"[INFO] models.Constraint={constraint_count}")
    print(f"[INFO] sql_objects={sql_objects}")
    print(f"[INFO] object_buttons={buttons}")
    print(f"[INFO] ui_matrix={sum({'search','list','form'} <= v for v in ui.values())}/{len(PERSISTENT)}")
    print(f"[INFO] acl_rows={acl_rows}")
    print(f"[INFO] test_methods={test_methods}")
    if errors:
        for err in errors:
            print(f"[FAIL] {err}")
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

