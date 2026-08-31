
# ClinicOne / clinic_doctor — Codex Hard Gate

PROJECT_IDENTITY_PREFLIGHT: REQUIRED
PROJECT: ClinicOne
ADDON: clinic_doctor
AUTHORITATIVE_BASELINE: user-provided active source; ignore filename prefix `0` backups
PRESERVATION_RULE: functional baseline is FINISHED; preserve business behavior
ALLOWED_CHANGE: bounded Odoo 19 technical hardening and verified blocker repair only
FORBIDDEN_CHANGE: architecture, simplification, scope expansion, ownership moves, sibling edits, core247 integration
CURRENT_VERIFIED_STATUS: clinic_base and clinic_staff frozen/installed; clinic_doctor source hardening complete, target-PC runtime pending

CODEX_ROLE: LIMITED_IMPLEMENTATION_WORKER
NOT_ARCHITECT: YES
NOT_SIMPLIFIER: YES
NOT_AUTONOMOUS_REFACTORER: YES
NOT_UNBOUNDED_RETRY_ENGINE: YES
MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER: 3

Before editing:
1. Read `docs/CLINIC_DOCTOR_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md`.
2. Read `docs/CLINIC_DOCTOR_BASELINE_CONTRACT.json`.
3. Run `python3 tools/clinic_doctor_guardrail.py`.
4. State the exact blocker/root-cause class and files to touch.
5. Refuse to redesign architecture or change ownership/dependencies unless the user explicitly authorizes it.

During editing:
- Touch only `clinic_doctor` unless explicitly authorized otherwise.
- Never delete/rename/merge models, fields, methods, states, actions, or business flows to make a test pass.
- Never activate dormant modules just because they exist.
- Never use files whose filename begins with digit `0` as implementation source.
- Preserve all existing ClinicOne manifest dependencies. `account` and `sale` are the only dependency additions authorized by this hardening because active fields reference `account.move` and `sale.order`.
- A retry must test a new root-cause hypothesis. Cosmetic rewrites do not reset the attempt count.

After each focused attempt:
1. Run `python3 tools/clinic_doctor_guardrail.py`.
2. Run the requested Odoo runtime command/test.
3. Record PASS/FAIL and the root cause.

After the third failed focused attempt for the same blocker:
STOP.
Do not create V4/V5/V11/etc.
Emit:
`MOVE_FORWARD_READY: NO`
and report traceback, root cause, touched files, three attempted hypotheses/fixes, and the architecture decision needed.

Definition of done:
- Guardrail PASS.
- Odoo 19 fresh install/upgrade as requested PASS.
- Repeat upgrade PASS.
- Focused doctor smoke PASS.
- No preservation-contract regression.
Only then: `CLINIC_DOCTOR_MOVE_FORWARD_READY: YES`.

