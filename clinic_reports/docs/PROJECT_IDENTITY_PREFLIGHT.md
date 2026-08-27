# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_reports`
- OFFICIAL SEQUENCE: addon 28 of 39
- AUTHORITATIVE BLUEPRINT:
  - **Central reporting engine for financial, operational, and clinical reports.**
- AUTHORITATIVE SOURCE BASELINE:
  - latest user bundle dated 2026-08-20;
  - `clinic_feedback` 19.0.1.0.0 installed/frozen.
- CURRENT RUNTIME STATUS: PENDING.

## Ownership boundary

Addon 28 owns only:
- governed Report Definitions;
- Report Runs / snapshots;
- normalized Report Metrics;
- traceable Report Detail snapshots;
- Report Schedules;
- Generate Report wizard.

Addon 28 does **not** own or replace:
- Billing;
- AR;
- AP;
- Finance;
- Accounting;
- Tax;
- Insurance;
- Booking;
- Queue;
- Room;
- Inventory;
- Membership;
- Wallet;
- Encounter;
- Procedure;
- Triage;
- Adverse Event;
- Post-Care;
- Feedback.

Report engines read those models and snapshot selected facts.  Source records
remain authoritative.

## Downstream boundary

`clinic_dashboard` is the official next addon.  Addon 28 deliberately exposes
stable normalized `clinic.report.metric` and `clinic.report.detail` records for
future dashboard consumption, while maintaining **zero dependency** on
`clinic_dashboard`.

Other future modules such as Portal, Quality, Integration API and Analytics are
also not dependencies.
