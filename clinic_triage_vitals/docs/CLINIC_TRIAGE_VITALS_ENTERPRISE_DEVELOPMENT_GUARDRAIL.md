
# ClinicOne — clinic_triage_vitals Enterprise Development Guardrail

## HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
Project: ClinicOne  
Addon: `clinic_triage_vitals`  
Authoritative baseline: user-supplied finished source, excluding filenames beginning with digit `0`.  
Allowed change: Odoo 19 technical hardening and enterprise completeness only.  
Forbidden change: redesign, simplification, ownership/dependency change, sibling-addon edits, dormant integration activation.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex is a **LIMITED IMPLEMENTATION WORKER**. It may implement an already-approved correction. It may not decide architecture, move models, redefine ownership, change dependencies, or simplify business scope.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
All baseline active models, fields, methods, lifecycle states, and active import ownership must remain present unless the user explicitly authorizes a change.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Static/runtime PASS alone is insufficient. Search/List/Form, operational actions, security, multi-company behavior, cross-model contracts, and human usability are separate gates.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
`docs/CLINIC_TRIAGE_VITALS_STRUCTURAL_INVENTORY.md` is mandatory and must remain aligned with the source.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Business models remain separated by responsibility. UI files are split by business model/domain. Do not collapse the addon into generated monoliths.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Forms must expose lifecycle, clinical context, routing, SLA, vitals, notes, and operational actions in understandable sections.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
`docs/CLINIC_TRIAGE_VITALS_UI_UX_MATRIX.md` is mandatory.

## HARD GATE 8 — SEARCH VIEW WAJIB
Every persistent custom business model requires an explicit Search view.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Lists must expose useful operational columns, optional secondary columns, and meaningful decorations where state/abnormality supports them.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
`invisible`, `readonly`, menus, and buttons are not authorization. ACLs + ORM record rules are authoritative.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Prefer explicit methods, readable field sections, descriptive identifiers, and bounded helpers over dense abstraction.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain business/compatibility decisions, especially Odoo 19 migrations and intentional dormant integrations. Avoid decorative comments that repeat the code.

## HARD GATE 14 — CODEX RETRY LIMIT
Maximum **3 focused repair attempts per blocker/root-cause class**. After the third failed attempt, Codex must STOP, set `MOVE_FORWARD_READY: NO`, and report the blocker/root cause/changed files/attempt history. No V4/V7/V20 endless loop.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
`docs/CLINIC_TRIAGE_VITALS_ENTERPRISE_COMPLETENESS_MATRIX.md` is mandatory and must report all owner gates independently.

## Dormant integration contract
`models/encounter_link.py` remains intentionally unimported. Codex may not activate it. Integration with `clinic.encounter` belongs to an explicit downstream architecture decision.

## Cross-Addon XML-ID Runtime Resilience

A sibling addon being present on disk does not prove that the installed database
contains every XML-ID from that source revision.

Therefore optional UI inheritance must not become a hard installation blocker.
For the Patient form integration, `clinic_triage_vitals` uses a defensive
`post_init_hook` and does not load the inheritance template directly from the
manifest.

Machine gate:

`CROSS_ADDON_PATIENT_VIEW_RUNTIME_RESILIENCE_GATE`

Codex is forbidden to repair this class of problem by modifying or forcibly
upgrading the frozen `clinic_patient` addon.


## Additional runtime-resilience gate

`CROSS_ADDON_XMLID_INSTALLATION_BLOCKER_GATE`

No manifest-loaded XML may hard-reference a sibling ClinicOne presentation
XML-ID that can be absent from an older installed database revision. Patient
form/menu presentation integration must use the defensive post-init contract.
