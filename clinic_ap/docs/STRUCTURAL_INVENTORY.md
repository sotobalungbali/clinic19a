# Structural Inventory — `clinic_ap` 19.0.3.0.0

## Persistent owner models
1. `clinic.ap`
2. `clinic.ap.line`
3. `clinic.ap.aging`
4. `clinic.ap.aging.line`
5. `clinic.cashflow`
6. `clinic.cashflow.bucket`
7. `clinic.cashflow.detail`
8. `clinic.cashflow.adjustment`
9. `clinic.ap.integration.event`

## Standard/ClinicOne model extensions
- `res.company`, `res.config.settings`, `res.partner`
- `account.payment.term`, `account.move`, `account.payment`
- `purchase.order`, `stock.move`
- `clinic.billing.invoice`, `clinic.billing.line`
- `clinic.ap` runtime view bridge helper

## Core workflows
- AP: Draft → To Approve → Approved → Posted → Partially Paid / Paid; Cancelled with controlled reset
- Aging: Draft → Generated → Archived
- Cashflow: Draft → Generated → Archived
- Integration event: Pending → Processed / Failed with bounded retry

## Scheduled jobs
- AP payment-state synchronization
- refresh pinned AP aging snapshots
- refresh pinned cashflow forecasts

## Security
- AP User
- AP Accountant
- AP Manager
- company-scoped record rules on all 9 persistent owner models

