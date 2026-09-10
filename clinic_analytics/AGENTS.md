# ClinicOne `clinic_analytics` — Codex Boundary

Codex is a bounded implementation worker.

Codex is NOT:
- the architect;
- a simplifier that drops upstream contracts;
- a generic formula/RPC builder;
- a retry engine without an end condition.

## Hard boundaries

1. `clinic_analytics` is addon #39 / 39 and may consume upstream addon contracts,
   but must never move ownership of Patient, Booking, Billing, Membership,
   Wallet, Feedback, Reports, Dashboard, Marketing, Incident, Quality, API or Audit.
2. KPI sources are code-owned fixed adapters. User input never selects arbitrary
   Odoo models, fields, methods or domains.
3. Source aggregation may use sudo only behind fixed company/branch-scoped
   adapters. Source drill-down always falls back to the user's normal ACL/rules.
4. Company-wide analytical evidence is manager-only. Analyst/user roles are
   branch-scoped through backend record rules.
5. Forecasting is transparent and deterministic: Naive, Moving Average,
   Linear Trend. No external ML dependency or unsupported AI claim.
6. Executable `_sql_constraints` is forbidden. Use Odoo 19 `models.Constraint`.
7. Digit-prefixed backup file basenames are never packaged.
8. Maximum bounded implementation repairs for this build cycle: 3.

