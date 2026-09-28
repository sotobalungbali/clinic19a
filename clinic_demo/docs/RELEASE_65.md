# ClinicOne Enterprise Population Runtime Repair — 19.0.1.0.65

Baseline: `clinic19a(20260922-062015).md`; governing architecture:
`modelbymodel(9).md` (stored as `GOVERNING_MODEL_BY_MODEL.md`).

## Runtime closure

`population.setup` previously rejected the source Billing product because it
had no product/category Income property.  The already-posted `DEMO-BILL-001`
nevertheless proved the actual owner-selected Income account on its uniquely
linked accounting line.  Version 65 freezes that exact account as the bounded
population contract:

1. require one source monetary Billing line and a posted accounting move;
2. require exactly one accounting invoice line linked by
   `clinic_billing_line_id`;
3. validate Income type, company membership and actor read access through the
   Billing owner API;
4. pass the account explicitly into every population Billing workflow;
5. verify the posted population move used precisely that account.

Normal Billing callers retain their existing account resolution.  The explicit
contract is optional and fail-closed when supplied.  No source product,
category, account or posted move is modified.

## Upgrade and resume

Replace both addon folders and upgrade in this order:

1. `clinic_billing` 19.0.3.0.7
2. `clinic_demo` 19.0.1.0.65

Then restart Odoo, Update Apps List, open the same Demo Run, run Refresh
Compatibility, Reconcile Existing Dataset, and Execute Next / Resume.  Do not
Reset Dataset and do not create another Demo Run.  The failed setup savepoint
created no committed population payload; the 31 valid prior journeys remain.

## Build evidence and limitation

- 253 source/behavior contract tests: PASS.
- `clinic_demo`, `clinic_billing`, `clinic_membership` guardrails: PASS.
- Full composite Python/XML parse: PASS.
- ZIP integrity: PASS before delivery.

These are source/static and record-double checks.  Native Odoo database runtime
was not available in the build environment, so runtime PASS must be established
on the target database through the bounded journey controls above.











