# Cross-Addon Contract Audit

Baseline: ClinicOne source bundle supplied by the user on 2026-08-20.

## `clinic_finance`

Verified:
- `clinic.finance.transaction`
  - `company_id`
  - `transaction_date`
  - `state`
  - `posting_policy`
  - `move_id`
- `clinic.finance.transfer`
  - `company_id`
  - `transfer_date`
  - `state`
  - `move_id`
- `clinic.finance.cash.session`
  - `company_id`
  - `opened_at`
  - `state`

Verified reverse fields already present on `account.move`:
- `clinic_finance_transaction_id`
- `clinic_finance_transfer_id`

Accounting therefore consumes Finance outcomes through the legal Odoo ledger.

## `clinic_billing`

Verified `clinic.billing.invoice`:
- `company_id`
- `invoice_date`
- `state`
- `move_id`

Verified `account.move.clinic_invoice_id`.

## `clinic_ar`

Verified:
- `clinic.ar.invoice.move_id`
- `clinic.ar.payment.move_id`
- `account.move.ar_invoice_ids`
- `account.move.ar_payment_ids`

## `clinic_ap`

Verified:
- `clinic.ap.move_id`
- `account.move.clinic_ap_ids`

## `clinic_wallet`

Verified `clinic.wallet.transaction`:
- `move_id`
- `journal_id`
- `state`
- `date`
- `amount`

Current Wallet source did not own a reverse One2many on `account.move`.
`clinic_accounting` adds only that reverse traceability field and does not move
Wallet transaction ownership.

## `clinic_branch`

Verified:
- `account.move.branch_id`
- `account.move.line.branch_id`
- `res.users.working_branch_id`
- `res.company.default_branch_id`

## Odoo 19 native accounting contracts used

- `res.company.fiscalyear_lock_date`
- `res.company.hard_lock_date`
- `account.account.company_ids`
- `account.account.internal_group`
- `account.move.line.reconciled`

## Boundary results

- duplicated upstream business model ownership: 0
- unknown ClinicOne model reference expected by Accounting: 0
- downstream `clinic_l10n_id` dependency: 0
- fragile upstream custom inherited-view XML ID: 0
- proprietary replacement GL model: 0

These are source/static contract findings. Runtime registry behavior remains a
separate gate.
