# ClinicOne / clinic_staff — Enterprise Development Guardrail

## Authority
This addon is a FINISHED functional baseline. Codex is a LIMITED IMPLEMENTATION WORKER only.

Codex MUST NOT act as:
- architect
- simplifier
- product designer
- dependency optimizer
- model owner reassigner
- autonomous refactorer
- unbounded retry engine

## Hard source rules
1. Preserve every active business model, field, method, selection value, workflow state, and dependency unless an explicit task instruction names the exact change.
2. Do not rename, delete, merge, move, or replace models/fields/methods.
3. Do not activate, inspect as baseline, merge from, or copy logic from user backup files whose filename begins with digit `0`.
4. Do not modify `clinic_base` or any sibling addon while fixing `clinic_staff`.
5. Do not add or remove manifest dependencies.
6. Do not enable currently unloaded ACL/data/demo/view files unless the task explicitly authorizes it.
7. Do not uncomment dormant integrations or invent new integration bridges.
8. Do not remove business behavior merely to make installation/tests pass.
9. Do not replace implementation with stubs, `pass`, broad exception swallowing, fake PASS markers, or disabled tests.
10. Odoo 19 compatibility work must preserve semantics.

## Allowed implementation scope for this hardening baseline
- migrate legacy `_sql_constraints` declarations to Odoo 19 `models.Constraint`
- correct Odoo 19 API signatures/view type naming where required
- repair accidental source defects that prevent already-present behavior from functioning
- preserve existing manifest dependency graph
- compile/parse/static validation
- runtime install/upgrade repair only when a concrete traceback proves the blocker belongs to `clinic_staff`

Anything beyond this scope is BLOCKED pending explicit user approval.

## Attempt budget
MAX_REPAIR_ATTEMPTS = 3 for the same blocker/root-cause class.

After attempt 3 fails:
- STOP editing.
- Do not create v4/v5/vN retry scripts.
- Produce a blocker report with exact traceback, root-cause hypothesis, files touched, changes attempted, and why further work requires an architecture/user decision.
- Set `MOVE_FORWARD_READY: NO`.

A materially different blocker discovered after a prior blocker is fixed is a new blocker, but it still receives its own maximum of 3 focused attempts.

## Mandatory hard gate
Before reporting success run:

`python3 tools/clinic_staff_guardrail.py`

The command MUST exit 0.

Runtime success may only be claimed with real Odoo evidence for:
1. install/upgrade on target environment
2. repeat upgrade
3. registry load
4. basic clinic_staff smoke

Static PASS is never equivalent to runtime PASS.

## Definition of Done
Success requires all of:
- baseline contract gate PASS
- Python compile PASS
- XML parse PASS
- manifest contract PASS
- legacy `_sql_constraints`: 0
- stale `name_search(... args=...)`: 0
- Python action `view_mode` containing `tree`: 0
- missing field compute/inverse/search methods: 0
- no unauthorized model/field/method/dependency drift
- target Odoo runtime gates PASS

Only then report:
`CLINIC_STAFF_MOVE_FORWARD_READY: YES`
