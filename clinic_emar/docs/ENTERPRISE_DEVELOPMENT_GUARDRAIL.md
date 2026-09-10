# clinic_emar — Enterprise Development Guardrail

This document is a **hard gate**, not a style suggestion. A source/test PASS is not equivalent to enterprise completion or runtime acceptance.

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- **PROJECT:** ClinicOne, Odoo 19 Community Edition.
- **ADDON:** `clinic_emar`, logical upstream medication execution owner (user sequence: #13).
- **AUTHORITATIVE BASELINE:** latest user-supplied ClinicOne combined source; files whose basename starts with digit `0` are excluded as user backups.
- **PRESERVATION RULE:** preserve business intent and downstream contracts; merge duplicate inactive generations without feature loss.
- **ALLOWED CHANGE:** Odoo 19 hardening, dependency-DAG correction, safety/security enforcement, UI completion, bug fixes, integration contracts, tests and documentation.
- **FORBIDDEN CHANGE:** delete clinical depth to make tests pass; change model ownership; introduce forward/circular dependencies; weaken security; silently swallow critical clinical errors.
- **CURRENT VERIFIED STATUS:** source/static only until user proves Windows/Odoo install/upgrade runtime.

## HARD GATE 1 — CODEX BUKAN ARCHITECT

Codex is a bounded implementation worker. Architecture, ownership, dependencies, safety policy and acceptance criteria are defined here. Codex may implement a specifically described defect only; it may not redesign, simplify, rename owners or change dependencies on its own.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION

The baseline contained two generations: the imported `models/core/*` generation and a richer but non-imported root `models/emar_*.py`/integration generation. Valuable intent is merged into one owned model set. Duplicate `_name` owners are not activated in parallel. See `BASELINE_PRESERVATION_MATRIX.md`.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS

Completion requires coherent prescribing, medication order execution, scheduling, administration verification, inventory traceability, alerts, multi-company security, usable UI, downstream contracts and install/upgrade runtime. A green unit/static test does not satisfy this gate by itself.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY

Inventory must include manifest/dependencies, model owners/extensions, fields, constraints, methods/actions, security, rules, data/cron/sequences, views/search/list/form/calendar, wizards, tests, downstream contracts and removed/rejected baseline artifacts.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE

Owned models live under `models/core`; reusable abstract capabilities under `models/mixins`; Odoo stock/account extensions under `models/external_bridges`; ClinicOne integration contracts under `models/integrations`; wizard, security, data and views remain separate. Business sections and methods use readable grouping/comments.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN

Core forms must provide lifecycle statusbars, context, safety/governance information, notebook separation, smart/action buttons and readable medication execution details. Buttons must represent genuine workflows, not decorative shortcuts.

## HARD GATE 7 — UI/UX MATRIX PER MODEL

Every primary persistent eMAR model requires a fit-for-purpose search/list/form experience; schedule additionally has calendar execution context. See `ENTERPRISE_COMPLETENESS_MATRIX.md`.

## HARD GATE 8 — SEARCH VIEW WAJIB

Search views are mandatory for medication profile, prescription, medication line, order, schedule, administration and alert, with operational filters/groupings appropriate to each model.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY

Primary lists use Odoo 19 `<list>`, useful columns, badges/decorations and row actions where operationally justified. No legacy `<tree>`/`tree,form`.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI

ACL + company record rules are mandatory. Clinical state transitions for Prescription, Order, Schedule and Administration are also locked at ORM `write` level: UI invisibility is not treated as a security boundary. Safety/prescriber/administration verification gates execute server-side. Clinical ledgers are not unlinkable by normal eMAR roles.

### Odoo 19 registry inheritance rule

Concrete Odoo model extensions must not use a plain Python helper as an
additional Python base beside `models.Model`, `models.AbstractModel`, or
`models.TransientModel`. Shared behavior must be expressed through Odoo-native
inheritance or module-level helpers. This rule exists because Odoo 19 rebuilds
model bases during registry setup and incompatible Python object layouts can
make the whole database registry unavailable.

### Schema-safe global-model extension rule

`res.company` is a global/high-frequency model and must not receive new
**stored** eMAR configuration columns. A source/schema mismatch on such a field
can make unrelated Website, login, Apps and QWeb requests fail before the module
can be upgraded. The established `res.company.emar_*` API is therefore
preserved as non-stored computed proxies backed by company-scoped
`ir.config_parameter` values. Reintroducing `store=True` on those six fields is
a HARD GATE 10 failure.

Background jobs must also be upgrade-window safe: the eMAR schedule cron checks
its owned tables with PostgreSQL `to_regclass()` before searching them, and the
reschedule TransientModel contains `UndefinedTable` inside a savepoint until its
table has been materialized by the module upgrade.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY

Prefer explicit names, small helpers, readable lifecycle methods and stable integration contracts. Avoid clever metaprogramming when ordinary Odoo model code is clearer to a maintainer.

## HARD GATE 13 — COMMENTS YANG BERGUNA

Comments explain ownership, clinical reason, compatibility contract or non-obvious safety decision. Do not add comments that merely repeat the code.

## HARD GATE 14 — CODEX RETRY LIMIT

Maximum **2 bounded implementation attempts** for one defect and maximum **1 repetition of the same root cause**. If the same root cause persists, STOP. Return the failing evidence/root cause to architecture review. Codex must never enter an unbounded patch/retry loop.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX

The release must carry an explicit matrix covering owned model, purpose, workflow, search/list/form, action/smart buttons, security, multi-company scope, constraints and integration. Missing enterprise dimensions are blockers, even if compilation succeeds.

## Acceptance gates

- Source/static guardrail: PASS required.
- Fresh install on target Odoo 19 CE: PASS required.
- Upgrade on an existing database when applicable: PASS required.
- Real workflow smoke: prescription → order → schedule → verified administration → inventory/audit: PASS required.
- Only after runtime evidence may the addon be frozen/completed.

