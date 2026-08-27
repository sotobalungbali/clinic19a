# ClinicOne Treatment Session Management

Source-actual ClinicOne addon **#41 / 41** for Odoo 19 Community Edition.

`clinic_treatment_session` is the operational treatment-delivery layer between
Booking and downstream clinical/billing/reporting workflows.

Core lifecycle:

`Draft → Confirmed → In Progress → Done`

with controlled `No-show` and `Cancelled` branches.

Enterprise scope includes:
- canonical Patient / Clinic Doctor / Branch / Encounter / Referral links;
- Booking → Treatment Session generation;
- Package attribution;
- stock-aware material consumption;
- Clinic Billing bridge plus preserved standard `account.move` API;
- actual execution timestamps and duration variance;
- doctor/room overlap protection;
- reminders and bounded auto-no-show;
- Patient/Doctor/Encounter/Branch/Booking smart-button bridges;
- Search/List/Form/Kanban/Calendar/Graph/Pivot UI;
- Odoo 19 privilege hierarchy, ACLs and branch/company record rules;
- upgrade migration from the historical 19.0.1.0.0 draft;
- Enterprise Development Guardrail HARD GATE 0–15.

Downstream consumers such as Membership, AR, Wallet, Reports, Dashboard and
Analytics remain downstream and are intentionally not hard dependencies.
