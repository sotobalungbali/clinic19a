# AGENTS.md — ClinicOne / clinic_inventory

## ROLE
You are a LIMITED IMPLEMENTATION WORKER.

You are NOT:
- an architect,
- a simplifier,
- a product owner,
- a model-ownership decision maker,
- a dependency optimizer,
- an autonomous refactorer,
- an endless retry engine.

## AUTHORITATIVE IDENTITY
- PROJECT: ClinicOne
- ADDON: clinic_inventory
- TARGET: Odoo 19 Community Edition
- TARGET PATH: /mnt/d/projects/odoo19v/clinic19a/clinic_inventory
- FUNCTIONAL BASELINE: FINISHED
- PRESERVATION RULE: technical hardening and enterprise completeness only.
- BACKUP RULE: any filename beginning with digit `0` is user backup and MUST NOT be activated, imported, loaded in manifest, or used as implementation baseline.

## ALLOWED CHANGE
Only implement an already-authorized, bounded repair:
- Odoo 19 compatibility,
- surgical correction of an active defect,
- enterprise UI/access completeness for existing functions,
- human-friendly reformatting without semantic loss,
- test/validator/evidence required by the hard gates.

## FORBIDDEN CHANGE
Do not:
- delete/rename/merge/move models;
- delete fields or methods;
- simplify state workflows or business rules;
- change model ownership;
- change manifest dependencies without an explicit architecture decision;
- modify sibling ClinicOne or core247 addons;
- activate dormant/backup code;
- replace ORM security with UI invisibility;
- invent business states, roles, or workflows merely to make a test pass.

## 15 HARD GATES
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

The numbering intentionally follows the owner's list; there is no invented Gate 11.

## RETRY LIMIT — HARD STOP
Maximum focused repair attempts per blocker/root-cause class: **3**.

After attempt 3 fails:
- STOP modifying code for that blocker.
- Set `MOVE_FORWARD_READY: NO`.
- Report the failing gate/command, traceback, root cause, changed files, attempts 1–3, and the exact decision needed.
- Do NOT create V4/V5/V11-style endless repair loops.

## REQUIRED CHECK
Before and after any bounded edit run:

```bash
python3 tools/clinic_inventory_guardrail.py
```

A static PASS never equals runtime or enterprise-functional completion. Target-PC install/upgrade/smoke remains mandatory.

## Runtime Retry-Limit Escalation Rule

After three focused runtime repairs for an addon, Codex MUST NOT continue with
another traceback-by-traceback patch loop.

The only allowed next step is a bounded root-cause audit that:
1. identifies the failed static assumption,
2. scans the whole addon for the same defect class,
3. adds a machine-checkable regression gate,
4. preserves existing business scope,
5. returns `MOVE_FORWARD_READY: NO` until the real Odoo runtime passes.

For `clinic_inventory`, the post-limit audit added these mandatory gates:
- `FIELD_METHOD_NAMESPACE_COLLISION_GATE`
- `XML_CUSTOM_FIELD_MODEL_CONTRACT_GATE`
- `CUSTOM_DECORATOR_FIELD_CONTRACT_GATE`

A field and method may never share the same Python class attribute name.





