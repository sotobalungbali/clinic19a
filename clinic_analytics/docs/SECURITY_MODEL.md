# Security Model — HARD GATE 10

## Roles

1. Clinic Analytics User
   - read analytical evidence assigned to allowed branches.

2. Clinic Analytics Analyst
   - User rights plus creation/execution of branch-scoped Snapshots,
     Forecasts, Cohorts, and insight workflow.

3. Clinic Analytics Manager
   - Analyst rights plus company-wide analytics, KPI governance,
     schedule management and deletion of permitted draft/config records.

## Backend controls

- Regular users/analysts cannot read company-wide (`branch_id = False`)
  analytical evidence through analytics record rules.
- Company-wide analytics require Analytics Manager at Python workflow level.
- Ready Snapshots, Snapshot Lines, Ready Forecasts, Forecast Points and Ready
  Cohorts enforce immutability in Python, not only in UI.
- Source aggregation uses fixed adapters with mandatory company/branch domain.
- Source drill-down never uses sudo.
- Integration event publishing is disabled by default.
- Analytics integration payloads contain aggregate metadata, not patient PII.

