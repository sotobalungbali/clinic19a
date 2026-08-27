# Architecture Decision Record

## Decision

Clinic Analytics is a governed downstream analytics layer.

It owns:
- KPI definitions;
- immutable KPI snapshot evidence;
- transparent forecast runs and points;
- aggregate retention cohorts;
- actionable insight workflow;
- analytics schedules.

It does **not** own:
- Patient;
- Booking;
- Billing / AR / AP / Wallet;
- Membership;
- Feedback;
- Reports;
- Dashboard;
- Marketing;
- Incident / Quality;
- Integration API;
- Audit evidence.

## Source execution

KPI source adapters are fixed Python methods. The user cannot configure an
arbitrary Odoo model, field, method, or domain.

Aggregate source reads may use `sudo()` only inside those fixed adapters and
must include code-owned company/branch scope. Drill-down actions return normal
Odoo actions and therefore use the viewer's ordinary ACL and record rules.

## Forecasting

Release 19.0.1.0.0 implements auditable baseline methods only:
- Naive;
- Moving Average;
- Linear Trend.

These are deterministic decision-support forecasts, not guarantees and not an
opaque AI/ML claim.
