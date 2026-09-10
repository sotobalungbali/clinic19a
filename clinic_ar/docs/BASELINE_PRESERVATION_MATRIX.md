# Baseline Preservation Matrix

| Baseline capability | Decision | Final ownership |
|---|---|---|
| AR invoice | PRESERVE + HARDEN | `clinic.ar.invoice` |
| AR line | PRESERVE + HARDEN | `clinic.ar.invoice.line` |
| AR payment/receipt | PRESERVE + COMPLETE | `clinic.ar.payment` + `account.payment` |
| Credit allocation | PRESERVE + HARDEN | `clinic.ar.allocation*` + reconciliation |
| Follow-up/dunning | PRESERVE + HARDEN | `clinic.ar.followup*` |
| Partner credit limit/hold/aging | PRESERVE + HARDEN | `res.partner` extension |
| Accounting bridge | PRESERVE + REWRITE | `account.move` extension |
| Historical `clinic.booking` reference | REPLACE WITH ACTUAL OWNER | `booking.booking` |
| Historical `clinic.membership` reference | REPLACE WITH ACTUAL OWNER | `membership.contract` |
| Missing treatment-session dependency | ADD OWNER DEPENDENCY | `clinic_treatment_session` |
| Customer statements | ENTERPRISE COMPLETION | `clinic.ar.statement*` |
| Integration outbox | ENTERPRISE COMPLETION | `clinic.ar.integration.event` |
| Scaffold controllers/demo/comment-only views | REJECT_WITH_REASON | no business behavior to preserve |
| Small residual write-off policy | PRESERVE + HARDEN | `res.company` + `account.move.action_ar_writeoff_small_residual` |
| Accounting reverse flags/receivable helpers | PRESERVE | `account.move` / `account.move.line` |



