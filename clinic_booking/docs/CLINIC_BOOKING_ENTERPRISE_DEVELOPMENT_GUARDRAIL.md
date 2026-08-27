# ClinicOne — clinic_booking Enterprise Development Guardrail

## HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
- PROJECT: ClinicOne
- ADDON: clinic_booking
- TARGET: `/mnt/d/projects/odoo19v/clinic19a/clinic_booking`
- AUTHORITATIVE BASELINE: uploaded active `clinic_booking` source; filename prefix `0` means user backup and is excluded.
- FUNCTIONAL STATUS: FINISHED baseline; do not redesign from zero.
- ALLOWED CHANGE: Odoo 19 CE hardening, compatibility, necessary enterprise UI/security completion, bounded defect repair.
- FORBIDDEN CHANGE: silent scope/model/field/method/dependency/ownership reduction or redesign.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex is `LIMITED_IMPLEMENTATION_WORKER`. It may implement an already-defined repair. It may not decide product architecture, simplify business scope, merge/remove models, or optimize dependencies on its own.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
Every baseline source file, active model, field, and method is a preservation contract. Additions are allowed only when required for Odoo 19 compatibility, usability, security, or a concrete existing contract.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Static/runtime tests are gates, not proof that the module is commercially complete. UI, security, workflow usability, model coverage, and functional smoke must also pass.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
`docs/CLINIC_BOOKING_STRUCTURAL_INVENTORY.md` must exist and remain aligned with baseline preservation.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Keep domain logic in readable model files. Split view files by domain. Avoid generated mega-files when a human-maintainable split is possible.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
The primary booking form must expose workflow actions, statusbar, scheduling/clinical grouping, lines, deposits, integration links, notes, and chatter without bypassing ORM rules.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
Every persistent custom model must be accounted for in `CLINIC_BOOKING_UI_UX_MATRIX.md`. Supporting child models may be relationally accessed, but still require Search/List/Form definitions.

## HARD GATE 8 — SEARCH VIEW WAJIB
Every persistent custom model requires a search view. Search domains may only use searchable fields.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Every persistent custom model requires a meaningful list view with identity/context fields appropriate to the model.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
Menus, invisible modifiers, readonly fields, and buttons are not security. ACL and record rules are authoritative. No public/portal ACL is added unless explicitly designed.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Prefer clear sections, descriptive helper names, shallow control flow where reasonable, and code a maintainer can edit manually.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain business intent, Odoo-version compatibility, or non-obvious safeguards. Avoid noisy comments that merely repeat code.

## HARD GATE 14 — CODEX RETRY LIMIT
Maximum focused repair attempts per blocker/root-cause class: **3**.
After attempt 3 fails: **STOP**. Emit `MOVE_FORWARD_READY: NO` with failing gate, traceback, root cause, files changed, attempt history, and the decision required. Do not create endless V4/V7/V11 repair loops.
A root-cause audit may be requested after the stop, but it is a new bounded task, not continuation of blind retry.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
`docs/CLINIC_BOOKING_ENTERPRISE_COMPLETENESS_MATRIX.md` must be maintained. Runtime and functional rows remain PENDING until real Odoo evidence exists.

## Mandatory local gate
Run:

`python3 tools/clinic_booking_guardrail.py`

A PASS permits runtime testing. It does **not** declare final completion.
