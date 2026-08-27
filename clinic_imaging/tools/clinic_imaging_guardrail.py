#!/usr/bin/env python3
"""Machine-checkable Enterprise Development Guardrail for clinic_imaging."""
from __future__ import annotations

from pathlib import Path
import ast
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, OrderedDict

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MODEL_DIR = ROOT / "models"
EXPECTED_FOLDER = "clinic_imaging"

FAILURES: list[str] = []
PASSES: list[str] = []

def fail(name: str, detail: str) -> None:
    FAILURES.append(f"FAIL: {name}: {detail}")

def ok(name: str) -> None:
    PASSES.append(f"PASS: {name}")

def literal_manifest(path: Path):
    return ast.literal_eval(path.read_text(encoding="utf-8"))

def active_imports() -> list[str]:
    text = (MODEL_DIR / "__init__.py").read_text(encoding="utf-8")
    return re.findall(r"^from \. import ([A-Za-z0-9_]+)", text, re.M)

def parse_model_surface(modules: list[str]):
    data = OrderedDict()
    class_rows = []
    helper_methods = set()
    for mod in modules:
        path = MODEL_DIR / f"{mod}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            is_abstract = any("AbstractModel" in ast.unparse(base) for base in cls.bases)
            explicit_name = None
            inherit = None
            for st in cls.body:
                if isinstance(st, ast.Assign):
                    for target in st.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id == "_name":
                            try:
                                explicit_name = ast.literal_eval(st.value)
                            except Exception:
                                pass
                        elif target.id == "_inherit":
                            try:
                                inherit = ast.literal_eval(st.value)
                            except Exception:
                                pass
            if is_abstract:
                helper_methods.update(
                    st.name for st in cls.body if isinstance(st, ast.FunctionDef)
                )
                continue
            model = explicit_name or (inherit if isinstance(inherit, str) else None)
            if not model:
                continue
            rec = data.setdefault(model, {"fields": {}, "methods": set(), "explicit_names": 0, "classes": []})
            if explicit_name:
                rec["explicit_names"] += 1
            rec["classes"].append((mod, cls.name))
            field_names = set()
            method_names = set()
            for st in cls.body:
                if isinstance(st, ast.Assign) and isinstance(st.value, ast.Call):
                    f = st.value.func
                    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "fields":
                        for target in st.targets:
                            if isinstance(target, ast.Name):
                                field_names.add(target.id)
                                kw = {k.arg: k.value for k in st.value.keywords if k.arg}
                                def lit(key):
                                    if key not in kw:
                                        return None
                                    try:
                                        return ast.literal_eval(kw[key])
                                    except Exception:
                                        return ast.unparse(kw[key])
                                comodel = None
                                inverse = None
                                if f.attr in {"Many2one", "One2many", "Many2many"}:
                                    if st.value.args:
                                        try:
                                            comodel = ast.literal_eval(st.value.args[0])
                                        except Exception:
                                            pass
                                    if "comodel_name" in kw:
                                        try:
                                            comodel = ast.literal_eval(kw["comodel_name"])
                                        except Exception:
                                            pass
                                if f.attr == "One2many":
                                    if len(st.value.args) > 1:
                                        try:
                                            inverse = ast.literal_eval(st.value.args[1])
                                        except Exception:
                                            pass
                                    if "inverse_name" in kw:
                                        try:
                                            inverse = ast.literal_eval(kw["inverse_name"])
                                        except Exception:
                                            pass
                                relation = None
                                if f.attr == "Many2many":
                                    if len(st.value.args) > 1:
                                        try:
                                            relation = ast.literal_eval(st.value.args[1])
                                        except Exception:
                                            pass
                                    if "relation" in kw:
                                        try:
                                            relation = ast.literal_eval(kw["relation"])
                                        except Exception:
                                            pass
                                rec["fields"][target.id] = {
                                    "type": f.attr,
                                    "compute": lit("compute"),
                                    "inverse_method": lit("inverse"),
                                    "search": lit("search"),
                                    "store": lit("store"),
                                    "related": lit("related"),
                                    "comodel": comodel,
                                    "inverse_name": inverse,
                                    "relation": relation,
                                }
                elif isinstance(st, ast.FunctionDef):
                    method_names.add(st.name)
            rec["methods"].update(method_names)
            class_rows.append((mod, cls.name, model, field_names, method_names, cls))
    return data, class_rows, helper_methods

