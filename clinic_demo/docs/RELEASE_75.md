# ClinicOne bounded final acceptance — 19.0.1.0.75

`Validate` no longer calls whole-registry `JourneyEngine.reconcile()` after all
137 journeys already hold persisted PASS evidence. The final gate verifies the
exact registry cardinality and identities, PASS state, owner-validation
timestamp, downstream refresh state and complete dependency closure.

Reporting Sufficiency still evaluates every unique run-bound record, but reads
them in bounded model/declared-reader ORM batches. Normal ACLs, record rules,
company scope, L1-L8 volume, 12-month history, dimensional spread, status
variation and exception requirements remain fail-closed.

The explicit **Reconcile Existing Dataset** action retains whole-path owner
revalidation semantics. This release only removes that expensive replay from
the final HTTP acceptance request, which previously reached 98k–109k queries
and exceeded the Windows Odoo 120-second virtual real-time limit.

Upgrade only `clinic_demo`, retain the same Demo Run, run **Refresh
Compatibility**, then click **Validate** once. Do not reset or regenerate the
137 PASS journeys.

