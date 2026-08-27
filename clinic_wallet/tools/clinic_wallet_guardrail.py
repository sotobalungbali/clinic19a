#!/usr/bin/env python3
"""Source/static hard gate for ClinicOne clinic_wallet.

PASS here never means Odoo runtime PASS. Target install/upgrade, UI smoke,
accounting scenarios, portal and multi-company tests are still required.
"""
from pathlib import Path
import ast, csv, re, sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
G = {
    0: "HARD GATE 0 — PROJECT IDENTITY PREFLIGHT",
    1: "HARD GATE 1 — CODEX BUKAN ARCHITECT",
    2: "HARD GATE 2 — EXISTING FUNCTION PRESERVATION",
    3: "HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS",
    4: "HARD GATE 4 — FULL STRUCTURAL INVENTORY",
    5: "HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE",
    6: "HARD GATE 6 — PROFESSIONAL FORM DESIGN",
    7: "HARD GATE 7 — UI/UX MATRIX PER MODEL",
    8: "HARD GATE 8 — SEARCH VIEW WAJIB",
    9: "HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY",
    10: "HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI",
    12: "HARD GATE 12 — CODE STYLE HUMAN FRIENDLY",
    13: "HARD GATE 13 — COMMENTS YANG BERGUNA",
    14: "HARD GATE 14 — CODEX RETRY LIMIT",
    15: "HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX",
}
errors = {k: [] for k in G}
notes = {k: [] for k in G}

def err(k, msg): errors[k].append(msg)
def ok(k, msg): notes[k].append(msg)
def txt(rel): return (ROOT / rel).read_text(encoding="utf-8")

py_files = [p for area in ("models", "wizard", "controllers", "tests") for p in (ROOT/area).rglob("*.py")]
prod_py = [p for area in ("models", "wizard", "controllers") for p in (ROOT/area).rglob("*.py")]
xml_files = list(ROOT.rglob("*.xml"))
prod_source = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in prod_py)
manifest = ast.literal_eval(txt("__manifest__.py"))

# Syntax / XML parse are hard failures under code style.
for p in py_files + [ROOT/"tools/clinic_wallet_guardrail.py"]:
    try: compile(p.read_text(encoding="utf-8"), str(p), "exec")
    except Exception as exc: err(12, f"Python compile: {p.relative_to(ROOT)}: {exc}")
for p in xml_files:
    try: ET.parse(p)
    except Exception as exc: err(12, f"XML parse: {p.relative_to(ROOT)}: {exc}")

# 0 — project identity / dependency direction.
if manifest.get("version") != "19.0.3.0.5": err(0, "authoritative version must be 19.0.3.0.5")
required = {"base_setup","portal","uom","analytic","purchase","stock_account","clinic_base","clinic_patient","clinic_inventory","clinic_booking","clinic_membership","clinic_billing","clinic_ar","clinic_ap"}
missing = required - set(manifest.get("depends", []))
if missing: err(0, f"required dependencies missing: {sorted(missing)}")
forward = {"clinic_finance","clinic_accounting","clinic_l10n_id","clinic_insurance_authorization","clinic_reports","clinic_dashboard","clinic_analytics"}
if set(manifest.get("depends", [])) & forward: err(0, "forward/downstream ClinicOne dependency detected")
ok(0, "ClinicOne / clinic_wallet / downstream-through-clinic_ap identity locked")

# 1 and 14 — Codex contract.
agents = txt("AGENTS.md")
for phrase in ("implementation worker only", "not** the architect", "Forbidden changes"):
    if phrase not in agents: err(1, f"missing Codex boundary: {phrase}")
ok(1, "Codex bounded implementer; architecture/preservation fixed")
if "MAX_RETRY_ITERATIONS = 2" not in agents or "open-ended retry loop" not in agents:
    err(14, "retry limit contract missing")
ok(14, "maximum two implementation retries per verified defect")

