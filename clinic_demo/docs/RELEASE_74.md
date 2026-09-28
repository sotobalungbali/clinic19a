# ClinicOne incremental Execute Next 10 — 19.0.1.0.74

The Control Center now exposes **Execute Next 10**. It executes at most ten
ordered non-PASS journeys, stops fail-closed on the first error, and reports
both the number completed in the request and the next journey.

The incremental runner no longer reconciles all 137 journeys before and after
every single execution. It trusts persisted PASS evidence from the same build,
revalidates each target immediately before mutation, validates the resulting
owner aggregate, invalidates downstream consumers, and reconciles only the
next remaining target. Explicit Reconcile Existing Dataset and broad rebuild
actions retain whole-path reconciliation semantics.

This removes the 153k+ query full-registry sweep that exceeded the Windows
Odoo 120-second request limit at `population.procedure.m06`. Existing 74 PASS
journeys remain retained; no dataset reset is required.


