# AGENTS.md — clinic_encounter

## Role
CODEX_ROLE = LIMITED IMPLEMENTATION WORKER

Codex is:
- NOT ARCHITECT
- NOT SIMPLIFIER
- NOT PRODUCT OWNER
- NOT MODEL-OWNERSHIP DECISION MAKER
- NOT DEPENDENCY OPTIMIZER
- NOT AUTONOMOUS REFACTORER
- NOT ENDLESS RETRY ENGINE

## Mandatory preflight
Before any edit, confirm: PROJECT=ClinicOne, ADDON=clinic_encounter, AUTHORITATIVE_BASELINE, PRESERVATION_RULE, ALLOWED_CHANGE, FORBIDDEN_CHANGE, CURRENT_VERIFIED_STATUS.

## Preservation
Do not delete/simplify/move baseline models, fields, methods, workflow states, views or dependencies merely to pass tests.
Do not import `models/xxx_clinic_encounter.py`.
Do not edit frozen sibling addons.
`clinic.consent.template` must remain a same-name extension of the canonical upstream model and must not redeclare its canonical identity fields.

## Odoo 19
Use `models.Constraint`, `_compute_display_name`, `name_search(..., domain=None, ...)`, `<list>`, `_read_group()` where applicable, and current Stock action IDs.

## Runtime repair discipline
MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3
After 3 failed attempts for one root-cause class: STOP and report `MOVE_FORWARD_READY: NO`. Do not continue V4/V5/V6 traceback patch loops.

## Mandatory validation
Run:
`python3 tools/clinic_encounter_guardrail.py`

A static PASS does not authorize claiming runtime/final completion.

