# ClinicOne — clinic_patient Enterprise Development Guardrail

This document is the human-readable hard-gate policy for `clinic_patient`.
`AGENTS.md` is the Codex execution policy; the JSON baseline and Python validator are the machine-checkable contracts.

## Non-negotiable identity
- Project: ClinicOne
- Addon: clinic_patient
- Target: Odoo 19 Community Edition
- Target path: `/mnt/d/projects/odoo19v/clinic19a/clinic_patient`
- Functional status before hardening: FINISHED
- Review mode: preserve + harden + complete presentation/security contracts
- Backup filenames beginning with `0`: ignored

## The 15 owner hard gates
0. PROJECT IDENTITY PREFLIGHT
1. CODEX BUKAN ARCHITECT
2. EXISTING FUNCTION PRESERVATION
3. ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
4. FULL STRUCTURAL INVENTORY
5. HUMAN-FRIENDLY CODING STRUCTURE
6. PROFESSIONAL FORM DESIGN
7. UI/UX MATRIX PER MODEL
8. SEARCH VIEW WAJIB
9. LIST VIEW ENTERPRISE QUALITY
10. SECURITY TIDAK BOLEH DIKALAHKAN UI
12. CODE STYLE HUMAN FRIENDLY
13. COMMENTS YANG BERGUNA
14. CODEX RETRY LIMIT
15. ENTERPRISE COMPLETENESS MATRIX

The omission of Gate 11 is intentional because this guardrail preserves the owner's numbering exactly.

## Allowed change classes
### A. Odoo 19 compatibility
- `_sql_constraints` → `models.Constraint`
- `_name_search` compatibility → Odoo 19 `name_search`
- legacy action `tree` view type → `list`
- display label compatibility through `_compute_display_name`

### B. Existing-code completion
Allowed only when active source already calls/requires the artifact:
- patient sequence called from `create()`
- stage records consumed by default/register/deceased logic
- patient-card report called by `action_print_patient_card()`

### C. Enterprise presentation/security completion
- ACLs and company record rules
- Search/List/Form coverage
- professional forms
- buttons calling existing methods
- one presentation-only `action_open_contact()` helper for existing `partner_id`

## Explicit prohibitions
No model/field/workflow deletion, dependency redesign, sibling-addon changes, Core247 coupling, role architecture invention, public/portal exposure, or retry loops beyond three focused attempts.

## Security position
The old scaffold ACL was unloaded and did not secure the real patient models. The hardened addon uses `base.group_user` because the source baseline contains no ClinicOne patient-specific role architecture. Company-scoped medical records are additionally restricted by ORM record rules. A future dedicated clinical role model is an architecture decision and is outside this hardening task.

## Runtime freeze criteria
Only set `CLINIC_PATIENT_MOVE_FORWARD_READY: YES` after:
1. static guardrail PASS,
2. fresh install or install on the target Odoo 19 environment,
3. first upgrade PASS,
4. repeat upgrade PASS,
5. registry load PASS,
6. patient create/register/print-card smoke PASS,
7. identifier/allergy/condition/vital smoke PASS,
8. multi-company record-rule smoke PASS,
9. no critical traceback attributable to `clinic_patient`.

Until then, static readiness only.