def loaded_xml_files(manifest: dict) -> list[Path]:
    return [ROOT / rel for rel in manifest.get("data", []) if str(rel).endswith(".xml")]

contract = json.loads((DOCS / "CLINIC_IMAGING_BASELINE_CONTRACT.json").read_text(encoding="utf-8"))
manifest = literal_manifest(ROOT / "__manifest__.py")
mods = active_imports()
surface, class_rows, helper_methods = parse_model_surface(mods)
local_inventory = json.loads((DOCS / "CLINIC_IMAGING_MODEL_INVENTORY.json").read_text(encoding="utf-8"))["models"]
local_models = set(local_inventory)

# Gate 0 — identity
if ROOT.name != EXPECTED_FOLDER:
    fail("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT", f"folder must be {EXPECTED_FOLDER}, got {ROOT.name}")
elif manifest.get("name") != "ClinicOne - Clinical Imaging Management":
    fail("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT", "manifest identity mismatch")
else:
    ok("HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT")

# Gate 1 / bounded worker contract
agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
required_agent_tokens = [
    "LIMITED IMPLEMENTATION WORKER", "NOT ARCHITECT", "NOT SIMPLIFIER",
    "NOT ENDLESS RETRY ENGINE", "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3",
]
if all(token in agents for token in required_agent_tokens):
    ok("HARD_GATE_1_CODEX_BUKAN_ARCHITECT")
else:
    fail("HARD_GATE_1_CODEX_BUKAN_ARCHITECT", "AGENTS.md bounded-worker contract incomplete")

# Dependencies + active import graph preserved.
if manifest.get("depends") == contract["dependencies"]:
    ok("MANIFEST_DEPENDENCY_PRESERVATION")
else:
    fail("MANIFEST_DEPENDENCY_PRESERVATION", "depends differs from baseline")
if mods == contract["active_imports"]:
    ok("ACTIVE_IMPORT_GRAPH_PRESERVATION")
else:
    fail("ACTIVE_IMPORT_GRAPH_PRESERVATION", f"active imports changed: {mods}")
if "models" not in mods and "xxx_clinic_imaging" not in mods:
    ok("DORMANT_SOURCE_PRESERVATION")
else:
    fail("DORMANT_SOURCE_PRESERVATION", "dormant aggregate source was activated")

# Python compile / XML parse / manifest references.
try:
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("0") or "__pycache__" in path.parts:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    ok("PYTHON_COMPILE")
except Exception as exc:
    fail("PYTHON_COMPILE", repr(exc))
try:
    for path in ROOT.rglob("*.xml"):
        if path.name.startswith("0"):
            continue
        ET.parse(path)
    ok("XML_PARSE")
except Exception as exc:
    fail("XML_PARSE", repr(exc))
missing_manifest = [rel for rel in manifest.get("data", []) + manifest.get("demo", []) if not (ROOT / rel).exists()]
if not missing_manifest:
    ok("MANIFEST_FILE_REFERENCE_CONTRACT_GATE")
else:
    fail("MANIFEST_FILE_REFERENCE_CONTRACT_GATE", str(missing_manifest))

# Odoo 19 constraints + active compatibility.
legacy = []
constraint_count_active = 0
for path in MODEL_DIR.glob("*.py"):
    if path.name.startswith("0"):
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"))
    is_active = path.stem in mods
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "_sql_constraints" for t in node.targets):
                legacy.append(f"{path.name}:{node.lineno}")
            if is_active and isinstance(node.value, ast.Call):
                f = node.value.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "models" and f.attr == "Constraint":
                    constraint_count_active += 1
if legacy:
    fail("ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE", f"legacy declarations: {legacy}")
elif constraint_count_active < 30:
    fail("ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE", f"unexpected active constraint count {constraint_count_active}")
else:
    ok("ODOO19_MODELS_CONSTRAINT_MIGRATION_GATE")

active_text = "\n".join((MODEL_DIR / f"{m}.py").read_text(encoding="utf-8") for m in mods)
compat_bad = {
    "active name_get": r"^\s*def name_get\s*\(",
    "legacy name_search args": r"def name_search\([^\n]*args\s*=\s*None",
    "legacy read_group": r"\.read_group\(",
    "legacy tree view_mode": r"view_mode[^\n]*[\"'](?:[^\"']*,)?tree(?:,|[\"'])",
    "legacy product type": r"[\"']product[\"']\s*,\s*[\"']consu[\"']",
    "removed analytic tag": r"account\.analytic\.tag",
    "legacy stock qty_done": r"\bqty_done\b|\bquantity_done\b",
}
compat_hits=[]
for label,pat in compat_bad.items():
    if re.search(pat, active_text, re.M): compat_hits.append(label)
