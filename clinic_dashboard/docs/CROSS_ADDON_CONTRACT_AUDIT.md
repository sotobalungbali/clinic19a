# Cross-Addon Contract Audit

Authoritative source: latest ClinicOne bundle supplied on 2026-08-20.

## Baseline

- `clinic_reports`: **19.0.1.0.0**
- `clinic_dashboard`: absent from baseline, therefore addon 29 is a new owner.

## Normalized reporting contracts consumed

### `clinic.report.definition`

Dashboard consumes:
- `name`
- `family`
- `report_key`
- `state`
- `allow_branch_filter`
- `default_detail_limit`

### `clinic.report.run`

Dashboard consumes:
- `definition_id`
- `company_id`
- `branch_id`
- `date_from`
- `date_to`
- `state`
- `generated_at`
- `finalized_at`
- `metric_ids`
- `action_generate()`

Dashboard may create a missing exact-scope Report Run only through the
`clinic_reports` owner model and invokes its existing generation workflow.

### `clinic.report.metric`

Dashboard consumes:
- `run_id`
- `definition_id`
- `company_id`
- `branch_id`
- `currency_id`
- `code`
- `name`
- `metric_type`
- `value`
- `display_value`
- `note`

Dashboard does not write Report Metrics.

### `clinic.report.detail`

Dashboard does not copy transactional Detail formulas.  Detail remains
available through Clinic Reports for drill-down and analysis.

## Report metric mapping

The six built-in Dashboard Boards use only metric codes verified in the live
`clinic_reports` engine source.

Built-in boards:
1. Executive Overview
2. Financial Performance
3. Operations Performance
4. Clinical Performance
5. Room Utilization
6. Patient Experience

## Branch contract

Dashboard never invents a branch for a report.

When a Branch is selected:
- a Widget whose Report Definition supports Branch may use an exact
  branch-scoped Report Run;
- a Widget whose Report Definition does not support Branch becomes
  `Unsupported Branch Scope`;
- company `policy_branch_scope_reports` is enforced.

## Controlled report generation

Dashboard Analyst implies Clinic Reports Analyst.

When `auto_generate_missing_reports=True`, Dashboard can create the missing
exact-scope `clinic.report.run` and call the Reports-owned `action_generate()`.

This is delegation, not duplicated KPI logic.

## Provenance

Every available Dashboard KPI Snapshot Line stores:
- Dashboard Widget;
- Report Definition;
- Report Run;
- source Report Metric;
- current value;
- previous comparable period value where available;
- threshold/target interpretation.

## Result

- duplicated KPI formulas: 0
- source transaction mutation: 0
- parallel report engine: 0
- fabricated branch scope: 0
- future addon dependency: 0


