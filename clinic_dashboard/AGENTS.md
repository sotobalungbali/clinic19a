# ClinicOne `clinic_dashboard` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- KPI definition owner;
- report-engine owner;
- transactional-model owner;
- an endless retry engine.

Architecture authority:
- `clinic_reports` owns normalized KPI/report output.
- `clinic_dashboard` consumes `clinic.report.metric`,
  `clinic.report.detail`, and `clinic.report.run`.
- upstream transaction addons remain authoritative.
- future addons remain downstream/independent.

Forbidden:
- duplicating Report KPI formulas in Dashboard;
- mutating Billing/AR/AP/Finance/Accounting/Booking/Queue/Clinical records;
- shadow models for upstream transactions;
- silently ignoring branch scope;
- using future `clinic_analytics` or `clinic_integration_api` as dependencies;
- deleting widgets/features merely to pass tests;
- executable legacy `_sql_constraints`;
- legacy `<tree>`, `attrs=`, or `states=`;
- list-valued `_inherit` without explicit `_name`.

Retry limit:
- maximum 2 bounded implementation attempts per verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause/architecture review.

Odoo 19:
- `models.Constraint` / `models.Index`;
- `res.groups.privilege` / `privilege_id`;
- `<list>` architecture;
- attribute-free `<search>` and direct `<group>`;
- Owl client action registered in the actions registry;
- backend model views remain available as an operational fallback.
