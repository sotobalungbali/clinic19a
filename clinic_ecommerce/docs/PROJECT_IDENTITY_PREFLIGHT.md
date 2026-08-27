# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_ecommerce`
- OFFICIAL SEQUENCE: addon 30 of 39
- AUTHORITATIVE BASELINE: latest user bundle dated 2026-08-20/21
- LAST FROZEN UPSTREAM: `clinic_dashboard` 19.0.1.0.0
- REQUIRED REPORT/DASHBOARD STATUS: preserved; no re-ownership
- CURRENT RUNTIME STATUS: PENDING

## Addon responsibility

`clinic_ecommerce` is the ClinicOne online-commerce orchestration layer built on
Odoo 19 Website Sale.

It owns:
- governed Clinic online catalog mappings;
- Clinic-specific cart/order metadata;
- patient, Branch, terms and scheduling-preference capture;
- fulfillment handoff evidence and exception queue;
- curated Clinic storefront routes/templates;
- controlled downstream creation of owner-module artifacts after Sale/Payment
  lifecycle events.

It does **not** own:
- Odoo cart/checkout/payment/Sales Order/invoice/delivery lifecycle;
- Treatment master data;
- Booking workflow;
- Package Allocation lifecycle;
- Membership Contract lifecycle;
- Clinic Reports KPI formulas;
- Clinic Dashboard presentation/KPI ownership.

## Preservation rule

Existing installed addon behavior is preserved. `clinic_ecommerce` adds
provenance/coordination only. It must not simplify or replace owner workflows
merely to make eCommerce convenient.

## Future-addon boundary

No dependency is permitted on official later addons 31–39, including
`clinic_portal`, `clinic_marketing`, `clinic_telemedicine_secure_messaging`,
`clinic_incident_event`, `clinic_quality`, `clinic_integration_api`,
`clinic_audit`, and `clinic_analytics`.
