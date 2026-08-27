
# Runtime Repair 2026-08-14 #02 — Searchable Depletion Domain

## Runtime failure

Windows Odoo 19.0.20260505 rejected `wizard/package_redeem_wizard_views.xml`
because the relational field domain on `allocation_line_id` searched
`clinic.package.allocation.line.is_depleted`, while that field was a non-stored
computed field without a custom search method.

Failing contract:

```xml
<field name="allocation_line_id"
       domain="[('allocation_id','=',allocation_id),('is_depleted','=',False)]"/>
```

## Root cause

`is_depleted` was declared as:

```python
is_depleted = fields.Boolean(compute="_compute_consumption")
```

The same compute method also produced remaining quantity/credit and usage count
by manually searching confirmed redemption rows.  The result was correct for
record display, but `is_depleted` was not searchable and therefore invalid for
an Odoo domain.

## Corrective design

The domain is intentionally preserved because hiding depleted entitlements is a
valid enterprise UX rule.  Instead, the allocation benefit snapshot now owns a
proper One2many redemption history and stores its derived consumption metrics:

- `usage_ids`
- `qty_redeemed`
- `remaining_qty`
- `credit_redeemed`
- `remaining_credit`
- `usage_count`
- `is_depleted`

`_compute_consumption()` now uses `@api.depends` on the snapshot totals and the
redemption history fields (`state`, `qty_used`, `credit_used`).  Confirmation,
cancellation, reset, or Draft amount changes therefore trigger ORM
recomputation.  `is_depleted` is stored and indexed, making the wizard and
booking bridge domains valid and efficient.

## Preservation decision

This is a bounded runtime repair.  No package models, workflows, UI actions,
security rules, integration bridges, or commercial/clinical features were
removed.  The existing domain is preserved rather than weakened.

## Regression coverage

Two tests were added:

1. depletion is searchable and recomputes across confirm/cancel;
2. the wizard domain contract explicitly requires `is_depleted` to remain a
   stored/searchable field.

## Result

Package version: **19.0.2.2.0**.

Source/static validation: **PASS**.
Windows install/upgrade runtime: **PENDING** until verified in the target Odoo
instance.