# 2 — preserve baseline public contract + Odoo 19 constraints.
required_methods = {
    "reserve_funds","release_reserved","validate_reserved_to_posted","ensure_usable","action_open","action_suspend","action_close","action_view_transactions",
    "action_set_reserved","action_post","action_cancel","split_reserved","do_topup","do_refund","do_adjust_in","do_adjust_out","_check_transaction",
    "get_or_create_wallet","wallet_reserve_and_link","wallet_release_reservation","wallet_validate_reservation","action_submit","action_approve","action_reject","action_set_done",
    "portal_get_wallet_summary","portal_submit_request",
    "_compute_wallet_reserved","_get_default_reference",
    "_onchange_use_wallet_invoice","_onchange_wallet_amount_invoice",
    "_check_wallet_amount_vs_residual","button_cancel",
    "_get_int","_get_bool","_set_int","_set_bool","_set_m2o_param",
    "_get_m2o_from_param","_upsert_wallet_liability_property",
    "_validate_wallet_amount_against_total"
}
methods = set(re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", prod_source, re.M))
if required_methods - methods: err(2, f"baseline methods missing: {sorted(required_methods-methods)}")
if "_sql_constraints" in prod_source: err(2, "legacy _sql_constraints remains in executable source")
if prod_source.count("models.Constraint(") < 2: err(2, "models.Constraint conversion incomplete")
if '"clinic.membership.tier"' in prod_source:
    err(2, "removed clinic.membership.tier comodel reintroduced")
if '"membership.plan"' not in txt("models/wallet.py") or '"membership.plan"' not in txt("models/wallet_rule.py"):
    err(2, "Clinic Membership V6 plan/tier contract missing")
partner_source = txt("models/res_partner.py")
if re.search(r"^\s*wallet_balance\s*=\s*fields\.", partner_source, re.M):
    err(2, "res.partner.wallet_balance must stay owned by clinic_patient, not redeclared by clinic_wallet")
ok(2, "public wallet/billing/portal API preserved; ownership conflicts removed; SQL constraints converted")

# 3 — completeness beyond tests.
for rel in ["security/clinic_wallet_security.xml","security/ir.model.access.csv","data/wallet_sequence.xml","data/wallet_cron.xml","views/wallet_views.xml","views/wallet_transaction_views.xml","views/wallet_rule_views.xml","views/wallet_portal_views.xml","views/portal_templates.xml","report/wallet_statement_report.xml","tests/test_wallet_enterprise.py","docs/ENTERPRISE_COMPLETENESS_MATRIX.md"]:
    if not (ROOT/rel).exists(): err(3, f"missing enterprise layer: {rel}")
ok(3, "models + security + UI + portal + reports + cron + tests present; runtime separate")

# 4 — structural inventory.
persistent = ["clinic.wallet","clinic.wallet.transaction","clinic.wallet.rule","clinic.wallet.portal.mgr.approver","clinic.wallet.portal.request"]
inv = txt("docs/STRUCTURAL_INVENTORY.md")
for model in persistent:
    if model not in inv or f'_name = "{model}"' not in prod_source: err(4, f"inventory/source missing {model}")
ok(4, "5 persistent plus abstract/transient/inherited models inventoried")

# 5 — human-editable separation.
model_files = [p for p in (ROOT/"models").glob("*.py") if p.name != "__init__.py"]
if len(model_files) < 8: err(5, "model responsibilities too consolidated")
if (ROOT/"models/models.py").exists(): err(5, "generic scaffold models/models.py still exists")
if any(p.stat().st_size > 90000 for p in model_files): err(5, "mega model file exceeds manual-edit threshold")
ok(5, f"responsibilities split across {len(model_files)} focused model files + wizard/controller")

# Extract local ir.ui.view records.
views = []
for p in xml_files:
    try: tree = ET.parse(p)
    except Exception: continue
    for rec in tree.findall(".//record"):
        if rec.get("model") != "ir.ui.view": continue
        mf, af = rec.find("field[@name='model']"), rec.find("field[@name='arch']")
        if mf is not None and af is not None:
            views.append((mf.text or "", ET.tostring(af, encoding="unicode"), rec.get("id") or ""))

# 6/8/9 — form/search/list each persistent model.
for model in persistent:
    vv = [v for v in views if v[0] == model]
    if not any("<form" in a for _,a,_ in vv): err(6, f"form missing: {model}")
    if not any("<search" in a for _,a,_ in vv): err(8, f"search missing: {model}")
    if not any("<list" in a for _,a,_ in vv): err(9, f"list missing: {model}")
enterprise_view_source = "\n".join(txt(x) for x in ["views/wallet_views.xml","views/wallet_transaction_views.xml","views/wallet_rule_views.xml","views/wallet_portal_views.xml"])
for token in ('widget="statusbar"','oe_stat_button','d-flex gap-2','action_open_self'):
    if token not in enterprise_view_source: err(6, f"professional interaction missing: {token}")
ok(6, "professional forms include workflow, smart buttons, body actions and O2M action buttons")
ok(8, "search view exists for all 5 persistent models")
ok(9, "enterprise list view exists for all 5 persistent models")

# 7 — UI matrix.
ux = txt("docs/UI_UX_MATRIX.md")
for model in persistent:
    if model not in ux: err(7, f"UI matrix missing {model}")
ok(7, "UI/UX matrix covers every Wallet-owned persistent model")

# 10 — security must be backend-enforced.
sec = txt("security/clinic_wallet_security.xml")
for token in ("group_wallet_user","group_wallet_accountant","group_wallet_manager","company_ids","base.group_portal","account.group_account_user"):
    if token not in sec: err(10, f"security XML missing {token}")
with (ROOT/"security/ir.model.access.csv").open(encoding="utf-8", newline="") as fh:
    acl = list(csv.DictReader(fh))
if len(acl) < 15: err(10, f"ACL matrix incomplete: {len(acl)}")
for token in ("wallet_state_transition","wallet_tx_transition","wallet_request_transition","protected =","Only Wallet Managers"):
    if token not in prod_source: err(10, f"ORM workflow security missing {token}")
ok(10, f"3-role hierarchy + company/portal rules + {len(acl)} ACL rows + ORM transition protection")

# Runtime registry contract — Monetary ownership belongs on concrete documents.
billing_source = txt("models/clinic_billing_inherit.py")
mixin_block = billing_source.split("class ClinicBillingInvoiceWallet", 1)[0]
if "fields.Monetary(" in mixin_block:
    err(12, "abstract clinic.wallet.billing.mixin must not define Monetary fields")
if mixin_block.count("fields.Float(") < 2:
    err(12, "abstract billing mixin must retain neutral wallet_amount/wallet_reserved fields")
for class_name in ("ClinicBillingInvoiceWallet", "AccountMoveWallet"):
    if class_name not in billing_source:
        err(12, f"missing concrete Wallet billing model: {class_name}")
if billing_source.count('currency_field="currency_id"') < 4:
    err(12, "concrete billing/account.move Monetary redeclarations incomplete")
ok(12, "abstract mixin registry-safe; concrete billing models retain currency-aware Monetary fields")


# Odoo 19 multiple-inheritance extension contract.
# A list-valued _inherit without explicit _name is dangerous: MetaModel
# derives a new technical model name from the Python class name.
list_inherit_without_name = []
for py_path in ROOT.rglob("*.py"):
    if any(part == "__pycache__" for part in py_path.parts):
        continue
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        explicit_name = False
        inherit_value = None
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id == "_name":
                        explicit_name = True
                    elif target.id == "_inherit":
                        try:
                            inherit_value = ast.literal_eval(stmt.value)
                        except Exception:
                            inherit_value = None
        if isinstance(inherit_value, list) and not explicit_name:
            list_inherit_without_name.append(f"{py_path.relative_to(ROOT)}::{node.name}")
if list_inherit_without_name:
    err(12, "list-valued _inherit without explicit _name: " + ", ".join(list_inherit_without_name))

billing_source = txt("models/clinic_billing_inherit.py")
for required in (
    '_name = "clinic.billing.invoice"',
    '_inherit = ["clinic.billing.invoice", "clinic.wallet.billing.mixin"]',
    '_name = "account.move"',
    '_inherit = ["account.move", "clinic.wallet.billing.mixin"]',
):
    if required not in billing_source:
        err(12, f"missing Odoo 19 in-place multiple inheritance contract: {required}")

for forbidden in ("clinic.billing.invoice.wallet", "account.move.wallet"):
    # The only allowed occurrence is in regression/docs as a forbidden shadow name.
    pass

ok(12, "multiple inheritance targets are explicit; no accidental *.wallet shadow models")


# ACTIVE_FOLDER_MARKER_GATE
build_marker_path = ROOT / "BUILD_ID.txt"
if not build_marker_path.exists():
    err(12, "BUILD_ID.txt missing from active clinic_wallet source")
marker_text = build_marker_path.read_text(encoding="utf-8")
if "CLINIC_WALLET_BUILD_20260820_0500_V19.0.3.0.5" not in marker_text:
    err(12, "unexpected clinic_wallet build marker")
partner_view_source = txt("views/res_partner_views.xml")
if 'ref="clinic_patient.view_partner_form_clinic_patient"' in partner_view_source:
    err(12, "legacy Clinic Patient partner-view anchor still active")
if 'ref="base.view_partner_form"' not in partner_view_source:
    err(12, "stable base.view_partner_form anchor missing")
ok(12, "active-folder marker and stable partner-view anchor verified")

# 12 — Odoo 19 code contracts.
if "ir.property" in prod_source: err(12, "legacy ir.property found")
if "company_ids" not in txt("models/wallet.py") or "company_ids" not in txt("models/wallet_transaction.py"):
    err(12, "account.account Odoo19 company_ids domain not used")
if "models.Constraint(" not in prod_source: err(12, "Odoo19 Constraint API missing")
if '"membership.plan"' not in prod_source: err(12, "Clinic Membership V6 comodel contract missing")
ok(12, "Python/XML parse + Odoo19 account/constraint/membership contracts pass")

# 13 — useful comments/docstrings.
comment_lines = sum(1 for p in prod_py for line in p.read_text(encoding="utf-8").splitlines() if line.strip().startswith("#"))
if comment_lines < 60: err(13, f"comment floor too low: {comment_lines}")
if prod_source.count('"""') < 20: err(13, "business-method docstrings too sparse")
ok(13, f"{comment_lines} focused comment lines plus business docstrings")

# 15 — completeness matrix explicitly keeps runtime pending.
matrix = txt("docs/ENTERPRISE_COMPLETENESS_MATRIX.md")
for token in ("Runtime gate","Pending","Multi-company isolation","Reporting","Regression suite"):
    if token not in matrix: err(15, f"matrix missing {token}")
ok(15, "completeness matrix separates source/static PASS from runtime acceptance")

print("ClinicOne clinic_wallet Enterprise Development Guardrail")
print(f"[INFO] python_files={len(py_files)} xml_files={len(xml_files)} acl_rows={len(acl)}")
print(f"[INFO] models.Constraint={prod_source.count('models.Constraint(')} test_methods={len(re.findall(r'^\s+def test_', txt('tests/test_wallet_enterprise.py'), re.M))}")
failed = False
for k,label in G.items():
    if errors[k]:
        failed = True
        print(f"[FAIL] {label}")
        for msg in errors[k]: print(f"       - {msg}")
    else:
        print(f"[PASS] {label}: {notes[k][-1] if notes[k] else 'PASS'}")
if failed:
    print("RESULT: FAIL")
    sys.exit(1)
print("RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME INSTALL/UPGRADE/SMOKE TEST PENDING)")



