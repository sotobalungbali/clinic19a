# ClinicOne Referral Management

Source-actual ClinicOne addon **#40 / 41** for Odoo 19 Community Edition.

This full-corrected release rebuilds the historical referral draft into an
enterprise referral/acquisition module while preserving its three public owner
models:

- `clinic.referral`
- `clinic.referral.program`
- `clinic.referral.source`

## Enterprise capabilities

- source / channel attribution;
- referral program governance;
- branch-aware acquisition tracking;
- CRM / UTM lineage;
- referral-to-booking attribution;
- patient and branch smart navigation;
- downstream-safe membership and treatment-session visibility;
- conversion evidence and value attribution;
- reward policy/status workflow without stealing Wallet/Accounting ownership;
- Search/List/Form/Kanban/Graph/Pivot views;
- daily expiry cron;
- Odoo 19 Settings extension;
- Odoo 19 `models.Constraint`;
- HARD GATE 0–15 source/static guardrail.

Runtime status remains pending until installation/upgrade succeeds on the target
Odoo database.
