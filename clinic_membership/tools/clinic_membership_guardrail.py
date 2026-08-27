

#!/usr/bin/env python3
from pathlib import Path
import ast, csv, re, sys
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
errors=[]
py=[p for p in ROOT.rglob('*.py') if '__pycache__' not in p.parts and not p.name.startswith('0')]
xml=[p for p in ROOT.rglob('*.xml') if not p.name.startswith('0')]
for p in py:
    try: ast.parse(p.read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'Python parse {p}: {e}')
for p in xml:
    try: etree.parse(str(p))
    except Exception as e: errors.append(f'XML parse {p}: {e}')


# Odoo 19 search-view Relax NG contract.
# Official common.rng requires every <filter> to have @name.
# Search <group> uses the generic group definition; legacy expand/string attrs are invalid.
for p in xml:
    try:
        doc = etree.parse(str(p))
    except Exception:
        continue
    for search in doc.xpath("//search"):
        filter_names = []
        for node in search.xpath(".//filter"):
            name = node.get("name")
            if not name:
                errors.append(f"Odoo 19 search view: filter without name in {p}")
            else:
                filter_names.append(name)
        duplicate_names = sorted({
            name for name in filter_names if filter_names.count(name) > 1
        })
        if duplicate_names:
            errors.append(
                f"Odoo 19 search view: duplicate filter names in {p}: "
                + ", ".join(duplicate_names)
            )
        for group_node in search.xpath(".//group"):
            legacy_attrs = sorted(
                attr for attr in ("expand", "string") if attr in group_node.attrib
            )
            if legacy_attrs:
                errors.append(
                    f"Odoo 19 search view: legacy group attrs in {p}: "
                    + ", ".join(legacy_attrs)
                )


# Static owner-model field contract for search fields and group-by targets.
owned_fields = {}
for p in py:
    try:
        tree = ast.parse(p.read_text(encoding='utf-8'))
    except Exception:
        continue
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        model_name = None
        fields_found = set()
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == '_name':
                        try:
                            value = ast.literal_eval(stmt.value)
                        except Exception:
                            value = None
                        if isinstance(value, str):
                            model_name = value
                if isinstance(stmt.value, ast.Call):
                    call_name = ast.unparse(stmt.value.func)
                    if call_name.startswith('fields.'):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                fields_found.add(target.id)
        if model_name:
            owned_fields.setdefault(model_name, set()).update(fields_found)

for p in xml:
    try:
        doc = etree.parse(str(p))
    except Exception:
        continue
    for record in doc.xpath("//record[@model='ir.ui.view']"):
        model_nodes = record.xpath("./field[@name='model']")
        arch_nodes = record.xpath("./field[@name='arch']")
        if not model_nodes or not arch_nodes:
            continue
        model_name = (model_nodes[0].text or '').strip()
        if model_name not in owned_fields:
            continue
        for search in arch_nodes[0].xpath(".//search"):
            for field_node in search.xpath(".//field[@name]"):
                field_name = field_node.get('name')
                if field_name not in owned_fields[model_name]:
                    errors.append(
                        f"Search field missing on {model_name}: {field_name} in {p}"
                    )
            for filter_node in search.xpath(".//filter[@context]"):
                context = filter_node.get('context') or ''
                match = re.search(
                    r"['\"]group_by['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                    context,
                )
                if not match:
                    continue
                field_name = match.group(1).split(':', 1)[0]
                if field_name not in owned_fields[model_name]:
                    errors.append(
                        f"Group-by field missing on {model_name}: {field_name} in {p}"
                    )

# Odoo 19 security hierarchy contract:
#   ir.module.category -> res.groups.privilege -> res.groups.
# Odoo 19 removed category_id from res.groups; groups must use privilege_id.
security_xml_path = ROOT / 'security' / 'clinic_membership_security.xml'
try:
    security_doc = etree.parse(str(security_xml_path))
    group_records = security_doc.xpath("//record[@model='res.groups']")
    privilege_records = security_doc.xpath("//record[@model='res.groups.privilege']")
    if not privilege_records:
        errors.append('Odoo 19 security: missing res.groups.privilege record')
    for record in group_records:
        field_names = {
            field.get('name')
            for field in record.xpath("./field")
            if field.get('name')
        }
        record_id = record.get('id') or '<unknown>'
        if 'category_id' in field_names:
            errors.append(
                f"Odoo 19 security: res.groups record {record_id} uses removed category_id"
            )
        if 'privilege_id' not in field_names:
            errors.append(
                f"Odoo 19 security: res.groups record {record_id} missing privilege_id"
            )
except Exception as e:
    errors.append(f'Odoo 19 security hierarchy parse failed: {e}')

