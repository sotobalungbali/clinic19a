# Runtime Repair — 2026-08-22

## Trigger

Upgrading `clinic_branch` caused the Odoo 19 registry to revalidate installed views.
`clinic_treatment_catalog/views/treatment_views.xml` failed because
`is_currently_valid` was a non-stored computed Boolean without a search method.

## Root cause

The business value is intentionally dynamic: it depends on the current date.
Using `store=True` would make the value stale when the date changes unless a
separate scheduled recomputation mechanism were introduced.

## Corrective action

Preserve `store=False` and add `search="_search_is_currently_valid"` on all three
models whose search views use the field:

- `clinic.treatment.catalog`
- `clinic.treatment.bundle`
- `clinic.treatment.pricelist`

The search method translates the Boolean into domains over stored fields
`active`, `valid_from`, and `valid_to`, and supports Odoo 19 Boolean search
normalization (`in` / `not in`).

## Scope

No model name, field name, XML ID, dependency, security rule, sequence, business
workflow, or ClinicOne cross-addon contract was removed or renamed.

