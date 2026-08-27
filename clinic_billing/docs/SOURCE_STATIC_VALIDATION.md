# Source / Static Validation — `clinic_billing`

Release candidate: **19.0.3.0.1**

## Result

**PASS — SOURCE/STATIC ONLY. ODOO WINDOWS RUNTIME IS NOT ASSERTED.**

## Gate evidence

- Active Python files: **25**
- Active XML files: **14**
- Persistent billing models: **19 / 19**
- `models.Constraint`: **4**
- Odoo 19 SQL table objects with non-private class names: **0**
- Executable legacy `_sql_constraints`: **0**
- Object buttons: **60**
- Context-aware One2many/List object-button mismatches: **0**
- Search/List/Form UI matrix: **19 / 19**
- Search filters without technical `name`: **0**
- Legacy search `<group expand/string>` attributes: **0**
- ACL rows: **42**
- Enterprise regression test methods: **39**
- Odoo 19 `res.groups.category_id` usage: **0**
- Billing groups without `privilege_id`: **0**
- Executable `account.account.company_id` assumptions: **0**
- `account.account._check_company_domain()` usage: **present**
- Manifest data files missing: **0**
- Required hard-owner dependencies missing: **0**
- Custom ClinicOne comodel references checked: **64**
- Missing custom comodels: **0**
- Missing owning-addon dependencies: **0**
- Dependency cycles reachable from `clinic_billing`: **0**
- Unsafe Odoo model Python multiple-base classes: **0**
- Legacy `<tree>` / `tree` view modes: **0**
- Legacy `attrs=` / `states=` modifiers: **0**
- Packaged basename-prefix-`0` files: **0**
- `__pycache__` / `.pyc`: **0** required in release package

## Runtime defect repaired in 19.0.3.0.1

The previous release declared Odoo 19 SQL table objects with public class attributes, for example:

`name_company_unique = models.Constraint(...)`

Odoo 19 requires SQL table objects to be private class members. The repaired declarations are:

- `_name_company_unique`
- `_provider_tx_company_unique`
- `_code_company_unique`
- `_origin_unique`

This release also proactively applies the already-proven ClinicOne Odoo 19 compatibility contracts:
`res.groups.privilege_id`, named search filters, modern search-group schema, and
`account.account.company_ids` / `_check_company_domain()`.

## Runtime gates still pending

1. Windows/Odoo 19 install;
2. registry/model setup;
3. XML view validation;
4. ACL/record-rule behavior;
5. draft → confirm → accounting invoice → post → payment/reconciliation;
6. clinical imports;
7. discount/voucher/membership;
8. insurance;
9. commission;
10. gateway lifecycle;
11. multi-company isolation.