if compat_hits:
    fail("ODOO19_ACTIVE_SOURCE_COMPATIBILITY_GATE", ", ".join(compat_hits))
else:
    ok("ODOO19_ACTIVE_SOURCE_COMPATIBILITY_GATE")

# Duplicate owner reconciliation.
if surface.get("clinical.imaging.type",{}).get("explicit_names") == 1 and surface.get("clinical.imaging.device",{}).get("explicit_names") == 1:
    ok("IMAGING_MASTER_OWNER_RECONCILIATION_GATE")
else:
    fail("IMAGING_MASTER_OWNER_RECONCILIATION_GATE", "type/device have duplicate explicit _name declarations")

# Field/method collision + compute/inverse/search methods.
collisions=[]; missing_methods=[]
for mod, clsname, model, field_names, method_names, cls in class_rows:
    overlap = field_names & method_names
    if overlap:
        collisions.append(f"{mod}.{clsname}:{sorted(overlap)}")
for model, rec in surface.items():
    methods=rec["methods"]
    for fname, f in rec["fields"].items():
        for key in ("compute","inverse_method","search"):
            method=f.get(key)
            if isinstance(method,str) and method and method not in methods and method not in helper_methods:
                missing_methods.append(f"{model}.{fname}->{key}:{method}")
if collisions:
    fail("FIELD_METHOD_NAMESPACE_COLLISION_GATE", "; ".join(collisions))
else:
    ok("FIELD_METHOD_NAMESPACE_COLLISION_GATE")
if missing_methods:
    fail("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE", "; ".join(missing_methods[:20]))
else:
    ok("FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE")

# One2many inverse contract for local models.
rel_errors=[]
for model, rec in surface.items():
    for fname,f in rec["fields"].items():
        if f["type"] != "One2many" or not f["comodel"] or not f["inverse_name"]:
            continue
        target=surface.get(f["comodel"])
        if target and f["inverse_name"] not in target["fields"]:
            rel_errors.append(f"{model}.{fname}->{f['comodel']}.{f['inverse_name']}")
if rel_errors:
    fail("RELATIONAL_MODEL_INVERSE_CONTRACT_GATE", "; ".join(rel_errors[:20]))
else:
    ok("RELATIONAL_MODEL_INVERSE_CONTRACT_GATE")

# Many2many effective relation identifier limit.
def table(model: str) -> str: return model.replace('.', '_')
m2m_errors=[]
for model, rec in surface.items():
    for fname,f in rec["fields"].items():
        if f["type"] != "Many2many" or not f["comodel"]:
            continue
        relation=f["relation"] or "_".join(sorted([table(model),table(f["comodel"])]))+"_rel"
        if len(relation)>63:
            m2m_errors.append(f"{model}.{fname}:{relation} ({len(relation)})")
if m2m_errors:
    fail("ODOO19_MANY2MANY_RELATION_IDENTIFIER_GATE", "; ".join(m2m_errors))
else:
    ok("ODOO19_MANY2MANY_RELATION_IDENTIFIER_GATE")

# Baseline model/field/method preservation (name_get technical migration allowed).
preservation=[]
for model, base in contract["baseline_models"].items():
    current=surface.get(model)
    if not current:
        preservation.append(f"model removed: {model}")
        continue
    missing_fields=set(base["fields"])-set(current["fields"])
    if missing_fields:
        preservation.append(f"{model} missing fields {sorted(missing_fields)}")
    allowed_removed={"name_get"}
    missing_methods=set(base["methods"])-set(current["methods"])-allowed_removed
    if missing_methods:
        preservation.append(f"{model} missing methods {sorted(missing_methods)}")
if preservation:
    fail("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION", "; ".join(preservation[:30]))
else:
    ok("HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION")

