# Clinic Demo Report Coverage Matrix

All report runs use the deterministic window `anchor_date - 365 days` through
`anchor_date + 90 days`, the Demo Run company, no Branch filter, and the native
`clinic.report.run.action_generate()` owner workflow. Metrics and details are
derived from source transactions; the demo generator never creates report
metrics or report details directly.

| Report | Addon | Source model | Domain/filter | Required demo source | Expected result | Status |
|---|---|---|---|---|---|---|
| Revenue & Billing Summary | clinic_reports | clinic.billing.invoice | company, invoice_date, posted/paid | Prompt 18 billing | INVOICE_COUNT > 0 | Required non-zero |
| Accounts Receivable Aging | clinic_reports | clinic.ar.invoice | company, invoice_date, posted | Prompt 18 AR | AR_INVOICE_COUNT > 0 | Required non-zero |
| Accounts Payable Summary | clinic_reports | clinic.ap | company, invoice_date, approved/posted/partial/paid | Prompt 18 AP | AP_DOCUMENT_COUNT > 0 | Required non-zero |
| Finance Cash Flow | clinic_reports | clinic.finance.transaction | company, transaction_date, posted | Source-supported finance transactions | governed metrics; zero allowed | Coverage-only |
| Accounting Activity | clinic_reports | account.move.line | company, date, posted parent | Prompt 18 accounting moves | JOURNAL_ITEM_COUNT > 0 | Required non-zero |
| Indonesia Tax Reporting | clinic_reports | clinic.l10n.id.tax.report | company, overlapping period, generated/locked | Source-supported tax reports | governed metrics; zero allowed | Coverage-only |
| Insurance Authorization & Claims | clinic_reports | clinic.insurance.authorization / clinic.insurance.claim | company and request/claim date | GAP: authorization producer missing | AUTH_COUNT > 0 | Required non-zero |
| Booking Performance | clinic_reports | booking.booking | company and start_datetime | Prompt 14/20 bookings | BOOKING_COUNT > 0 | Required non-zero |
| Queue Performance | clinic_reports | clinic.queue | company and checkin_time | Prompt 15 queue | QUEUE_COUNT > 0 | Required non-zero |
| Room Utilization | clinic_reports | clinic.room.assignment | company and assigned_at | Prompt 15 room flow | ROOM_ASSIGNMENTS > 0 | Required non-zero |
| Clinical Inventory Usage | clinic_reports | clinic.treatment.product.usage | company, date_usage, done | GAP: completed usage producer missing | INVENTORY_USAGE_COUNT > 0 | Required non-zero |
| Membership Activity | clinic_reports | membership.contract | company and start_date | GAP: contract producer missing | MEMBERSHIP_CONTRACTS > 0 | Required non-zero |
| Patient Wallet Activity | clinic_reports | clinic.wallet.transaction | company, date, posted | GAP: posted ledger producer missing | WALLET_TX_COUNT > 0 | Required non-zero |
| Clinical Encounter Activity | clinic_reports | clinic.encounter | company and date_start | Prompt 16 encounters | ENCOUNTER_COUNT > 0 | Required non-zero |
| Procedure Performance | clinic_reports | clinic.procedure.session | company and date_start | GAP: procedure-session producer missing | PROCEDURE_SESSION_COUNT > 0 | Required non-zero |
| Triage & Vitals | clinic_reports | clinic.triage.session | company and arrival_datetime | Prompt 15 triage | TRIAGE_COUNT > 0 | Required non-zero |
| Adverse Event Activity | clinic_reports | clinic.adverse.event | company and date_occurred | Source-supported adverse events | governed metrics; zero allowed | Coverage-only |
| Post-Care Outcomes | clinic_reports | clinic.postcare.plan | company and start_datetime | Prompt 17/20 follow-up | POSTCARE_PLAN_COUNT > 0 | Required non-zero |
| Patient Satisfaction & Feedback | clinic_reports | clinic.feedback | company, submitted_at, non-draft | Prompt 19 feedback | FEEDBACK_COUNT > 0 | Required non-zero |

`Coverage-only` is explicit: the native report still executes and produces its
governed zero metric when the registered Prompt 01–21 dataset has no legitimate
source transaction. No fake tax, cash-flow, or adverse-event record is invented
merely to make a card non-zero.



















