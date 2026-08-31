


# Clinic Membership — Source / Static Validation

Release: **19.0.3.0.3**

## Authoritative input
- Latest ClinicOne aggregate snapshot supplied by the user on 18 Aug 2026.
- Active baseline `clinic_membership` files inspected: **60**.
- Numeric-prefix backup files are excluded by policy.

## Odoo 19 compatibility
- Python source AST parse: PASS.
- XML parse: PASS.
- Manifest data references: 19/19 present.
- Executable legacy `_sql_constraints`: **0**.
- `models.Constraint`: **22**.
- Legacy `<tree>` view tags: **0**.
- Legacy `tree` action view modes: **0**.
- Legacy `attrs=` / `states=` view modifiers: **0**.
- Unsafe arbitrary Python multiple inheritance on Odoo model classes: **0**.

## Enterprise domain coverage
Persistent owner models: **9/9**
1. `membership.plan`
2. `membership.plan.benefit`
3. `membership.contract`
4. `membership.contract.benefit`
5. `membership.usage`
6. `membership.voucher`
7. `membership.point.tx`
8. `membership.hold`
9. `membership.integration.event`

UI matrix: Search/List/Form **9/9**.
Object action methods referenced by XML: **43**, missing methods: **0**.
Regression tests authored: **27**.

## Searchability contracts
- `membership.contract.is_expired`: custom search method.
- `membership.voucher.is_expired`: custom search method.
- `membership.contract.benefit.is_depleted`: stored/indexed computed field.
- No known Membership domain/search filter depends on an unsearchable computed field.

## Cross-addon contract audit
- Custom ClinicOne/membership relational comodels referenced: **20**.
- Missing custom comodels in supplied snapshot: **0**.
- Missing owner dependencies: **0**.
- Dependency cycles reachable from `clinic_membership`: **0**.
- Forbidden downstream manifest dependencies (`clinic_billing`, `clinic_ar`, `clinic_wallet`): **0**.
- Hard cross-addon inherited form XML IDs in loadable static views: **0**.
- Runtime-safe form bridges: Partner, Patient, Booking, Encounter, Care Plan, Package Allocation, Package Usage, eMAR Administration.

## Odoo 19 security-group compatibility
- `res.groups.category_id`: **0** occurrences in Membership group records.
- `res.groups.privilege`: **1** dedicated Membership privilege record.
- Membership User and Membership Manager both use `privilege_id`.
- Static guardrail fails if legacy `category_id` is reintroduced on `res.groups`.
- Runtime regression test verifies the Odoo 19 privilege linkage.

## Security / governance
- Multi-company record rules cover all nine persistent Membership owner models.
- Plan/Benefit master mutation requires Membership Manager.
- Entitlement snapshots are ORM-created, immutable operational snapshots.
- Validated usage, voucher history, points, and hold workflows are lifecycle governed.
- Ordinary users cannot directly create loyalty point ledger or voucher master rows; internal governed workflows use bounded elevated creation where required.
- UI readonly/invisible state is not treated as the security boundary.

## Architecture direction
`clinic_membership` is deliberately upstream of Billing/AR/Wallet. It owns the membership/benefit/loyalty domain and publishes `membership.integration.event` for downstream consumers. Existing Billing can consume canonical partner hints `membership_reference` and `membership_level_key` without a Membership -> Billing dependency.

## Result
**PASS — SOURCE / STATIC ONLY.**

Windows Odoo 19 CE installation/upgrade and clinical/commercial smoke tests remain **PENDING** until executed on the user's Odoo runtime.

## Runtime Repair 19.0.3.0.2 — Search View Validation

- Search filters without `name`: **0**
- Duplicate filter names within a search view: **0**
- Search `<group>` with legacy `expand`/`string`: **0**
- Search fields missing from their owner model (static owner audit): **0**
- Group-by fields missing from their owner model (static owner audit): **0**
- Persistent owner search/list/form matrix: **9/9**

The guardrail contains explicit Odoo 19 search-view contract checks so this
class of parse failure is blocked before release.




## Runtime Repair 19.0.3.0.3 — Odoo 19 Account Company Contract

- `account.account.company_id` assumptions in Membership runtime code: **0**
- `membership.plan.income_account_id.check_company`: **True**
- Revenue-account field domain uses removed `account.account.company_id`: **0**
- Backend fallback search uses `account.account._check_company_domain(company)`: **PASS**
- Explicit ORM validation that selected income account contains the plan company in `company_ids`: **PASS**
- `account.analytic.account.company_id` remains valid and is not rewritten.

Static guardrail now fails if the legacy account-company assumption is reintroduced.


## Runtime Repair 19.0.3.0.4
- Context-aware inline relational button audit: PASS.
- One2many/Many2many row object-button/model mismatches: 0.
- `membership.contract.benefit` inline Usage action uses `action_view_usages`: PASS.
- Regression tests authored: 28.


## Runtime Repair 19.0.3.0.5 — Odoo 19 Settings Action Ownership

- Historical `base.action_res_config_settings` references: **0**
- Membership Settings menu external action dependencies: **0**
- Local `clinic_membership.action_membership_settings`: **PASS**
- Local action target `res.config.settings`: **PASS**
- Local action view mode `form`: **PASS**
- Local action context selects `clinic_membership`: **PASS**
- Membership menu actions resolving to locally defined actions: **PASS**
- Regression tests authored: **29**

The guardrail now rejects external menu action dependencies for Membership and
requires the Settings menu to use the addon-owned action.


## V6 cross-addon/source audit
- Release version: **19.0.3.0.5**
- Custom relational references examined: **67**
- Unique custom comodels referenced: **20**
- Missing custom comodels in supplied ClinicOne snapshot: **0**
- Missing owning-addon dependencies: **0**
- Dependency cycles reachable from `clinic_membership`: **0**
- External action XML IDs used by Membership menu items: **0**
- External core XML IDs remaining in Membership views are limited to stable core
  contracts required for security/multi-company/settings view inheritance.
