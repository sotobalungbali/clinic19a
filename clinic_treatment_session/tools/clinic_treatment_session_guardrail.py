
#!/usr/bin/env python3
from pathlib import Path
import ast
import csv
import re
import sys
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
passes = []
errors = []


def ok(gate, message):
    passes.append(f"[PASS] HARD GATE {gate}: {message}")


def fail(gate, message):
    errors.append(f"[FAIL] HARD GATE {gate}: {message}")


# Gate 0 — identity
try:
    manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
except Exception as exc:
    manifest = {}
    fail(0, f"manifest parse: {exc}")

if manifest.get("version") == "19.0.2.0.4":
    ok(0, "ClinicOne / Odoo 19 release identity locked")
else:
    fail(0, f"unexpected version {manifest.get('version')}")

# Gate 1 — manifest dependency
for dep in ("clinic_booking", "clinic_patient", "clinic_doctor", "clinic_referral", "clinic_billing"):
    if dep not in manifest.get("depends", []):
        fail(1, f"dependency missing: {dep}")
if not any(x.startswith("[FAIL] HARD GATE 1") for x in errors):
    ok(1, "source-actual direct dependencies retained")

# Gate 2 — public contract
all_py = [
    p for p in (ROOT / "models").rglob("*.py")
    if not p.name[:1].isdigit()
]
source = "\n".join(p.read_text(encoding="utf-8") for p in all_py)
for token in (
    'clinic.treatment.session',
    'clinic.treatment.session.line',
    'clinic.treatment.session.stage',
    "generate_treatment_sessions",
    "action_generate_treatment_sessions",
    "action_view_treatment_history",
    "action_view_today_treatment_sessions",
    "prepare_billing_payload_line",
    "reschedule",
):
    if token not in source:
        fail(2, f"historical contract token missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 2") for x in errors):
    ok(2, "historical models and public API preserved")

# Gate 3 — complete release files
required = {
    "security/clinic_treatment_session_security.xml",
    "security/ir.model.access.csv",
    "data/sequence_data.xml",
    "data/session_stage_data.xml",
    "data/mail_template_data.xml",
    "data/cron_data.xml",
    "data/optional_ui_bridge.xml",
    "views/treatment_session_views.xml",
    "views/treatment_session_line_views.xml",
    "views/session_stage_views.xml",
    "views/res_config_settings_views.xml",
    "views/treatment_session_menus.xml",
    "models/enterprise_session.py",
    "models/enterprise_line.py",
    "models/enterprise_booking.py",
    "models/enterprise_billing.py",
    "models/enterprise_navigation.py",
    "models/canonical_bridges.py",
    "models/referral_bridge.py",
    "models/ui_bridge.py",
    "migrations/19.0.2.0.0/pre-migrate.py",
    "docs/FULL_STRUCTURAL_INVENTORY.md",
    "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
    "docs/UI_UX_MATRIX.md",
    "docs/SECURITY_MODEL.md",
    "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
    "docs/CLINIC_DEMO_CORE_PATCH_LEDGER.md",
    "tests/test_source_contracts.py",
}
missing = [rel for rel in sorted(required) if not (ROOT / rel).is_file()]
if missing:
    fail(3, f"files missing: {missing}")
else:
    ok(3, "workflow/security/stock/billing/UI/migration/docs/tests packaged")

# Gate 4 — owned models
for model in (
    '_name = "clinic.treatment.session"',
    '_name = "clinic.treatment.session.line"',
    '_name = "clinic.treatment.session.stage"',
):
    if model not in source:
        fail(4, f"owned model declaration missing: {model}")
if not any(x.startswith("[FAIL] HARD GATE 4") for x in errors):
    ok(4, "three owned persistent models inventoried")

# Gate 5 — bounded files
large = [
    f"{p.relative_to(ROOT)}={len(p.read_text(encoding='utf-8').splitlines())}"
    for p in (ROOT / "models").rglob("*.py")
    if not p.name[:1].isdigit()
    and len(p.read_text(encoding="utf-8").splitlines()) > 900
]
if large:
    fail(5, f"God-class threshold exceeded: {large}")
else:
    ok(5, "model files remain responsibility-bounded")

# Gate 6 — XML / Odoo 19 syntax
xml_files = [p for p in ROOT.rglob("*.xml") if not p.name[:1].isdigit()]
for path in xml_files:
    try:
        ET.parse(path)
    except Exception as exc:
        fail(6, f"XML parse {path.relative_to(ROOT)}: {exc}")
        continue
    text = path.read_text(encoding="utf-8")
    if "<tree" in text or re.search(r"\sattrs\s*=", text) or re.search(r"\sstates\s*=", text):
        fail(6, f"legacy view syntax: {path.relative_to(ROOT)}")
if not any(x.startswith("[FAIL] HARD GATE 6") for x in errors):
    ok(6, f"{len(xml_files)} XML files parse using Odoo 19 syntax")

# Gate 7 — ACL/security
with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
if len(rows) != 8:
    fail(7, f"expected 8 ACL rows, got {len(rows)}")
