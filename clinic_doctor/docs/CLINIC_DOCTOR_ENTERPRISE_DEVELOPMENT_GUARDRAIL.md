
# ClinicOne Enterprise Development Guardrail — clinic_doctor

## 1. HARD GATE STATUS
This document is normative for all work on `clinic_doctor`. It is not a suggestion.

## 2. Project Identity Preflight
- PROJECT: ClinicOne
- ADDON: clinic_doctor
- TARGET: Odoo 19 Community Edition
- TARGET PATH: `/mnt/d/projects/odoo19v/clinic19a/clinic_doctor`
- AUTHORITATIVE BASELINE: active files from the user-provided ClinicOne source dump
- BACKUP RULE: every filename beginning with digit `0` is excluded from the implementation baseline
- FUNCTIONAL STATUS: FINISHED
- UPSTREAM FROZEN: `clinic_base`, `clinic_staff`
- REVIEW MODE: TECHNICAL_HARDENING_ONLY

If any of those facts is contradicted by a future task, Codex must STOP rather than silently reinterpret the project.

## 3. Preservation Rule
The addon is not a greenfield redesign. Existing business functionality is presumed accepted.
No implementation worker may remove, rename, merge, split, relocate, or simplify models, fields, methods, states, actions, or business workflows merely to achieve static/runtime PASS.

## 4. Allowed Changes
Only:
- Odoo 19 API compatibility repairs;
- migration of legacy `_sql_constraints` to `models.Constraint`;
- correction of manifest dependencies required by already-active fields;
- surgical repair of an active reference to a missing/commented field or method where intent is explicit in the existing source;
- defensive guards for explicitly optional downstream integrations;
- exact blocker fixes demonstrated by runtime traceback/evidence;
- tests/validators/evidence that do not change business scope.

## 5. Forbidden Changes
Without explicit user architecture decision:
- no new architecture;
- no simplification;
- no model ownership move;
- no ClinicOne dependency removal/reordering;
- no activation of dormant/commented integration modules;
- no sibling-addon changes;
- no core247 integration;
- no broad refactor;
- no feature deletion;
- no endless retries.

## 6. Codex Role
`LIMITED_IMPLEMENTATION_WORKER`.

Codex is NOT:
- architect;
- simplifier;
- product owner;
- autonomous refactorer;
- dependency optimizer;
- retry engine.

Codex implements an already-bounded technical decision and proves it with evidence.

## 7. Retry Circuit Breaker
Maximum focused attempts per blocker/root-cause class: **3**.

Each attempt must:
1. state a distinct root-cause hypothesis;
2. make the smallest bounded change that tests that hypothesis;
3. run the hard gate;
4. run the relevant Odoo runtime test;
5. retain evidence.

After attempt 3 fails:
- STOP;
- `MOVE_FORWARD_READY: NO`;
- provide traceback, root cause, touched files, attempts 1–3, and the specific architecture decision required.
A renamed script/version is not a new attempt.

## 8. Authorized clinic_doctor Hardening
This hardening is bounded to:
- 7 legacy SQL constraints migrated to Odoo 19 `models.Constraint`;
- Odoo 19 display-name/name-search compatibility;
- Python window actions migrated from `tree` to `list`;
- `clinic.appointment.patient_id` restored from its existing commented declaration because active code already uses it and `clinic_patient` is already a hard dependency;
- optional `treatment_session_id` dereference guarded so an absent downstream field cannot crash the base addon;
- primary-patient action guarded when the optional patient-side `primary_doctor_id` extension is absent;
- specialty doctor action made independent of optional `hr.employee` extension fields;
- `account` and `sale` added because active fields hard-reference `account.move` and `sale.order`.

No existing ClinicOne dependency was removed.

## 9. Hard-Gate Commands
From addon root:

```bash
python3 tools/clinic_doctor_guardrail.py
```

This gate must PASS before and after any Codex change.

Runtime gates on the target PC remain separate:
- fresh install / actual install as applicable;
- first upgrade;
- repeat upgrade;
- registry load;
- focused doctor/specialty/schedule/availability/leave/appointment smoke.

Static PASS is never equivalent to runtime or enterprise-functional completion.

## 10. Freeze Rule
Only after static + runtime + smoke PASS:
`CLINIC_DOCTOR_MOVE_FORWARD_READY: YES`

Then freeze the addon. Downstream addons must extend it rather than casually reopen it.