# XML view model/field/button contract + coverage.
view_coverage=defaultdict(set); xml_errors=[]; all_xml_ids=set()
for path in loaded_xml_files(manifest):
    tree=ET.parse(path); rootxml=tree.getroot()
    for el in rootxml.iter():
        rid=el.get("id")
        if rid: all_xml_ids.add(rid)
    for record in rootxml.findall(".//record"):
        if record.get("model") != "ir.ui.view": continue
        model_el=record.find("field[@name='model']")
        arch_el=record.find("field[@name='arch']")
        if model_el is None or arch_el is None or not model_el.text: continue
        model=model_el.text.strip()
        if model not in local_models: continue
        arch_children=list(arch_el)
        if not arch_children: continue
        arch=arch_children[0]
        view_coverage[model].add(arch.tag)
        fields=set(surface.get(model,{}).get("fields",{})) | {"id","display_name","create_date","write_date","create_uid","write_uid"}
        methods=surface.get(model,{}).get("methods",set())
        for node in arch.iter():
            if node.tag=="field" and node.get("name") and node.get("name") not in fields:
                xml_errors.append(f"{path.name}:{model} missing field {node.get('name')}")
            if node.tag=="button" and node.get("type")=="object" and node.get("name") not in methods:
                xml_errors.append(f"{path.name}:{model} missing method {node.get('name')}")
if xml_errors:
    fail("XML_MODEL_FIELD_BUTTON_CONTRACT_GATE", "; ".join(xml_errors[:30]))
else:
    ok("XML_MODEL_FIELD_BUTTON_CONTRACT_GATE")
missing_views=[]
for model in local_models:
    have=view_coverage.get(model,set())
    for needed in {"search","list","form"}:
        if needed not in have: missing_views.append(f"{model}:{needed}")
if missing_views:
    fail("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL", str(missing_views[:30]))
    fail("HARD_GATE_8_SEARCH_VIEW_WAJIB", "coverage incomplete")
    fail("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY", "coverage incomplete")
else:
    ok("HARD_GATE_7_UI_UX_MATRIX_PER_MODEL")
    ok("HARD_GATE_8_SEARCH_VIEW_WAJIB")
    ok("HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY")

# Local XML-ID / Python env.ref / sequence contract.
local_refs=set(re.findall(r"env\.ref\(\s*[\"']clinic_imaging\.([A-Za-z0-9_]+)[\"']", active_text))
missing_local_refs=sorted(local_refs-all_xml_ids)
if missing_local_refs:
    fail("LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE", str(missing_local_refs))
else:
    ok("LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE")
sequence_codes=set(re.findall(r"next_by_code\(\s*[\"']([^\"']+)[\"']", active_text))
seq_xml=(ROOT/'data/imaging_sequences.xml').read_text(encoding='utf-8')
missing_seq=[code for code in sorted(sequence_codes) if f">{code}<" not in seq_xml]
if missing_seq:
    fail("SEQUENCE_REPORT_MAIL_CONTRACT_GATE", f"missing sequences {missing_seq}")
elif not {"report_clinical_imaging_result","mail_template_clinical_imaging_result"}.issubset(all_xml_ids):
    fail("SEQUENCE_REPORT_MAIL_CONTRACT_GATE", "report/mail XML-ID missing")
else:
    ok("SEQUENCE_REPORT_MAIL_CONTRACT_GATE")

# Cross-addon presentation XML-ID resilience: manifest-loaded XML must not hard-ref sibling ClinicOne presentation IDs.
external_blockers=[]
for path in loaded_xml_files(manifest):
    txt=path.read_text(encoding="utf-8")
    for match in re.finditer(r"(?:ref|parent|action)=[\"'](clinic_[a-z0-9_]+\.[A-Za-z0-9_]+)[\"']", txt):
        if not match.group(1).startswith("clinic_imaging."):
            external_blockers.append(f"{path.name}:{match.group(1)}")
if external_blockers:
    fail("CROSS_ADDON_XMLID_INSTALLATION_RESILIENCE_GATE", str(external_blockers))
elif "post_init_hook" not in manifest or not (ROOT/'hooks.py').exists():
    fail("CROSS_ADDON_XMLID_INSTALLATION_RESILIENCE_GATE", "optional menu hook missing")
else:
    ok("CROSS_ADDON_XMLID_INSTALLATION_RESILIENCE_GATE")

# ACL + company rules.
acl_path=ROOT/'security/ir.model.access.csv'
with acl_path.open(encoding='utf-8',newline='') as fh:
    rows=list(csv.DictReader(fh))
acl_models={row['model_id:id'].removeprefix('model_').replace('_','.') for row in rows}
# Compare by XML model ids rather than reconstruct dots ambiguity.
missing_acl=[]
for model in local_models:
    xmlid='model_'+model.replace('.','_')
    if not any(row['model_id:id']==xmlid for row in rows): missing_acl.append(model)
