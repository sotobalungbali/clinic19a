


# Clinic Membership — Enterprise Development Guardrail

## PROJECT IDENTITY PREFLIGHT — HARD GATE 0
PROJECT: ClinicOne. ADDON: clinic_membership. PLATFORM: Odoo 19 CE. AUTHORITATIVE BASELINE: latest user-provided ClinicOne snapshot. POSITION: membership before clinic_billing. PRESERVATION: active non-prefix-0 functionality preserved or explicitly replaced with a safer contract. CURRENT VERIFIED STATUS: source/static only until Windows runtime succeeds.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Architecture is defined here. Codex may only execute bounded implementation work.
## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
Plans, benefits, contracts, usage, vouchers, points, holds and integration intent must not disappear.
## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Test success cannot replace lifecycle, audit, security, traceability, UI and integration completeness.
## HARD GATE 4 — FULL STRUCTURAL INVENTORY
Inventory models, views, security, data, wizard, migration, tests and integration contracts before release.
## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Domain ownership is separated by file; business actions use descriptive names and small helpers.
## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Primary forms require lifecycle header, logical groups/notebooks and actionable operational context.
## HARD GATE 7 — UI/UX MATRIX PER MODEL
All nine persistent owner models require Search/List/Form coverage.
## HARD GATE 8 — SEARCH VIEW WAJIB
No persistent business owner model ships without a search view.
## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Lists expose identifiers, ownership, dates, value/state and relevant decorations.
## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
ACL, record rules, immutable ledgers/snapshots and ORM workflow guards are authoritative; invisible/readonly UI is not security.
## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Avoid generated-looking mega-files; maintain readable modules and conventional Odoo structure.
## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain ownership, safety, compatibility or non-obvious tradeoffs; avoid noise.
## HARD GATE 14 — CODEX RETRY LIMIT
Maximum 2 bounded attempts and maximum 1 repetition of the same root cause; then stop and return to root-cause review.
## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
Release requires domain, workflow, UI, searchability, security, multi-company, integration, migration, Odoo-19 compatibility and test evidence.

> Numbering intentionally follows the user's permanent guardrail. There is no invented HARD GATE 11.

## Odoo 19 Search View Runtime Gate (19.0.3.0.2)

As part of HARD GATE 8 and HARD GATE 15:

- every search `<filter>` MUST have a stable `name`;
- filter names MUST be unique inside a search view;
- search `<group>` MUST NOT use legacy `expand` or `string` attributes;
- every Group By field MUST exist on the target model;
- a source/static PASS is not a Windows runtime PASS.




## Odoo 19 Accounting Company Runtime Gate (19.0.3.0.3)

As part of HARD GATE 10 and HARD GATE 15:

- `account.account.company_id` MUST NOT be referenced; Odoo 19 uses `company_ids`;
- Many2one fields to `account.account` MUST use `check_company=True` when company consistency matters;
- backend account searches MUST use the comodel's `_check_company_domain(company)` contract;
- UI domains do not replace ORM company validation;
- a source/static PASS is not a Windows runtime PASS.


## Odoo 19 Inline Relational Button Runtime Gate
For every inline One2many/Many2many list/form, a `type="object"` button MUST
resolve to a Python method on the relational comodel represented by that row.
A method with the same name on the parent form model does not satisfy this gate.
The static guardrail performs context-aware relational-model resolution.


## Odoo 19 Settings/Menu Action Runtime Gate (19.0.3.0.5)

As part of HARD GATE 6, HARD GATE 10 and HARD GATE 15:

- Membership-owned menus MUST resolve their actions to XML IDs defined by
  `clinic_membership`;
- `base.action_res_config_settings` is forbidden because it is not an Odoo 19
  core XML ID;
- Membership Settings MUST use
  `clinic_membership.action_membership_settings`;
- that action MUST target `res.config.settings` in form mode and select the
  `clinic_membership` settings app through context;
- a source/static PASS is not a Windows runtime PASS.
