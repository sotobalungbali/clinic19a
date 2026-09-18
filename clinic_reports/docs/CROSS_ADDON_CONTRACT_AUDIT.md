# Cross-Addon Contract Audit

Authoritative source: latest ClinicOne bundle supplied on 2026-08-20.

## Upstream baseline

`clinic_feedback` version: **19.0.1.0.0**

`clinic_reports` was absent from the baseline and is therefore created as a new
owner addon.

## Financial source contracts

### `clinic_billing`
Report source:
- `clinic.billing.invoice`
- `invoice_date`
- states `posted` / `paid`
- `amount_untaxed`, `amount_tax`, `amount_total`, `amount_residual`
- `patient_id`, `clinic_patient_id`, `clinic_doctor_id`
- `move_id`

Branch scope:
- authoritative through `move_id.branch_id` from `clinic_branch`.

### `clinic_ar`
Report source:
- `clinic.ar.invoice`
- `invoice_date`, `due_date`
- `amount_total`, `amount_paid`, `amount_residual`
- stored `is_overdue`, `days_overdue`, `aging_bucket`
- `move_id`

Branch scope:
- authoritative through `move_id.branch_id`.

### `clinic_ap`
Report source:
- `clinic.ap`
- `invoice_date`, `invoice_date_due`
- `amount_total`, `amount_paid`, `amount_residual`
- `vendor_id`, `move_id`

Branch scope:
- authoritative through `move_id.branch_id`.

### `clinic_finance`
Report source:
- `clinic.finance.transaction`
- `transaction_date`
- `direction`
- `amount`
- state `posted`
- company/branch source contract.

### `clinic_accounting`
Central report uses posted Odoo `account.move.line` journal items.
`clinic_branch` already extends `account.move.line` with `branch_id`.

No accounting entries are created or changed by Reports.

### `clinic_l10n_id`
Report source:
- `clinic.l10n.id.tax.report`
- `date_from`, `date_to`
- `output_tax`, `input_tax`, `net_ppn`
- `branch_ids`
- states `generated` / `locked`.

### Insurance
Report sources:
- `clinic.insurance.authorization`
- `clinic.insurance.claim`.

Authorization branch scope uses its direct branch contract.
Claim branch scope follows its authorization relationship.

## Operational source contracts

### Booking
`booking.booking`:
- `start_datetime`, `end_datetime`, `duration_minutes`
- `state`
- `amount_total`
- Patient, Doctor and Treatment links.

The current Booking model does not have an authoritative branch field, so the
Booking report intentionally disables Branch filtering rather than inferring a
branch from a Patient or Room.

### Queue
`clinic.queue`:
- `checkin_time`, `start_time`, `end_time`
- stored `waiting_duration_min`, `service_duration_min`
- `sla_wait_breached`
- `state`
- Patient / Treatment / Room.

No authoritative Queue branch field exists in the current live source.
Branch filtering is therefore disabled for this report.

### Room
`clinic.room.assignment`:
- `assigned_at`
- `room_id`
- stored waiting/service/occupancy durations
- operational state.

The current Room/Assignment source is company-scoped but has no authoritative
branch field.  Reports does not fabricate one.

### Inventory
`clinic.treatment.product.usage`:
- `date_usage`
- state `done`
- usage lines and quantity
- `warehouse_id`.

Branch scope uses `warehouse_id.branch_id`, an explicit Clinic Branch contract.

### Membership / Wallet
`membership.contract` and `clinic.wallet.transaction` are company-scoped.
Current source does not expose authoritative transaction branch fields, so
their built-in reports disable Branch filtering.

## Clinical source contracts

- `clinic.encounter`
- `clinic.procedure.session`
- `clinic.triage.session`
- `clinic.adverse.event`
- `clinic.postcare.plan`
- `clinic.feedback`.

Only Post-Care and Feedback expose direct authoritative branch fields in the
current baseline.  The other clinical report definitions therefore disable
Branch filtering rather than guessing from Patient/Room.

## Clinic Branch policy

`res.company.policy_branch_scope_reports` is respected by backend validation.
If the company disables report branch scoping, a user cannot force a Branch
through RPC.

## Future Dashboard

No source KPI is mutated merely for dashboard convenience.

`clinic.report.metric` is the stable normalized downstream contract.  This
prevents addon 28 from taking ownership of `clinic_doctor` KPI fields or future
Dashboard models.

## Controlled reporting read authority

Report generation is restricted to `Reports Analyst` / `Reports Manager`.
The engine performs source **reads under sudo only after constructing an
explicit company/date/authoritative-branch domain**.  This avoids requiring a
reporting analyst to receive write/operational roles from every transactional
addon.  Source records are never created, written, or deleted by report engines.

Source drill-down does **not** use sudo: opening the original transaction still
requires the current user's normal source-model read access.

## Source authority

Source records remain authoritative. Report snapshots are downstream evidence only and never become the owner of Billing, Finance, Operational, or Clinical transactions.

## Result

- duplicated upstream ownership: 0
- source-state mutation: 0
- fabricated Branch semantics: 0
- future addon hard dependencies: 0

