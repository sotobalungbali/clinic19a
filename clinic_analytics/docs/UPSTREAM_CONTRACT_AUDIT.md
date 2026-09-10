# Upstream Contract Audit

The authoritative ClinicOne snapshot was audited before implementation.

| Purpose | Upstream model | Required contract |
|---|---|---|
| Revenue | `clinic.billing.invoice` | `company_id`, `patient_id`, `invoice_date`, `state`, `amount_total` |
| Booking | `booking.booking` | `company_id`, `patient_id`, `start_datetime`, `state`, `is_no_show` |
| Retention | `booking.booking` | completed booking history keyed by `patient_id` |
| Membership | `membership.contract` | `company_id`, `partner_id`, `start_date`, `end_date`, `state`, `renewed_from_id` |
| Wallet | `clinic.wallet` | `company_id`, `partner_id`, `state`, `balance` |
| Feedback | `clinic.feedback` | `company_id`, `branch_id`, `submitted_at`, `state`, `overall_rating`, `nps_score` |
| Quality | `clinic.quality.check` | `company_id`, `branch_id`, `planned_date`, `state`, `compliance_score` |
| Incident | `clinic.incident` | `company_id`, `branch_id`, `occurred_at`, `state`, `severity` |
| Marketing | `clinic.marketing.recipient` | `company_id`, `branch_id`, `create_date`, delivery states |
| Reports lineage | `clinic.report.definition` | governed report definitions |
| Dashboard bridge | `clinic.dashboard.board` | company/default-branch board scope |
| API bridge | `clinic.api.event` / `clinic.api.event.type` | optional non-PII completion events |
| Audit bridge | `clinic.audit.event` | immutable analytics workflow evidence |

External XML IDs used by this addon were verified in the baseline:
- `clinic_reports.report_definition_fin_revenue`
- `clinic_reports.report_definition_ops_booking`
- `clinic_reports.report_definition_ops_membership`
- `clinic_reports.report_definition_ops_wallet`
- `clinic_reports.report_definition_clinical_feedback`
- `clinic_dashboard.view_dashboard_board_form`
- `clinic_reports.view_report_definition_form`
- `clinic_dashboard.menu_dashboard_root`

