


# ClinicOne Membership — Odoo 19 CE

Enterprise membership, loyalty, benefit entitlement, vouchers, points, holds, and usage traceability for ClinicOne.

## Architecture
`clinic_membership` is intentionally upstream of `clinic_billing`, `clinic_ar`, and `clinic_wallet`. Downstream financial systems integrate through stable member hints, accounting documents, and `membership.integration.event`; they are not hard dependencies.

## Release
Version 19.0.3.0.5. Replace the complete addon directory; do not merge with numeric-prefix backup files.

## Runtime repair 19.0.3.0.1
Odoo 19 security groups use `res.groups.privilege`. Membership User/Manager are attached to
`privilege_clinic_membership` through `privilege_id`; legacy `res.groups.category_id` is forbidden.


## Runtime Compatibility Repairs

### 19.0.3.0.2 — Odoo 19 Search View Contract

The Odoo 19 installer validates search views against the Odoo 19 Relax NG schema.
Every `<filter>` now has a stable technical `name`, and legacy search-group
attributes `expand` / `string` have been removed from the nine primary
Membership search views.

This repair is deliberately UI/schema-only. Membership business ownership,
security, benefits, contracts, usage, vouchers, points, holds, clinical
traceability, and downstream integration contracts are preserved.


### Windows targeted install helper

For a database where Membership is still uninstalled after a rolled-back activation, use `tools/windows_install_clinic_membership_v6.ps1` with Odoo stopped.



### 19.0.3.0.3 — Odoo 19 Account Company Contract

Odoo 19 `account.account` is multi-company through `company_ids`; the legacy
`company_id` field no longer exists. Membership revenue account selection now:

- uses `check_company=True` on `membership.plan.income_account_id`;
- keeps only the account-type domain on the field;
- validates company membership at ORM level;
- uses `account.account._check_company_domain(company)` for backend fallback search.

This prevents both view validation failures and later invoice-generation failures.


### 19.0.3.0.4 — One2many Row Action Ownership

Odoo `type="object"` buttons execute on the model represented by the view row.
The Entitlements inline list on `membership.contract` renders records of
`membership.contract.benefit`, so its Usage button now calls the child model
method `action_view_usages` rather than the parent contract method
`action_open_usages`.

The enterprise guardrail now validates inline relational buttons against the
actual One2many/Many2many comodel, preventing global method-name checks from
masking row-model ownership defects.


### 19.0.3.0.5 — Odoo 19 Settings Action Ownership

Odoo 19 core exposes the base Settings action as `base.res_config_setting_act_window`
and the General Settings application action as
`base_setup.action_general_configuration`. The historical external ID
`base.action_res_config_settings` is not part of the Odoo 19 core contract.

Membership now owns `clinic_membership.action_membership_settings`, a dedicated
`ir.actions.act_window` for `res.config.settings` with
`{'module': 'clinic_membership', 'bin_size': False}` context. The Membership
Settings menu points to this local action, eliminating an unnecessary fragile
external action dependency.


## Runtime repair 19.0.3.0.6

Reloads the already-declared Membership Manager ACL contract after runtime evidence showed the installed database had no create grant for `membership.plan`. No workflow or permission scope is broadened beyond source-declared manager access.

