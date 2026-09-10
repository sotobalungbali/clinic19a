# ClinicOne `clinic_ap` — Enterprise Development Guardrail

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0
- PROJECT: ClinicOne
- ADDON: `clinic_ap`
- PLATFORM: Odoo 19 Community Edition
- AUTHORITATIVE BASELINE: latest user-supplied ClinicOne aggregate snapshot, excluding basenames beginning with digit `0`
- PRESERVATION RULE: preserve meaningful AP capabilities and owner contracts; corrections/hardening are allowed, silent deletion is forbidden
- ALLOWED CHANGE: Odoo 19 compatibility, enterprise completion, security hardening, UI completion, ownership correction, broken-reference repair
- FORBIDDEN CHANGE: architecture simplification, model/feature deletion for test convenience, downstream dependency cycles, fake model ownership
- VERIFIED STATUS AT BUILD: source/static only; runtime install remains pending until user confirms

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex is a bounded implementation worker. Architecture, ownership, scope and acceptance criteria are fixed before implementation.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
Preserve AP header/line, vendor bill integration, payment-term policy, vendor governance, purchase/receipt integration, Billing traceability, aging, cashflow, accounting navigation and company settings.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
A green test suite does not establish enterprise completeness. Lifecycle governance, security, auditability, accounting ownership, traceability and usable UI are independently required.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
Inventory all Python models/extensions, fields, constraints, workflows, data, security, views, crons and cross-addon contracts before accepting the build.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Use focused files by business responsibility, descriptive names, short orchestration methods and explicit ownership boundaries.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Primary transaction forms require clear lifecycle controls, statusbar, totals, traceability, smart navigation, audit metadata and actionable lines.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
Every persistent owner model has Search, List and Form views: 9/9 required.

## HARD GATE 8 — SEARCH VIEW WAJIB
Every persistent owner model has a search view. Every `<filter>` has a technical `name`; Group By uses valid Odoo 19 search schema.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
List views expose decision-relevant identifiers, state, dates, amounts and drill-down actions. Use Odoo 19 `<list>` architecture.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
Readonly/invisible UI is not a security boundary. ACLs, record rules and ORM workflow guards remain authoritative for RPC/import.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Readable methods, explicit domains, clear state names, limited side effects and manually editable code are mandatory.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain ownership, compatibility and non-obvious accounting decisions. Comments must not restate trivial syntax.

## HARD GATE 14 — CODEX RETRY LIMIT
Maximum 2 bounded implementation attempts and maximum 1 repetition of the same root cause. Then STOP and perform root-cause/architecture review.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
The build must pass the maintained completeness matrix covering domain, lifecycle, accounting, procurement, inventory, Billing, vendor governance, treasury, UI, security, multi-company, Odoo 19 compatibility, tests and documentation.