# Odoo 19 accounting company contract:
# account.account uses company_ids (Many2many) and _check_company_domain, not
# the legacy company_id field. Reject known legacy field/search patterns.
plan_py = (ROOT / 'models' / 'membership_plan.py').read_text(encoding='utf-8', errors='ignore')
contract_py = (ROOT / 'models' / 'membership_contract.py').read_text(encoding='utf-8', errors='ignore')
if re.search(
    r'income_account_id\s*=\s*fields\.Many2one\([\s\S]{0,500}?'
    r'domain\s*=\s*["\'][^"\']*company_id',
    plan_py,
):
    errors.append(
        'Odoo 19 accounting: income_account_id domain still uses removed '
        'account.account.company_id'
    )
if not re.search(
    r'income_account_id\s*=\s*fields\.Many2one\([\s\S]{0,500}?check_company\s*=\s*True',
    plan_py,
):
    errors.append(
        'Odoo 19 accounting: income_account_id must use check_company=True'
    )
if re.search(
    r'env\["account\.account"\]\.search\([\s\S]{0,350}?\("company_id"',
    contract_py,
):
    errors.append(
        'Odoo 19 accounting: backend account.account search still uses '
        'removed company_id field'
    )
if '_check_company_domain(self.company_id)' not in contract_py:
    errors.append(
        'Odoo 19 accounting: fallback income account search must use '
        'account.account._check_company_domain(company)'
    )

text='\n'.join(p.read_text(encoding='utf-8',errors='ignore') for p in py)
if re.search(r'^\s*_sql_constraints\s*=', text, re.M): errors.append('Legacy _sql_constraints is executable')
constraint_count=text.count('models.Constraint(')
if 'clinic_billing' in (ROOT/'__manifest__.py').read_text() or 'clinic_ar' in (ROOT/'__manifest__.py').read_text() or 'clinic_wallet' in (ROOT/'__manifest__.py').read_text(): errors.append('Forbidden downstream dependency found')
for p in ROOT.rglob('*'):
    if p.is_file() and (p.name.startswith('0') or '__pycache__' in p.parts or p.suffix=='.pyc'): errors.append(f'Backup/cache artifact: {p}')
if any('<tree' in p.read_text(encoding='utf-8',errors='ignore') for p in xml): errors.append('Legacy <tree> found')
if any(re.search(r'view_mode[^\n]*tree', p.read_text(encoding='utf-8',errors='ignore')) for p in xml): errors.append('Legacy tree view_mode found')
if any(' attrs=' in p.read_text(encoding='utf-8',errors='ignore') or ' states=' in p.read_text(encoding='utf-8',errors='ignore') for p in xml): errors.append('Legacy attrs/states found')
# Unsafe arbitrary Python multiple bases on Odoo classes.
for p in py:
    tree=ast.parse(p.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.ClassDef) and len(node.bases)>1:
            names=[ast.unparse(x) for x in node.bases]
            if any(n.endswith(('models.Model','models.TransientModel','models.AbstractModel')) or n in ('models.Model','models.TransientModel','models.AbstractModel') for n in names): errors.append(f'Unsafe multiple bases {p}:{node.name}:{names}')
models=['membership.plan','membership.plan.benefit','membership.contract','membership.contract.benefit','membership.usage','membership.voucher','membership.point.tx','membership.hold','membership.integration.event']
allxml='\n'.join(p.read_text(encoding='utf-8',errors='ignore') for p in xml)
for m in models:
    for typ in ('search','list','form'):
        if f'<field name="model">{m}</field>' not in allxml or f'{m}.{typ}' not in allxml: errors.append(f'UI matrix missing {m} {typ}')
# ACL coverage
with (ROOT/'security/ir.model.access.csv').open(encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(line for line in f if line.strip()))
acl_models={r.get('model_id:id','') for r in rows}
for m in models:
    key='model_'+m.replace('.','_')
    if key not in acl_models: errors.append(f'ACL missing {m}')
# State/searchability contracts known to be used by search/domain.
for pattern,label in [(r'is_expired\s*=\s*fields.Boolean\([\s\S]{0,240}?search=', 'contract/voucher is_expired search'),(r'is_depleted\s*=\s*fields.Boolean\([\s\S]{0,240}?store=True','entitlement is_depleted store')]:
    if not re.search(pattern,text): errors.append(f'Missing searchable contract: {label}')

# Context-aware object-button ownership for inline One2many/Many2many views.
# `type="object"` is executed on the current view/row model. A global method
# name match is insufficient because an inline row belongs to the relational
# comodel, not the parent form model.
model_methods = {}
relational_fields = {}
for p in py:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        model_name = None
        methods_found = {
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "_name"
                ):
                    try:
                        value = ast.literal_eval(stmt.value)
                    except Exception:
                        value = None
                    if isinstance(value, str):
                        model_name = value
        if not model_name:
            continue
        model_methods.setdefault(model_name, set()).update(methods_found)
        for stmt in node.body:
            if (
                not isinstance(stmt, ast.Assign)
                or not isinstance(stmt.value, ast.Call)
                or len(stmt.targets) != 1
                or not isinstance(stmt.targets[0], ast.Name)
            ):
                continue
            func = stmt.value.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "fields"
                and func.attr in ("One2many", "Many2many")
                and stmt.value.args
            ):
                continue
            first_arg = stmt.value.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                relational_fields[(model_name, stmt.targets[0].id)] = first_arg.value

