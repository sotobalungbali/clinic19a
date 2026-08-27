# ClinicOne / clinic_patient — Enterprise Development Guardrail

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0
- Project: ClinicOne.
- Addon: `clinic_patient`.
- Target runtime path: `/mnt/d/projects/odoo19v/clinic19a/clinic_patient`.
- Target platform: Odoo 19 Community Edition.
- `clinic_patient` is addon #4 and its business functionality is already accepted as FINISHED.
- Files whose filename begins with digit `0` are user backup files. Ignore them completely as implementation input.
- Before editing, verify the task is for this addon. Do not edit sibling addons.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex role is **LIMITED_IMPLEMENTATION_WORKER**.

Codex is NOT:
- an architect,
- a simplifier,
- a product owner,
- an autonomous refactorer,
- a dependency optimizer,
- a model-ownership decision maker,
- an endless retry engine.

Codex may implement only:
1. an explicitly identified Odoo 19 compatibility fix,
2. an explicitly identified runtime blocker,
3. the enterprise-completeness items already authorized by this guardrail.

Architecture/dependency/ownership decisions require explicit user authorization.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
The existing addon is the functional baseline.
Forbidden without explicit user approval:
- remove/rename/merge a model,
- remove/rename a field,
- remove existing business behavior,
- remove a method except an explicitly authorized Odoo API migration,
- simplify a workflow,
- change model ownership,
- edit a sibling addon,
- change the manifest dependency set,
- introduce Core247 coupling.

Read `docs/CLINIC_PATIENT_BASELINE_CONTRACT.json` before implementation.
The current source must remain a superset of that baseline, subject only to the documented API migrations.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Passing Python/XML parsing is insufficient.
The addon must also have:
- usable security,
- seed/config data required by existing code paths,
- complete Search/List/Form UX for all 16 custom persistent models,
- professional patient form,
- existing action methods exposed where useful,
- the patient-card report already referenced by existing code,
- runtime install/upgrade/security/workflow smoke on target PC.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
`docs/CLINIC_PATIENT_STRUCTURAL_INVENTORY.md` is mandatory and must remain aligned with the baseline contract.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Keep code organized by business responsibility:
- patient core,
- identifiers,
- allergies,
- conditions,
- vitals,
- canonical Odoo model extensions,
- security,
- data,
- reports,
- views split by model/domain.

Do not collapse large files or generate opaque metaprogramming merely to reduce line count.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
The main patient form must visibly provide:
- header workflow/action area,
- statusbar,
- sheet and title,
- useful smart/body buttons,
- grouped identity/status information,
- notebook-based related medical information,
- chatter,
- clear labels and manually editable XML.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
Every one of the 16 custom persistent models must have explicit Search/List/Form coverage.
See `docs/CLINIC_PATIENT_UI_UX_MATRIX.md`.

## HARD GATE 8 — SEARCH VIEW WAJIB
Every custom persistent model requires a Search view with useful fields and filters/grouping where materially useful.
Do not create placeholder-empty searches.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Every custom persistent model requires a List view.
Use Odoo 19 `<list>`, not legacy `<tree>`.
List views should expose decision-useful fields, optional columns, decorations, and safe object buttons where appropriate.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
UI invisibility is not security.
- ACLs must cover all 16 custom persistent models.
- Company-scoped clinical records must have ORM record rules.
- Do not grant public or portal access merely to make a view/button work.
- Do not use `sudo()` to bypass an access error unless the task explicitly authorizes and justifies it.
- Do not weaken record rules to make tests pass.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Prefer:
- explicit names,
- short purposeful helpers,
- one responsibility per method,
- normal Odoo patterns,
- readable XML broken into domain files,
- predictable formatting.

Avoid clever compression, code generation inside production code, broad catch-all exception handling, and unnecessary abstraction.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments should explain:
- why a compatibility bridge exists,
- why an optional integration is guarded,
- why a security rule exists,
- why a preserved legacy behavior must remain.

Do not add comments that merely repeat the code.

## HARD GATE 14 — CODEX RETRY LIMIT
Maximum focused repair attempts per blocker/root-cause class: **3**.

After attempt 3 fails:
- STOP.
- Do not create V4/V5/V11-style retry chains.
- Set `MOVE_FORWARD_READY: NO`.
- Emit a blocker report with:
  - exact failing command/gate,
  - traceback/error,
  - root-cause hypothesis,
  - files changed,
  - attempts already made,
  - why further work requires a new decision.

A new attempt is permitted only after a materially new root cause or explicit user direction.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
`docs/CLINIC_PATIENT_ENTERPRISE_COMPLETENESS_MATRIX.md` is mandatory.
Static readiness is not final readiness.
Final freeze requires target-PC runtime gates.

## Mandatory static command
Run from addon root:

```bash
python3 tools/clinic_patient_guardrail.py
```

Required marker before runtime testing:

`CLINIC_PATIENT_STATIC_MOVE_FORWARD_READY: YES`

Never claim final readiness until target-PC runtime passes.