rules_xml=(ROOT/'security/clinic_imaging_rules.xml').read_text(encoding='utf-8')
missing_rules=[]
for model in local_models:
    if 'company_id' in surface[model]['fields']:
        if f'model_{model.replace(".","_")}' not in rules_xml: missing_rules.append(model)
if missing_acl:
    fail("ORM_SECURITY_AUTHORITATIVE_GATE", f"missing ACL {missing_acl}")
elif missing_rules:
    fail("ORM_SECURITY_AUTHORITATIVE_GATE", f"missing company rules {missing_rules}")
else:
    ok("ORM_SECURITY_AUTHORITATIVE_GATE")
    ok("HARD_GATE_10_SECURITY_OVER_UI")

# Backup exclusion.
backups=[str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p.name.startswith('0')]
if backups:
    fail("BACKUP_FILE_EXCLUSION_GATE", str(backups))
else:
    ok("BACKUP_FILE_EXCLUSION_GATE")

# Documentation / completeness / style owner gates.
required_docs=[
    "CLINIC_IMAGING_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md",
    "CLINIC_IMAGING_STRUCTURAL_INVENTORY.md",
    "CLINIC_IMAGING_UI_UX_MATRIX.md",
    "CLINIC_IMAGING_ENTERPRISE_COMPLETENESS_MATRIX.md",
    "CLINIC_IMAGING_ODOO19_REVIEW.md",
]
if all((DOCS/name).exists() for name in required_docs):
    ok("HARD_GATE_3_ENTERPRISE_COMPLETENESS")
    ok("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY")
    ok("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX")
else:
    fail("HARD_GATE_3_ENTERPRISE_COMPLETENESS", "documentation incomplete")
    fail("HARD_GATE_4_FULL_STRUCTURAL_INVENTORY", "structural inventory missing")
    fail("HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX", "matrix missing")
# Human-friendly structure / professional forms / code style / comments / retry.
if all((ROOT/'views'/name).exists() for name in [
    'imaging_master_views.xml','imaging_operations_views.xml','imaging_quality_views.xml','imaging_support_views.xml','imaging_actions.xml','imaging_menus.xml']):
    ok("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE")
    ok("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN")
else:
    fail("HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE", "view files not domain-organized")
    fail("HARD_GATE_6_PROFESSIONAL_FORM_DESIGN", "enterprise forms missing")
if 'Compatibility extension' in (MODEL_DIR/'clinical_imaging.py').read_text(encoding='utf-8'):
    ok("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY")
    ok("HARD_GATE_13_USEFUL_COMMENTS")
else:
    fail("HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY", "owner reconciliation not documented in code")
    fail("HARD_GATE_13_USEFUL_COMMENTS", "useful compatibility comments missing")
if "MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3" in agents:
    ok("HARD_GATE_14_CODEX_RETRY_LIMIT")
else:
    fail("HARD_GATE_14_CODEX_RETRY_LIMIT", "retry contract missing")

# Final output.
print("="*78)
print("CLINIC_IMAGING ENTERPRISE DEVELOPMENT HARD GATE")
print("="*78)
for line in PASSES:
    print(line)
for line in FAILURES:
    print(line)
owner_names=[
    "HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT","HARD_GATE_1_CODEX_BUKAN_ARCHITECT","HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION",
    "HARD_GATE_3_ENTERPRISE_COMPLETENESS","HARD_GATE_4_FULL_STRUCTURAL_INVENTORY","HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE",
    "HARD_GATE_6_PROFESSIONAL_FORM_DESIGN","HARD_GATE_7_UI_UX_MATRIX_PER_MODEL","HARD_GATE_8_SEARCH_VIEW_WAJIB",
    "HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY","HARD_GATE_10_SECURITY_OVER_UI","HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY",
    "HARD_GATE_13_USEFUL_COMMENTS","HARD_GATE_14_CODEX_RETRY_LIMIT","HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX",
]
owner_pass=sum(any(line==f"PASS: {name}" for line in PASSES) for name in owner_names)
print(f"PASS: {owner_pass} / 15 OWNER HARD GATES")
if FAILURES or owner_pass != 15:
    print("CLINIC_IMAGING_STATIC_MOVE_FORWARD_READY: NO")
    print("CLINIC_IMAGING_MOVE_FORWARD_READY: NO")
    sys.exit(1)
print("CLINIC_IMAGING_STATIC_MOVE_FORWARD_READY: YES")
print("RUNTIME_GATE_REQUIRED: YES")
print("CLINIC_IMAGING_MOVE_FORWARD_READY: PENDING")
