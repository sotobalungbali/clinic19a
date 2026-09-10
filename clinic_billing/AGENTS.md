# AGENTS.md — ClinicOne Billing

## Role boundary

Codex is a **bounded implementation worker** only.

Codex MUST NOT:
- redesign ClinicOne architecture;
- change model ownership;
- delete or minimize enterprise features to make tests pass;
- remove fields, methods, views, security, integration contracts, comments, or documentation without an explicit preservation decision;
- create new forward dependencies;
- replace Odoo 19 mechanisms with legacy APIs;
- retry indefinitely.

Codex MAY:
- implement a precisely defined repair;
- add tests/evidence for an already-approved contract;
- make mechanical, scope-bounded changes needed by an explicit acceptance criterion.

## Retry limit

Maximum two bounded implementation attempts.
The same root cause may be retried once.
If the same defect recurs, STOP and return to root-cause / architecture review.

## Immutable project rules

- Odoo 19 CE.
- Ignore files whose basename begins with numeric `0`.
- No executable `_sql_constraints`; use `models.Constraint` where SQL persistence is appropriate.
- Preserve enterprise UI/security depth.
- PASS static/test != enterprise completion.