security = (ROOT / "security/clinic_treatment_session_security.xml").read_text(encoding="utf-8")
for token in ("res.groups.privilege", "group_treatment_session_user", "group_treatment_session_clinician", "group_treatment_session_manager", "allowed_branch_ids"):
    if token not in security:
        fail(7, f"security token missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 7") for x in errors):
    ok(7, "Odoo 19 privilege hierarchy, ACL and branch/company rules present")

# Gate 8 — constraints
if "_sql_constraints" in source:
    fail(8, "legacy _sql_constraints found")
if source.count("models.Constraint(") < 4:
    fail(8, "fewer than 4 Odoo 19 models.Constraint declarations")
if not any(x.startswith("[FAIL] HARD GATE 8") for x in errors):
    ok(8, "Odoo 19 models.Constraint policy PASS")

# Gate 9 — workflow
enterprise = (ROOT / "models/enterprise_session.py").read_text(encoding="utf-8")
for token in ("_workflow_states", "_check_state_transition", "_require_clinician", "action_confirm", "action_start", "action_done", "action_reset_draft"):
    if token not in enterprise:
        fail(9, f"workflow token missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 9") for x in errors):
    ok(9, "backend workflow enforcement present")

# Gate 10 — stock
line = (ROOT / "models/enterprise_line.py").read_text(encoding="utf-8")
for token in ("move._action_done()", 'if move.state != "done":', "A completed inventory movement cannot be hidden"):
    if token not in line:
        fail(10, f"stock token missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 10") for x in errors):
    ok(10, "stock completion verification and immutable reset guard present")

# Gate 11 — exact runtime traceback regression
room_path = ROOT / "models/extensions/ext_room_device.py"
room_source = room_path.read_text(encoding="utf-8")
room_tree = ast.parse(room_source)
method = None
for cls in room_tree.body:
    if isinstance(cls, ast.ClassDef):
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "is_available":
                method = node
if method is None:
    fail(11, "booking.room is_available override missing")
else:
    args = [a.arg for a in method.args.args]
    expected = [
        "self", "start_dt", "end_dt",
        "ignore_booking_id", "consider_capacity", "ignore_session_ids",
    ]
    if args[:6] != expected:
        fail(11, f"signature mismatch: {args}")
    segment = ast.get_source_segment(room_source, method) or ""
    for token in (
        "super().is_available",
        "ignore_booking_id=ignore_booking_id",
        "consider_capacity=consider_capacity",
        'self.env["clinic.treatment.session"]',
    ):
        if token not in segment:
            fail(11, f"runtime repair token missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 11") for x in errors):
    ok(11, "ignore_booking_id/consider_capacity owner API + super() delegation PASS")

# Gate 12 — billing
billing = (ROOT / "models/enterprise_billing.py").read_text(encoding="utf-8")
for token in ("action_create_clinic_billing", "clinic.billing.invoice", "Command.create", "action_view_clinic_billing"):
    if token not in billing:
        fail(12, f"billing token missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 12") for x in errors):
    ok(12, "Clinic Billing bridge present")

# Gate 13 — no backups / Python syntax
backup = [
    str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
    if p.is_file() and p.name[:1].isdigit()
]
if backup:
    fail(13, f"digit-prefixed backups packaged: {backup}")
for path in all_py:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        fail(13, f"Python parse {path.relative_to(ROOT)}: {exc}")
if not any(x.startswith("[FAIL] HARD GATE 13") for x in errors):
    ok(13, f"Python AST PASS; no digit-prefixed backup files")

# Gate 14 — migration/tests/ledger
for rel in (
    "migrations/19.0.2.0.0/pre-migrate.py",
    "migrations/19.0.2.0.3/post-migrate.py",
    "tests/test_source_contracts.py",
    "docs/CLINIC_DEMO_CORE_PATCH_LEDGER.md",
):
    if not (ROOT / rel).is_file():
        fail(14, f"evidence missing: {rel}")
if not any(x.startswith("[FAIL] HARD GATE 14") for x in errors):
    ok(14, "migration, regression and patch-ledger evidence packaged")

# Gate 15 — completeness matrix
matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text(encoding="utf-8")
for token in (
    "Historical model/method preservation",
    "Booking → Session generation",
    "State-machine workflow",
    "Stock move completion verification",
    "Clinic Billing bridge",
    "Multi-company / branch security",
    "Odoo 19 models.Constraint",
    "`ignore_booking_id` owner API compatibility",
):
    if token not in matrix:
        fail(15, f"completeness evidence missing: {token}")
if not any(x.startswith("[FAIL] HARD GATE 15") for x in errors):
    ok(15, "enterprise completeness evidence PASS")

if errors:
    print("CLINIC_TREATMENT_SESSION_GUARDRAIL: FAIL")
    for item in passes + errors:
        print(item)
    sys.exit(1)

print("CLINIC_TREATMENT_SESSION_GUARDRAIL: PASS")
for item in passes:
    print(item)
