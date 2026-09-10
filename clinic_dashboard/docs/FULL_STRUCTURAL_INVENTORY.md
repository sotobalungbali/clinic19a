# HARD GATE 4 - Full Structural Inventory

## Owned persistent models

1. `clinic.dashboard.board`
   - company-scoped Dashboard configuration;
   - dashboard type;
   - default period;
   - default branch;
   - missing-report generation policy;
   - scheduled refresh governance;
   - widget/snapshot navigation.

2. `clinic.dashboard.widget`
   - one normalized Clinic Reports metric per card;
   - target;
   - warning/critical thresholds;
   - higher/lower/neutral interpretation;
   - icon/display style/layout width;
   - Report Definition and Report Run drill-down.

3. `clinic.dashboard.snapshot`
   - immutable refresh evidence;
   - company/branch/date scope;
   - Ready/Failed/Archived lifecycle;
   - KPI exception counts;
   - source Report Run provenance.

4. `clinic.dashboard.snapshot.line`
   - immutable KPI value;
   - current/previous value;
   - trend;
   - target progress;
   - status;
   - Report Definition/Run/Metric traceability.

## Additive inherited models

- `res.company`
- `res.config.settings`
- `clinic.branch`
- `clinic.report.run`

## Client

- Odoo 19 Owl client action `clinic_dashboard.main`
- responsive Dashboard toolbar
- Board selector
- date range
- Branch selector
- Refresh
- History
- Configure
- KPI cards
- status badges
- trend indicators
- target progress
- Report/Metric drill-down

## Built-in workspaces

- Executive Overview
- Financial Performance
- Operations Performance
- Clinical Performance
- Room Utilization
- Patient Experience

## Services

- idempotent company setup
- post-init company seeding
- missing Report Run delegation
- scheduled Board refresh
- snapshot archival
- backend fallback views
- KPI Pivot/Graph analysis
- Enterprise Development Guardrail
- runtime contract suite