for p in xml:
    try:
        doc = etree.parse(str(p))
    except Exception:
        continue
    for record in doc.xpath("//record[@model='ir.ui.view']"):
        model_nodes = record.xpath("./field[@name='model']")
        arch_nodes = record.xpath("./field[@name='arch']")
        if not model_nodes or not arch_nodes:
            continue
        root_model = (model_nodes[0].text or "").strip()

        def validate_node(node, current_model):
            if node.tag == "field" and node.get("name"):
                comodel = relational_fields.get((current_model, node.get("name")))
                if comodel:
                    for child in node:
                        validate_node(child, comodel)
                    return

            if node.tag == "button" and node.get("type") == "object":
                method_name = node.get("name") or ""
                if (
                    current_model in model_methods
                    and method_name not in model_methods[current_model]
                ):
                    errors.append(
                        "Object button ownership mismatch: "
                        f"{p}:{node.sourceline} button {method_name!r} "
                        f"is rendered on {current_model}, but no such method "
                        "exists on that model"
                    )

            for child in node:
                validate_node(child, current_model)

        for child in arch_nodes[0]:
            validate_node(child, root_model)


# Odoo 19 menu/action external-ID ownership contract.
# Membership-owned menus must point to actions defined by clinic_membership itself.
# This blocks fragile/historical global Settings action references such as
# `base.action_res_config_settings`, which is not an Odoo 19 core XML ID.
if "base.action_res_config_settings" in allxml:
    errors.append(
        "Odoo 19 settings action: forbidden historical XML ID "
        "base.action_res_config_settings"
    )

local_xml_ids = set()
for p in xml:
    try:
        doc = etree.parse(str(p))
    except Exception:
        continue
    for node in doc.xpath("//*[@id]"):
        node_id = node.get("id")
        if node_id:
            local_xml_ids.add(node_id)

settings_view_path = ROOT / "views" / "res_config_settings_views.xml"
menu_view_path = ROOT / "views" / "menu_views.xml"
try:
    settings_doc = etree.parse(str(settings_view_path))
    menu_doc = etree.parse(str(menu_view_path))
    action_nodes = settings_doc.xpath(
        "//record[@id='action_membership_settings'][@model='ir.actions.act_window']"
    )
    if len(action_nodes) != 1:
        errors.append(
            "Membership settings: expected exactly one local "
            "action_membership_settings ir.actions.act_window"
        )
    else:
        action_node = action_nodes[0]
        values = {
            field.get("name"): (field.text or "").strip()
            for field in action_node.xpath("./field")
        }
        if values.get("res_model") != "res.config.settings":
            errors.append(
                "Membership settings: local action must target res.config.settings"
            )
        if values.get("view_mode") != "form":
            errors.append(
                "Membership settings: local action must use form view_mode"
            )
        if "clinic_membership" not in values.get("context", ""):
            errors.append(
                "Membership settings: local action context must target clinic_membership"
            )

    settings_menu = menu_doc.xpath("//menuitem[@id='menu_membership_settings']")
    if len(settings_menu) != 1:
        errors.append("Membership settings: menu_membership_settings missing/duplicated")
    else:
        menu_action = settings_menu[0].get("action") or ""
        if menu_action != "action_membership_settings":
            errors.append(
                "Membership settings: Settings menu must use local "
                "action_membership_settings"
            )

    for menu in menu_doc.xpath("//menuitem[@action]"):
        action_ref = menu.get("action") or ""
        if "." in action_ref:
            errors.append(
                f"Membership menu external action dependency forbidden: "
                f"{menu.get('id')} -> {action_ref}"
            )
        elif action_ref not in local_xml_ids:
            errors.append(
                f"Membership menu action not defined locally: "
                f"{menu.get('id')} -> {action_ref}"
            )
except Exception as e:
    errors.append(f"Membership settings/menu action audit failed: {e}")

# object buttons -> method defs
methods=set(re.findall(r'def\s+(action_[A-Za-z0-9_]+)\s*\(',text))
buttons=set(re.findall(r'<button[^>]+name="(action_[A-Za-z0-9_]+)"[^>]+type="object"',allxml))
missing=sorted(buttons-methods)
if missing: errors.append('Missing object methods: '+', '.join(missing))
tests=sum(1 for p in (ROOT/'tests').glob('test_*.py') for _ in re.finditer(r'\n\s*def\s+test_',p.read_text()))
print('clinic_membership Enterprise Development Guardrail')
print(f'[INFO] python_files={len(py)}')
print(f'[INFO] xml_files={len(xml)}')
print(f'[INFO] models.Constraint={constraint_count}')
print(f'[INFO] persistent_models={len(models)}/9')
print(f'[INFO] object_buttons={len(buttons)}')
print(f'[INFO] test_methods={tests}')
if errors:
    print('RESULT: FAIL')
    for e in errors: print('[FAIL]',e)
    sys.exit(1)
print('RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)')

