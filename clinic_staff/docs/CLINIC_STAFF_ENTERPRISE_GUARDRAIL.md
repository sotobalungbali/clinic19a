# ClinicOne Enterprise Development Guardrail — clinic_staff

## Purpose
This guardrail makes the existing `clinic_staff` functional baseline immutable by default and constrains Codex to bounded implementation work.

## Baseline status
- Functional baseline: FINISHED
- Target platform: Odoo 19 Community Edition
- Review mode: technical hardening only
- Sibling-addon edits: forbidden
- Architecture changes: forbidden
- Simplification-by-deletion: forbidden
- Maximum focused repair attempts per blocker class: 3

## Hard-gate design
The gate has two layers:

### Layer A — durable Codex instruction
`AGENTS.md` is stored at the addon root. Codex must obey it whenever operating in this scope.

### Layer B — machine-checkable baseline
`tools/clinic_staff_guardrail.py` compares the active source against
`docs/CLINIC_STAFF_BASELINE_CONTRACT.json`.

The validator blocks:
- model deletion/addition
- field deletion/addition
- method deletion/addition
- SQL-constraint object drift
- source runtime file drift
- dependency drift
- manifest data/demo drift
- reintroduction of `_sql_constraints`
- legacy `name_search(... args=...)`
- action `view_mode` values using legacy `tree`
- missing string-referenced compute/inverse/search methods
- Python syntax failures
- XML parse failures

Backup files whose filename begins with `0` are excluded from the active-source contract.

## Runtime gate
The validator is intentionally not allowed to fake Odoo runtime proof. On the target PC, after the static guardrail exits 0, the operator must still verify:
- Odoo install/upgrade
- repeat upgrade
- registry startup
- focused staff workflow smoke

## Retry stop rule
A Codex attempt is a focused edit/test cycle for one blocker/root-cause class. At 3 failed attempts, Codex must stop and emit `MOVE_FORWARD_READY: NO` with evidence. It must not continue to V4/V5/VN autonomously.
