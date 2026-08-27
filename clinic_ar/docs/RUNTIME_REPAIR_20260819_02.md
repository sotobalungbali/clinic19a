# clinic_ar Runtime Repair 2026-08-19 #02

## Baseline
- Authoritative input: clinic_ar 19.0.3.0.2 (V2) from the user's latest ClinicOne snapshot.
- Runtime failure: `views/billing_bridge_views.xml` hard-inherited
  `clinic_billing.view_clinic_billing_payment_form` and attempted
  `//div[@name='button_box']`.
- Actual current Billing payment form has `<sheet>` but no `button_box`.

## Root Cause
The AR-to-Billing business integration was correct, but the presentation bridge
was coupled to an upstream layout detail.  Odoo validates inherited XPath
anchors at module load, so one missing cosmetic anchor aborted the complete AR
installation.

## Repair
1. Removed hard `clinic_billing` inherited view records from loadable XML.
2. Preserved `views/billing_bridge_views.xml` as an architectural marker.
3. Added `models/view_bridge.py` with idempotent, savepoint-isolated runtime
   view creation.
4. Added two architecture candidates per Billing form:
   - insert into an existing `button_box`;
   - otherwise create an AR button box before the first `<sheet>` child.
5. Added `data/optional_view_bridge.xml` to invoke the bridge after models are
   registered.
6. Added regression tests for idempotence and missing-parent non-blocking behavior.
7. Strengthened the static guardrail to forbid hard `clinic_billing.*`
   `inherit_id` references in AR XML.

## Preservation
No AR model, accounting workflow, reconciliation behavior, security rule,
search/list/form UI, downstream outbox, or Billing model extension was removed.

## Version
`19.0.3.0.2`
