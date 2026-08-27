# ClinicOne clinic_room_device — AGENTS.md

## Project identity
- PROJECT: ClinicOne
- ADDON: clinic_room_device
- TARGET: Odoo 19 Community Edition
- TARGET PATH: /mnt/d/projects/odoo19v/clinic19a/clinic_room_device
- FUNCTIONAL BASELINE: FINISHED
- CHANGE POLICY: Odoo 19 technical hardening + enterprise completeness only
- BACKUP RULE: ignore every filename beginning with digit `0`

## Codex role
Codex is a LIMITED IMPLEMENTATION WORKER.

Codex is NOT:
- an architect;
- a simplifier;
- a product owner;
- a model-ownership decision maker;
- a dependency optimizer;
- an autonomous refactorer;
- an endless retry engine.

Codex must preserve existing models, fields, methods, workflows, ownership, and manifest dependencies unless the user explicitly authorizes a change.

## Dormant source
`models/inherit` is preserved but is NOT imported by `models/__init__.py`.
Do not activate that package unless the user explicitly authorizes it.

## Hard gates
The 15 owner hard gates are mandatory:
0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15.
Hard Gate 11 is intentionally absent because the owner numbering skips it.

## Retry limit
Maximum focused repair attempts per blocker/root-cause class: 3.
After the third failure STOP.
Do not create an endless V4/V5/V11/V20 retry chain.
Report the failing gate, command, traceback, root cause, files changed, attempts already made, and the decision required.

## Required validator
Before claiming source-ready, run:

    python3 tools/clinic_room_device_guardrail.py

Do not claim runtime-ready until the target Windows Odoo 19 installation/upgrade has passed.
