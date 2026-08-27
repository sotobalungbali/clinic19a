# AGENTS.md — ClinicOne clinic_treatment_catalog HARD GATE

## ROLE
`CODEX_ROLE = LIMITED_IMPLEMENTATION_WORKER`

Codex is NOT:
- an architect
- a simplifier
- a product owner
- an autonomous refactorer
- a model ownership decision maker
- a dependency optimizer
- an endless retry engine

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0
Before edits, print/verify: PROJECT=ClinicOne; ADDON=clinic_treatment_catalog; PLATFORM=Odoo19CE; BASELINE=FINISHED; CHANGE_MODE=TECHNICAL_HARDENING_ONLY.
If any identity item differs, STOP.

## PRESERVATION
Read `docs/CLINIC_TREATMENT_CATALOG_BASELINE_CONTRACT.json` before editing.
Do not remove/rename/merge baseline models, fields, methods, files, workflow states, actions, or active imports.
Do not modify sibling addons.
Do not integrate Core247 here.
Do not activate dormant engines/bridges.
Do not change dependencies except the already-authorized `clinic_patient` repair recorded in the contract.
Files beginning with digit `0` are user backups and must be ignored.

## 15 OWNER HARD GATES
HARD_GATE_0_PROJECT_IDENTITY_PREFLIGHT
HARD_GATE_1_CODEX_BUKAN_ARCHITECT
HARD_GATE_2_EXISTING_FUNCTION_PRESERVATION
HARD_GATE_3_ENTERPRISE_COMPLETENESS
HARD_GATE_4_FULL_STRUCTURAL_INVENTORY
HARD_GATE_5_HUMAN_FRIENDLY_CODING_STRUCTURE
HARD_GATE_6_PROFESSIONAL_FORM_DESIGN
HARD_GATE_7_UI_UX_MATRIX_PER_MODEL
HARD_GATE_8_SEARCH_VIEW_WAJIB
HARD_GATE_9_LIST_VIEW_ENTERPRISE_QUALITY
HARD_GATE_10_SECURITY_OVER_UI
HARD_GATE_12_CODE_STYLE_HUMAN_FRIENDLY
HARD_GATE_13_USEFUL_COMMENTS
HARD_GATE_14_CODEX_RETRY_LIMIT
HARD_GATE_15_ENTERPRISE_COMPLETENESS_MATRIX

## RETRY LIMIT
`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3`
After three failed attempts on the same blocker/root-cause class: STOP and emit a blocker report with `MOVE_FORWARD_READY: NO`.

## REQUIRED CHECK
Run:
`python3 tools/clinic_treatment_catalog_guardrail.py`

A static PASS means only `CLINIC_TREATMENT_CATALOG_STATIC_MOVE_FORWARD_READY: YES`. Final move-forward requires Odoo 19 runtime gates on the target PC.

