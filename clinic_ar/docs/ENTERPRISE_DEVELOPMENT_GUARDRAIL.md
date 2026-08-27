# ClinicOne `clinic_ar` — Enterprise Development Guardrail

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0
- PROJECT: ClinicOne
- ADDON: `clinic_ar`
- PLATFORM: Odoo 19 Community Edition
- AUTHORITATIVE BASELINE: latest user-supplied ClinicOne snapshot, numeric-prefix backup files excluded
- PRESERVATION RULE: retain meaningful baseline AR capabilities; scaffold-only artifacts may be rejected with reason
- ALLOWED CHANGE: Odoo 19 hardening, actual model-owner correction, enterprise UI/security, accounting correctness, traceability, statements/outbox, tests/docs
- FORBIDDEN CHANGE: silent feature deletion, downstream dependency cycles, duplicate legal accounting, swallowed accounting errors
- CURRENT VERIFIED STATUS: source/static validation only until Windows runtime install succeeds

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex is a bounded implementation worker. It may implement a proven repair but may not redesign ownership or simplify scope.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
Preserve AR invoice, invoice lines, receipts, allocations, partner credit controls, follow-up/dunning and accounting bridge. Scaffold controllers/demo/views with no active business function are rejected with reason.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Passing compilation/tests does not equal enterprise completion. Accounting authority, lifecycle, traceability, security, usable UI and downstream contract must all be present.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
Inventory manifest, models, fields, methods, constraints, data, security, menus, views, tests, docs and sibling-addon contracts before release.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
One domain per model file where practical; explicit names; readable workflow methods; no opaque metaprogramming for core finance logic.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Lifecycle forms use statusbars, meaningful headers, smart buttons, traceability sections, totals and chatter where appropriate.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
Every persistent AR owner model must have Search/List/Form definitions, including child ledger models.

## HARD GATE 8 — SEARCH VIEW WAJIB
Every persistent model has a Search View; every Odoo 19 `<filter>` has technical `name`; legacy search-group attributes are forbidden.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Lists expose identifiers, owner/context, amount/status and operational cues; use badges, totals and decorations where meaningful.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
Readonly/invisible is not security. ACL, record rules and ORM lifecycle restrictions remain authoritative for RPC/import.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Readable Python/XML, meaningful method names, limited nesting and standard Odoo patterns.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain ownership, accounting safety or non-obvious trade-offs; no noisy line-by-line narration.

## HARD GATE 14 — CODEX RETRY LIMIT
Maximum 2 bounded attempts and maximum 1 repetition of the same root cause. Then stop and return to root-cause/architecture review.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
Release requires: preservation PASS, ownership PASS, dependency PASS, Odoo 19 SQL/security/search compatibility PASS, 10/10 UI matrix PASS, multi-company security PASS, accounting strictness PASS, static guardrail PASS. Runtime remains pending until user activates on Windows Odoo.



## Odoo 19 Currency Contract
Direct Many2one fields to `res.currency` must not use `check_company=True`, because `res.currency` has no `company_id` field in Odoo 19.

## Runtime Repair Gate — Cross-Addon Form Decoration

`clinic_ar` MUST NOT hard-inherit `clinic_billing` form views through load-time XML
when the XPath depends on optional presentation anchors such as `button_box`.
Billing business/model dependencies remain mandatory, but AR Smart Buttons are
installed through an idempotent runtime bridge with savepoint-isolated fallback
architectures. Missing or structurally changed parent views must never abort the
AR accounting subledger installation.
