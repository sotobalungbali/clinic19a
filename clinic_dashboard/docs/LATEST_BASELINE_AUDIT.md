# Latest Baseline Audit - 2026-08-20

Authoritative attached bundle:
`clinic19a(20260820-121145).md`

## Project state

- Parsed bundle sections: 1,357
- Parsed ClinicOne manifests: 32
- `clinic_reports`: 19.0.1.0.0
- `clinic_dashboard`: absent from baseline
- Result: addon 29 is a new owner addon.

## Dashboard upstream contract

Live-imported `clinic_reports` provides:

- `clinic.report.definition`
- `clinic.report.run`
- `clinic.report.metric`
- `clinic.report.detail`
- `clinic.report.schedule`

Dashboard consumes the normalized Report Metric layer and delegates missing
exact-scope Report Runs to the Reports-owned `action_generate()` workflow.

## Built-in metric mapping audit

- built-in Boards: 6
- built-in Widgets: 50
- Report engine dispatches in `clinic_reports`: 19
- Dashboard `(report_key, metric_code)` pairs checked: 50
- unknown Report Keys: 0
- unknown Metric Codes: 0

## Dependency direction

Direct ClinicOne dependencies of addon 29:

1. `clinic_base`
2. `clinic_branch`
3. `clinic_reports`

No dependency exists on later addons:
- `clinic_ecommerce`
- `clinic_portal`
- `clinic_marketing`
- `clinic_telemedicine_secure_messaging`
- `clinic_incident_event`
- `clinic_quality`
- `clinic_integration_api`
- `clinic_audit`
- `clinic_analytics`

## Preservation result

- duplicated Report models: 0
- duplicated transactional models: 0
- duplicated KPI formulas: 0
- transactional source mutation: 0
- silent unsupported Branch fallback: 0
- dead/unimported source used as runtime contract: 0


