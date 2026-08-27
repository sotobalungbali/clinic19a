# Runtime Repair 19.0.2.0.2 — Searchable Overtime

## Concrete runtime evidence

Odoo 19 rejected `view_treatment_session_search` while validating:

`[('is_overtime', '=', True)]`

because `is_overtime` was a computed non-stored Boolean without a search
method.

## Why `store=True` is correct here

`is_overtime` is computed only from:

- `duration_planned`
- `duration_actual`

and `duration_actual` itself is stored from the session's stored start/end
datetimes.

Therefore `is_overtime` is deterministic from stored business data; it is not
a clock-dependent "now" flag. Persisting it is semantically safe, improves
search/filter performance and also makes it available to reporting/grouping.

## Repair

`is_overtime` now has:

- `store=True`
- `index=True`

The public field name and compute method remain unchanged.

## Same-pattern guard

The source tests and Enterprise Guardrail now reject Search View domains that
refer to a computed field unless that field is stored or has an explicit
`search=` method.

No workflow, security, billing, stock, stage, booking or downstream contract is
removed.
