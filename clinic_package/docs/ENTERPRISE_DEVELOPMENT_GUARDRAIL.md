# ClinicOne `clinic_package` — Enterprise Development Guardrail

Authoritative baseline: ClinicOne snapshot supplied 18 Aug 2026, excluding every basename beginning with a digit `0`.

This document is a HARD GATE. A source/static PASS does not mean the addon is enterprise-complete or runtime-complete.

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0

Before any change, state all of these explicitly:

- PROJECT: ClinicOne, Odoo 19 CE.
- ADDON: `clinic_package`.
- AUTHORITATIVE BASELINE: latest user-supplied ClinicOne snapshot plus this full-corrected release.
- PRESERVATION RULE: no model, field, workflow, security, view, integration contract, audit trail, or business feature may be removed merely to obtain PASS.
- ALLOWED CHANGE: root-cause correction, Odoo 19 compatibility, enterprise completion, documented integration extension, UI/UX hardening, migration safety.
- FORBIDDEN CHANGE: silent ownership transfer, dependency reduction by feature deletion, security weakening, bypassing workflow guards, rewriting other addon owners inside this addon.
- CURRENT VERIFIED STATUS: SOURCE/STATIC PASS only until Windows Odoo runtime upgrade/install and smoke tests pass.

## HARD GATE 1 — CODEX BUKAN ARCHITECT

Codex is a bounded implementation worker. Architecture, ownership, dependencies, preservation decisions, security boundaries, UI expectations, and acceptance criteria are fixed here first. Codex may implement a named defect only.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION

Preserve treatment-package catalog, component lines, pricing, policy, reusable benefits, patient allocation, immutable entitlement snapshot, redemption ledger, voucher/batch, transfer, booking, care plan, patient/contact bridge, integration event, commercial links, and eMAR traceability.

No feature may disappear because it is inconvenient to test.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS

Completion requires source/static, runtime registry, module upgrade/install, UI load, security checks, workflow smoke, and integration smoke. Test PASS alone is insufficient.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY

Inventory must include manifest, models, wizards, security, data, views, migrations, tests, docs, tools, and all cross-addon comodel/external-ID contracts. Backup files beginning with `0` are excluded.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE

One responsibility per file where practical. Public workflow actions use clear names. Technical helpers are private and documented. Avoid anonymous metaprogramming and unnecessary indirection.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN

Primary forms must have lifecycle statusbar, meaningful action buttons, smart buttons, grouped business information, notebook separation, readonly rules aligned to lifecycle, and visible governance context.

## HARD GATE 7 — UI/UX MATRIX PER MODEL

Primary owner models require deliberate Search/List/Form coverage:

- `clinic.package`
- `clinic.package.pricing`
- `clinic.package.policy`
- `clinic.package.benefit`
- `clinic.package.allocation`
- `clinic.package.usage`
- `clinic.package.voucher`
- `clinic.package.integration.event`

Embedded/support models must still have usable One2many forms/lists or technical navigation where relevant.

## HARD GATE 8 — SEARCH VIEW WAJIB

Every primary owner model above must have an explicit search view with business search fields plus state/group filters appropriate to its domain.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY

Lists must expose business identity, lifecycle state, operational context, optional secondary fields, badges/decorations where useful, and totals where meaningful. A plain CRUD list is insufficient.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI

`readonly`, `invisible`, and button visibility are not security. ORM methods, ACLs, multi-company rules, immutable snapshots, state-transition guards, and validation constraints remain authoritative.

The package manager group must imply the package user group. Company-tag records are protected by company rules. Integration events remain manager-only.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY

Follow Odoo 19 conventions, clear sections, descriptive variables, bounded method size, and explicit validation. Avoid compact one-line business logic when it reduces maintainability.

## HARD GATE 13 — COMMENTS YANG BERGUNA

Comments explain WHY: ownership, migration safety, schema-safety, security boundary, or non-obvious Odoo behavior. Do not narrate obvious assignments.

## HARD GATE 14 — CODEX RETRY LIMIT

Maximum two bounded implementation attempts for one defect and maximum one repetition of the same root cause. If the same root cause returns, STOP. Return to root-cause/architecture review. Never delete features or security to escape the retry limit.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX

The release must explicitly report:

- structural inventory
- preservation result
- dependency/ownership result
- Odoo 19 constraint result
- Python compile
- XML parse
- manifest/data existence
- action-method integrity
- Search/List/Form matrix
- ACL/record-rule coverage
- multi-company boundary
- schema-safe `res.company` package configuration
- migration preservation
- eMAR traceability contract
- regression tests
- runtime install/upgrade status
- clinical/operational smoke status

Only runtime evidence can turn PENDING runtime rows into PASS.
