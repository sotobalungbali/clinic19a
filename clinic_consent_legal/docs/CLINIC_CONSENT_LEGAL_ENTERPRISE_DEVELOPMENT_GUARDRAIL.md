# ClinicOne — clinic_consent_legal Enterprise Development Guardrail

This document is a hard-gate contract, not advisory prose.

## HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
Project ClinicOne, addon clinic_consent_legal, Odoo 19 CE, finished functional baseline, backup files beginning with `0` excluded, exact manifest dependency contract preserved.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex is a bounded implementation worker only. Ownership, dependency, scope, preservation and enterprise acceptance criteria are owner decisions.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
No baseline model/field/method/workflow may disappear merely to achieve technical PASS. Dormant files remain dormant. Frozen sibling addons are not edited.

Special reconciliation: `clinic.consent.template` is canonical in frozen `clinic_treatment_catalog`. clinic_consent_legal extends it in place. Canonical `name` remains Template Name; legal numbering uses `legal_reference`; legal-only validation applies only to `legal_governed` templates.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Static compile/XML/test success is necessary but insufficient. Legal lifecycle, evidence integrity, portal safety, auditability, multi-company security, cross-addon operational behavior and professional UI must remain coherent.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
The complete active model/import/field/method/view/action/security inventory is documented in `CLINIC_CONSENT_LEGAL_STRUCTURAL_INVENTORY.md` and machine checked against the baseline contract.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Domain files remain separated: template, consent form, signatures, attachments, sibling integrations, controllers, hooks, security, views and documentation.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Core legal surfaces use meaningful headers, statusbars, smart buttons, notebook sections, evidence ledgers and contextual actions. UI must expose real server methods only.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
All user-facing legal models have explicit Search/List/Form coverage. Canonical sibling forms are extended defensively at post-init rather than hard-linked through fragile presentation XML IDs.

## HARD GATE 8 — SEARCH VIEW WAJIB
Search views are required for all four user-facing legal surfaces.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Lists use Odoo 19 `<list>`, meaningful operational columns, decorations where useful, and no legacy `<tree>` architecture in active XML.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
ACLs and record rules are authoritative. Public/Portal receive no direct ORM ACL. Portal document access uses Odoo portal access checks and read-only routes.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Clear naming, domain-oriented modules, bounded helpers, no generator-style monolith in the active import graph.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain ownership reconciliation, legal invariants, compatibility decisions and security boundaries; they do not narrate obvious syntax.

## HARD GATE 14 — CODEX RETRY LIMIT
`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_ROOT_CAUSE = 3`. After attempt three, STOP and report evidence. No endless V1/V2/V3/V4 repair loop.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
`CLINIC_CONSENT_LEGAL_ENTERPRISE_COMPLETENESS_MATRIX.md` must be complete and PASS before source is marked static move-forward ready.

## Runtime truth
Static PASS may only produce `CLINIC_CONSENT_LEGAL_STATIC_MOVE_FORWARD_READY: YES`. Final freeze requires real target-PC Odoo 19 install/upgrade success.
