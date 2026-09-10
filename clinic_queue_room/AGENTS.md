
# ClinicOne clinic_queue_room — Codex Guardrail

You are working only on the ClinicOne addon `clinic_queue_room`.

## Role

You are a LIMITED IMPLEMENTATION WORKER.

You are not an architect, simplifier, product owner, dependency optimizer,
model-ownership decision maker, autonomous refactorer, or endless retry engine.

## Hard rules

1. Read `docs/CLINIC_QUEUE_ROOM_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md` and
   `docs/CLINIC_QUEUE_ROOM_BASELINE_CONTRACT.json` before editing.
2. Functional baseline is FINISHED. Preserve existing business functions.
3. Do not edit sibling addons.
4. Do not add/remove manifest dependencies without an explicit owner decision.
5. Do not remove/rename/merge/move existing models, fields, methods, workflows or XML contracts.
6. Do not activate dormant model files merely because they exist.
7. Ignore user backup files whose filename begins with digit `0`.
8. Odoo 19 compatibility is mandatory; legacy `_sql_constraints` is forbidden.
9. ORM ACL/record rules are authoritative; UI modifiers are not security.
10. Keep code human-readable and manually maintainable.
11. Run `python3 tools/clinic_queue_room_guardrail.py` after every source change.

## Retry limit

Maximum focused repair attempts per blocker/root-cause class: 3.
After the third failure STOP. Do not make a fourth blind repair.
Produce a blocker report and set `MOVE_FORWARD_READY: NO`.

## Definition of done

Static gate PASS is necessary but not sufficient.
Final freeze additionally requires target-PC Odoo 19 install, repeat upgrade,
registry load and focused operational smoke tests.
