# Release 19.0.1.0.60 — Inventory consumption payload closure

Contents: clinic_demo 19.0.1.0.60 and clinic_inventory 19.0.1.0.5.
Baseline: clinic19a(20260917-065643).md.

## Fix
The template hook already supplies origin, but its public API still required
name. The variant API also inserted and required name. Both validators now
require origin; the variant preserves/fills origin. The usage-line path already
uses origin and source/destination locations. No legacy name is introduced into
the stock.move payload by these APIs. Usage document name remains unchanged.

The demo tests the owner template/variant payload against live stock.move fields
before completing any receipt. Unknown payload fields and missing mandatory
payload keys are reported before stock processing. Company/location/usage links,
UoM, quantity, picked=True, _action_confirm(create_proc=...), _action_done,
explicit event dates and deterministic reference bindings are retained.

Regression tests execute actual template, variant and usage-line methods as a
chain using record doubles. They reject missing quantity/UoM, preserve the exact
variant identity and extension hooks, and ensure repeated payload preparation
adds no legacy name. No manual SQL, workflow bypass or production sequence is
introduced. The existing source.inventory transaction savepoint remains intact.

## Upgrade
1. Stop Odoo. Replace the complete clinic_inventory and clinic_demo folders.
2. Start Odoo and update Apps List.
3. Upgrade clinic_inventory to 19.0.1.0.5, then clinic_demo to 19.0.1.0.60.
4. Open the same Demo Run and Refresh Compatibility.
5. Reconcile Existing Dataset. The previously failed journey can remain FAILED
   until its missing data is successfully executed and validated.
6. Click Execute Next / Resume to retry Receipt and clinical consumption.
Do not Reset Dataset. No manual state or reference editing is needed.
After success the expected progression is 29/40 PASS, subject to all existing
records still satisfying validation. Continue one journey per click while PASS
increases; stop on FAILED/BLOCKED, RPC errors or repeated unchanged progress.

## Evidence and limits
231 source/behavior tests PASS. Main clinic_demo guardrail PASS.
clinic_inventory static owner hard gates 15/15 PASS.
Composite parse: 934 Python + 517 XML, zero errors.
All 41 companion manifest versions match the new expected version vector.
ZIP integrity checked. Raw evidence is in docs/evidence_60.
Native Odoo runtime execution is pending; 40/40 and enterprise readiness are
not claimed. Governing Model-by-Model prompt remains bundled unchanged.
