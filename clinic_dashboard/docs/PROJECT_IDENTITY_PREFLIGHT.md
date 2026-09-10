# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_dashboard`
- OFFICIAL SEQUENCE: addon 29 of 39
- AUTHORITATIVE BLUEPRINT:
  - **Interactive dashboards for KPIs, revenue, performance, and room utilization.**
- AUTHORITATIVE UPSTREAM BASELINE:
  - latest user bundle dated 2026-08-20;
  - `clinic_reports` 19.0.1.0.0 installed/frozen.
- CURRENT RUNTIME STATUS: PENDING.

## Ownership boundary

`clinic_dashboard` owns:
- Dashboard Board configuration;
- Dashboard Widget configuration;
- immutable Dashboard Snapshots;
- immutable KPI Snapshot Lines;
- the Odoo 19 interactive client action;
- Dashboard refresh/snapshot orchestration.

`clinic_dashboard` does NOT own:
- financial KPI formulas;
- operational KPI formulas;
- clinical KPI formulas;
- Billing/AR/AP/Finance/Accounting transactions;
- Booking/Queue/Room transactions;
- Encounter/Triage/Post-Care/Feedback transactions.

Those metrics remain owned by `clinic_reports` and its upstream transactional
addons.

## Downstream boundary

Future addons such as `clinic_analytics`, `clinic_integration_api`,
`clinic_quality`, and `clinic_portal` are not dependencies.

Dashboard does not implement predictive AI.  That remains the responsibility
of later `clinic_analytics`.

