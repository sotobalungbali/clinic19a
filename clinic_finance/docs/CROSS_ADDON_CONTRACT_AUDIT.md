# Cross-Addon Contract Audit

Baseline: user-supplied ClinicOne source bundle dated 2026-08-20, with
`clinic_wallet` installed/frozen and `clinic_finance` not previously present.

## Verified upstream contracts

### `clinic_ar`
`clinic.ar.invoice` exposes:
- `company_id`
- `currency_id`
- `invoice_date`
- `state` with `posted`
- `amount_residual`

`clinic.ar.payment` exists for Finance operational-origin traceability.

### `clinic_ap`
`clinic.ap` exposes:
- `company_id`
- `currency_id`
- `invoice_date`
- `state` with `posted` and `partial`
- `amount_residual`

`clinic.cashflow` exposes:
- `company_id`
- `currency_id`
- `state` with `generated`
- `as_of_date`
- `is_pinned`
- `ending_balance`

Finance links to this forecast; it does not duplicate AP cashflow ownership.

### `clinic_wallet`
`clinic.wallet` exposes:
- `company_id`
- `currency_id`
- `state` with `open` and `suspended`
- `balance`

`clinic.wallet.transaction` exists as an operational-origin model.

### `clinic_branch`
Current branch integration exposes:
- `res.users.working_branch_id`
- `res.company.default_branch_id`
- `account.move.branch_id`
- `account.move.line.branch_id`

### `clinic_billing`
`clinic.billing.invoice` and `clinic.billing.payment` exist and can be used as
operational-origin references without Finance inheriting or duplicating their
business models.

## Boundary result
- Unknown referenced ClinicOne models: **0**
- Future `clinic_accounting` dependency: **0**
- Fragile inherited custom upstream view XML IDs: **0**
- Upstream model ownership duplicated in Finance: **0**

These are source/static findings. Runtime registry/install validation remains a
separate acceptance gate.
