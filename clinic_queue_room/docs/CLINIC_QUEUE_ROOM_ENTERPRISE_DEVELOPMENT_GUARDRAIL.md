
# ClinicOne — clinic_queue_room Enterprise Development Guardrail

## Project Identity Preflight — Hard Gate 0

- PROJECT: ClinicOne
- ADDON: `clinic_queue_room`
- TARGET: Odoo 19 Community Edition
- TARGET PATH: `/mnt/d/projects/odoo19v/clinic19a/clinic_queue_room`
- AUTHORITATIVE BASELINE: owner-supplied active ClinicOne source
- FUNCTIONAL STATUS: FINISHED
- PRESERVATION RULE: preserve existing models, fields, methods and workflows
- ALLOWED CHANGE: Odoo 19 compatibility, real defect repair, enterprise UI/security completeness, guardrail/testing support
- FORBIDDEN CHANGE: redesign, simplification, model ownership migration, dependency redesign, sibling-addon edits, activation of dormant integrations
- BACKUP RULE: filenames beginning with `0` are excluded

## Codex Role — Hard Gate 1

Codex is a **LIMITED IMPLEMENTATION WORKER**.

Codex is NOT:
- an architect;
- a simplifier;
- a product owner;
- a model-ownership decision maker;
- a dependency optimizer;
- an autonomous refactorer;
- an endless retry engine.

## Retry limit — Hard Gate 14

Maximum focused repair attempts for one blocker/root-cause class: **3**.

After attempt 3 fails, Codex MUST STOP and emit:
- failing gate and command;
- complete traceback;
- root cause hypothesis and evidence;
- files changed in each attempt;
- why another retry would be unbounded;
- `MOVE_FORWARD_READY: NO`.

No V4/V7/V11-style blind retry loop is permitted.

## Preservation and completeness

The machine-checkable baseline contract and validator are authoritative for:
- source-file and active-import preservation;
- model/field/method preservation;
- Odoo 19 constraint/API checks;
- view/model/button/search contracts;
- ACL and record-rule coverage;
- Search/List/Form completeness;
- local XML-ID references;
- manifest file references.

Runtime PASS is still required before final freeze.
