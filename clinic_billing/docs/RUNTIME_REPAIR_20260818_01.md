# Runtime Repair 2026-08-18 #01 — `clinic_billing`

## Observed runtime error

`AssertionError: Names of SQL objects in a model must start with '_'`

The failure occurred while Python registered `clinic.billing.invoice`, before XML/security loading.

## Root cause

Four Odoo 19 `models.Constraint` descriptors were assigned to class attributes without a
leading underscore:

- `name_company_unique`
- `provider_tx_company_unique`
- `code_company_unique`
- `origin_unique`

Odoo 19 `TableObject.__set_name__()` asserts that SQL table object names start with `_`.

## Repair

Renamed the Python class attributes to:

- `_name_company_unique`
- `_provider_tx_company_unique`
- `_code_company_unique`
- `_origin_unique`

Constraint SQL definitions and business semantics are unchanged.

## Preventive Odoo 19 audit included

Because this billing release predated runtime lessons already proven in Membership, the repair
also normalized:

- Billing security groups to `res.groups.privilege` + `privilege_id`;
- every search filter to have a technical `name`;
- legacy Search View `<group expand/string>` attributes;
- every executable `account.account.company_id` domain/search to Odoo 19
  `company_ids` / `_check_company_domain()` semantics;
- `check_company=True` on commission/settings/doctor account fields;
- context-aware inline One2many/List `type="object"` button validation.

## Preservation

No billing owner model, workflow, financial engine, clinical bridge, security rule, UI feature,
or downstream integration event was removed.

## Status

SOURCE/STATIC: PASS
WINDOWS RUNTIME INSTALL: PENDING



