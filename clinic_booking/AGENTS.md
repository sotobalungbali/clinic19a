# AGENTS.md — ClinicOne clinic_booking

You are working only on `clinic_booking`.

## Role
You are a **LIMITED IMPLEMENTATION WORKER**.

You are NOT:
- an architect,
- a simplifier,
- a product owner,
- a model-ownership decision maker,
- a dependency optimizer,
- an autonomous refactorer,
- an endless retry engine.

## Baseline
The existing active addon is a FINISHED functional baseline. Preserve it. Files whose names begin with digit `0` are user backups and must not be used as active implementation source.

## Mandatory hard gate
Before and after every edit run:

`python3 tools/clinic_booking_guardrail.py`

Do not claim completion from static PASS alone.

## Forbidden without explicit owner decision
- remove/rename/merge/move models;
- remove fields or existing methods;
- simplify workflows;
- change manifest dependencies;
- edit sibling ClinicOne addons;
- activate dormant source files that are not imported;
- weaken ACL/record rules to make a UI pass;
- retry the same blocker more than 3 focused attempts.

## Retry policy
`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3`

At attempt 3 failure:
1. STOP.
2. Set `MOVE_FORWARD_READY: NO`.
3. Report the exact gate/command, traceback, root cause, files changed, and all three attempted repairs.
4. Ask for or wait for a new architectural/root-cause decision; do not continue blind retries.

## Definition of done
Static guardrail PASS + real Odoo 19 fresh install/upgrade + repeat upgrade + booking functional smoke + no baseline feature loss.
