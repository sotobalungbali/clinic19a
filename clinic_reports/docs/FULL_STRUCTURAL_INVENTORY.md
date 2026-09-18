# HARD GATE 4 — Full Structural Inventory

## Owned persistent models

1. `clinic.report.definition`
   - governed catalog of 19 built-in reports;
   - family/report-key semantics;
   - methodology and default output policy.

2. `clinic.report.run`
   - company/branch/date scope;
   - engine dispatch;
   - Draft/Generating/Ready/Failed/Finalized/Archived lifecycle;
   - immutable final snapshot;
   - CSV/PDF output.

3. `clinic.report.metric`
   - normalized count/amount/percentage/duration/score/quantity metrics;
   - stable future Dashboard layer.

4. `clinic.report.detail`
   - traceable source snapshots;
   - Patient/Doctor/Staff/Treatment/Room dimensions;
   - generic source-model/source-ID drill-down.

5. `clinic.report.schedule`
   - Daily/Weekly/Monthly recurring generation;
   - rolling date window;
   - owner, next/last run;
   - optional auto-finalization.

## Transient model

- `clinic.report.generate.wizard`

## Abstract models

- `clinic.report.company.mixin`
- `clinic.report.engine.financial`
- `clinic.report.engine.operational`
- `clinic.report.engine.clinical`

## Inherited additive integrations

- `clinic.branch`
- `res.company`
- `res.config.settings`

## Engines

Financial:
- Revenue/Billing
- AR
- AP
- Cash Flow
- Accounting
- Indonesia Tax
- Insurance

Operational:
- Booking
- Queue
- Room
- Inventory
- Membership
- Wallet

Clinical:
- Encounter
- Procedure
- Triage/Vitals
- Adverse Events
- Post-Care
- Feedback/NPS

## Output / services

- 19 seeded Report Definitions;
- 1 report sequence;
- 1 schedule cron;
- CSV export;
- QWeb PDF;
- Search/List/Form on every owned persistent model;
- Pivot/Graph for Metrics and Details;
- 3-level Odoo 19 Reports privilege hierarchy;
- multi-company record rules;
- Enterprise Development Guardrail;
- runtime contract/regression suite.

