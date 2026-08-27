# ClinicOne — `clinic_treatment_catalog` Enterprise Development Guardrail

## HARD GATE status
This file is normative. It is not advisory.

### HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
- PROJECT: ClinicOne
- ADDON: `clinic_treatment_catalog`
- PLATFORM: Odoo 19 Community Edition
- AUTHORITATIVE BASELINE: finished/active notebook implementation from the supplied ClinicOne source dump
- PRESERVATION RULE: no functional loss
- ALLOWED CHANGE: Odoo 19 compatibility, real blocker repair, enterprise presentation/security completeness, human-readable organization
- FORBIDDEN CHANGE: redesign, simplification, ownership change, sibling-addon edits, Core247 integration, dormant integration activation
- CURRENT VERIFIED STATUS: functional baseline FINISHED; PC runtime pending for this hardened package

### HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex role is `LIMITED_IMPLEMENTATION_WORKER`. Architecture decisions require an explicit approved contract.

### HARD GATE 2 — EXISTING FUNCTION PRESERVATION
Baseline models, fields, methods, source files, and active import closure are contract data. They may be hardened, not silently removed/renamed/merged.

### HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Compile/install/test PASS is necessary but insufficient. Security, navigation, model coverage, professional forms, operational actions, search/list quality, data contracts, and usability must also be reviewed.

### HARD GATE 4 — FULL STRUCTURAL INVENTORY
Maintain `docs/CLINIC_TREATMENT_CATALOG_STRUCTURAL_INVENTORY.md`.

### HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Keep business domains separated by readable files. Do not collapse code into generated monoliths.

### HARD GATE 6 — PROFESSIONAL FORM DESIGN
Forms must expose the finished business capability coherently. Do not invent a workflow state solely for presentation.

### HARD GATE 7 — UI/UX MATRIX PER MODEL
Every persistent business model must appear in the UI/UX matrix.

### HARD GATE 8 — SEARCH VIEW WAJIB
Every persistent custom model requires a useful Search view.

### HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Every persistent custom model requires decision-useful columns, not placeholder lists.

### HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
`invisible`, menus, tabs, buttons, and statusbars are not authorization. ORM ACLs and record rules are mandatory.

### HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Prefer explicit helpers, short methods, clear sectioning, and stable public APIs over clever abstraction.

### HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain business intent, compatibility rationale, and preservation boundaries. Do not narrate obvious Python syntax.

### HARD GATE 14 — CODEX RETRY LIMIT
Maximum **3 focused repair attempts per blocker/root-cause class**. After attempt 3: STOP. Emit `MOVE_FORWARD_READY: NO` with failing gate, traceback, root cause, files changed, attempt history, and the architectural/product decision needed. No V4/V11/V17 retry treadmill.

### HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
Maintain `docs/CLINIC_TREATMENT_CATALOG_ENTERPRISE_COMPLETENESS_MATRIX.md` and do not call the addon final solely because tests passed.

## Authorized hardening delta
`clinic_patient` is added to the manifest dependency closure because active existing consent code already reads/searches `clinic.patient` and uses `patient_id`. This is dependency-contract repair, not a new clinical architecture.

## Dormant source rule
Optional engines and bridges that are commented out in `__init__.py` stay dormant. Codex must not activate them while fixing this addon unless a separate architecture decision authorizes it.

## Required static command
```bash
python3 tools/clinic_treatment_catalog_guardrail.py
```

## Final runtime gate
Static PASS never substitutes for target-PC Odoo 19 fresh install/upgrade/repeat-upgrade + functional/security smoke.

