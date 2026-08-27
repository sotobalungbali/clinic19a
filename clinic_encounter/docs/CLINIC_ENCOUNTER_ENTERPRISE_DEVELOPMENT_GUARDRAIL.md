# ClinicOne — clinic_encounter Enterprise Development Guardrail

This document is a HARD GATE, not advisory prose.

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0
PROJECT: ClinicOne
ADDON: clinic_encounter
PLATFORM: Odoo 19 CE
AUTHORITATIVE BASELINE: the user-supplied finished addon in `clinic19a(20260814-031232).md`, excluding filenames beginning with digit `0`.
PRESERVATION RULE: preserve existing business depth; harden compatibility and completeness without redesign.
ALLOWED CHANGE: only the changes enumerated in `CLINIC_ENCOUNTER_BASELINE_CONTRACT.json`.
FORBIDDEN CHANGE: no simplification/removal/ownership move/frozen sibling edit.
CURRENT VERIFIED STATUS: source static gate must pass; PC runtime remains separate.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex is a LIMITED IMPLEMENTATION WORKER. It is NOT ARCHITECT, NOT SIMPLIFIER, NOT PRODUCT OWNER, NOT MODEL-OWNERSHIP DECISION MAKER, NOT DEPENDENCY OPTIMIZER, NOT AUTONOMOUS REFACTORER, and NOT ENDLESS RETRY ENGINE.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
No baseline model, business field, workflow, or method may disappear except documented Odoo 19 replacement (`name_get` → `_compute_display_name`) and the documented canonical `clinic.consent.template` ownership reconciliation.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Compile/XML parse/test PASS alone is insufficient. Validate functional contracts, actions, sequences, reports, mail, UI, security, multi-company and cross-addon resilience.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
`CLINIC_ENCOUNTER_STRUCTURAL_INVENTORY.md` is mandatory and must reflect active imports and dormant sources.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Domain files stay separated. Wizards, navigation helpers, actions, reports, menus, rules and guards remain readable and manually editable.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Primary clinical workflows require headers, statusbars where a real state exists, contextual actions, smart navigation, structured notebooks and chatter when the model has mail mixins.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
Every persistent custom model must be represented in the UI/UX matrix.

## HARD GATE 8 — SEARCH VIEW WAJIB
All 41 persistent custom models require a Search view.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
All 41 persistent custom models require Odoo 19 `<list>` views with operationally useful columns.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
ACL and record rules are authoritative. Invisible/read-only/menu hiding is never security.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Readable names, short helpers, explicit sections and domain-focused files. Do not compress business logic into generated-looking monoliths.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain compatibility, ownership, safety, invariants and why—not obvious syntax.

## HARD GATE 14 — CODEX RETRY LIMIT
MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3.
After attempt 3 for the same root-cause class: STOP, report the failing gate/command/traceback/root cause/files changed/attempt history, and set MOVE_FORWARD_READY: NO.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
`CLINIC_ENCOUNTER_ENTERPRISE_COMPLETENESS_MATRIX.md` is mandatory. Runtime must remain PENDING until a real Odoo install/upgrade passes.

## Additional machine gates learned from ClinicOne runtime failures
- field↔method namespace collision
- compute/inverse/search method existence
- decorator field roots
- One2many inverse contract
- XML model/field/object-button contract including nested One2many
- computed-field searchability
- local XML-ID/action/report/template/sequence contract
- no hard sibling presentation XML-ID in manifest-loaded XML
- current Odoo 19 stock/account external XML-ID allowlist
- no active legacy `_sql_constraints`, `name_get`, `args=None`, `.read_group(`, `tree` actions, `account.analytic.tag`, `qty_done`, `quantity_done`
- backup `0*` exclusion
