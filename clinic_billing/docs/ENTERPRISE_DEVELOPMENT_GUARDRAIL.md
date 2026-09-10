# ClinicOne `clinic_billing` — Enterprise Development Guardrail

This document is a HARD GATE. A change is not accepted merely because Python/XML parses or a test suite passes.

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0

**PROJECT:** ClinicOne  
**ADDON:** `clinic_billing`  
**PLATFORM:** Odoo 19 Community Edition  
**AUTHORITATIVE BASELINE:** latest non-backup `clinic_billing` and cross-addon contracts from the supplied ClinicOne snapshot; basename prefix `0` is backup and ignored.  
**PRESERVATION RULE:** preserve existing functional intent and enterprise depth; obsolete scaffold/history may be rejected only with a documented reason.  
**ALLOWED CHANGE:** Odoo 19 compatibility, model-contract correction, missing enterprise function completion, security/UI hardening, tests/docs/migrations/guardrail.  
**FORBIDDEN CHANGE:** silent feature deletion, ownership transfer, forward dependency creation, security weakening, test-driven simplification.  
**CURRENT VERIFIED STATUS:** SOURCE/STATIC gate only until Windows runtime install/upgrade is proven.

## HARD GATE 1 — CODEX BUKAN ARCHITECT

Codex is a bounded implementation worker. Architecture, ownership, dependencies, preservation decisions and acceptance criteria are determined before implementation.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION

Preserve billing-document lifecycle, lines, accounting bridge, split payments, discount/voucher engines, insurance, commissions, gateway traceability, membership/wallet contract, clinical-source traceability and extension hooks. Scaffold-only code may be removed if it has no executable business function and the preservation matrix records the decision.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS

Completion requires source integrity, model ownership, workflow depth, security, multi-company isolation, professional UI, accounting correctness, clinical traceability, failure handling, upgrade safety and runtime smoke evidence. Static/test PASS alone is insufficient.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY

Inventory every manifest dependency, Python model, abstract engine, security artefact, sequence/cron, view/action/menu, cross-addon bridge, test, tool and documentation file. The inventory is maintained in `STRUCTURAL_INVENTORY.md`.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE

Keep domain concerns in named files: invoice, line, payment, discount, voucher, insurance, commission, gateway, membership/wallet, treatment/source bridges, accounting bridges, UI bridge, integration event, cron, settings. Avoid giant anonymous helper files and hidden monkey patches.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN

Primary transactional forms must expose status, ownership, financial totals, source traceability, accounting status, actionable workflow controls and audit/navigation affordances. Do not settle for CRUD-only forms.

## HARD GATE 7 — UI/UX MATRIX PER MODEL

Every persistent billing owner model must have a purposeful Search, List and Form view. Transactional records additionally receive lifecycle buttons/statusbars where meaningful.

## HARD GATE 8 — SEARCH VIEW WAJIB

All 19 persistent billing models require Search Views with relevant identifiers/relations/status and useful grouping/filtering. Domains must not depend on unsearchable computed fields.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY

List views must surface business identity, patient/provider/source/amount/state/company data appropriate to the model, plus decorations/badges where they improve operational scanning.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI

`readonly`, `invisible`, button groups and statusbars are UX controls, not security. ACLs, record rules and ORM lifecycle guards enforce backend security. Posted accounting/billing data must not become editable merely through RPC/import.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY

Use explicit names, grouped fields, small helpers, docstrings for non-obvious contracts, readable domains, and comments that explain business or compatibility reasons rather than restating syntax.

## HARD GATE 13 — COMMENTS YANG BERGUNA

Comments must document ownership boundaries, Odoo 19 compatibility, accounting/clinical rationale, soft integration decisions and non-obvious security or idempotency rules. Remove stale comments that advertise historical model names/APIs as active contracts.

## HARD GATE 14 — CODEX RETRY LIMIT

Maximum two bounded implementation attempts; maximum one repetition of the same root cause. A repeated root cause requires STOP and root-cause/architecture review rather than another blind patch.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX

The release must explicitly assess:
1. manifest/dependency integrity;
2. model/field/method preservation;
3. Odoo 19 API compatibility;
4. `models.Constraint` migration;
5. accounting lifecycle;
6. payment lifecycle/reconciliation;
7. clinical traceability;
8. discount/voucher/membership;
9. insurance;
10. commissions;
11. gateway;
12. security/multi-company;
13. Search/List/Form coverage;
14. action/statusbar/smart-button quality;
15. upgrade/install packaging;
16. static tests;
17. Windows runtime install/upgrade;
18. clinical/financial smoke scenarios.

**Note:** the user-defined numbering intentionally has no Hard Gate 11. Do not invent one.


## Odoo 19 Runtime Compatibility Addendum — Release 19.0.3.0.1

The following are mandatory source hard gates after proven runtime defects:

- every `models.Constraint`, `models.Index`, and `models.UniqueIndex` class attribute must start with `_`;
- `res.groups` must not use `category_id`; Billing groups must use `res.groups.privilege` and `privilege_id`;
- every Search View `<filter>` must have a unique technical `name`;
- Search View `<group>` must not carry legacy `expand` / `string` attributes;
- executable Billing code must not assume `account.account.company_id`; use Odoo 19 company-domain helpers and `check_company=True`;
- inline relational `type="object"` buttons must resolve on the actual row comodel, not merely somewhere in the addon.



