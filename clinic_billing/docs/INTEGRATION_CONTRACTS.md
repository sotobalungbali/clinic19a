# Integration Contracts — `clinic_billing`

## Hard upstream dependencies

The manifest owns explicit dependencies for every hard comodel referenced by billing:
- `clinic_patient` → `clinic.patient`
- `clinic_doctor` → `clinic.doctor`
- `clinic_booking` → `booking.booking`
- `clinic_encounter` → `clinic.encounter`
- `clinic_care_plan` → `clinic.care.plan`, `clinic.care.plan.line`
- `clinic_package` → `clinic.package.allocation`, `clinic.package.usage`
- `clinic_emar` → `clinic.emar.administration`
- `clinic_inventory` → `clinic.treatment.product.usage`
- `clinic_room_device` → `clinic.room`, `clinic.device`
- `clinic_treatment_catalog` → `clinic.treatment`
- Odoo `account`, `product`, `stock`, `uom`, `hr`, `mail`, `contacts`

## Clinical traceability

Billing line links are typed and may point to Booking, Encounter, Care Plan/Line, Package Usage, eMAR Administration, Treatment/Product Usage, Room and Device. `clinic.treatment.billing.link` additionally maintains a generic origin identity where preservation requires it.

Duplicate source billing is prevented through source-link ownership/uniqueness logic.

## Accounting contract

`clinic.billing.invoice` is the ClinicOne billing owner. `account.move` remains the legal/accounting ledger owner. Posted moves lock protected ClinicOne financial data; corrections should follow accounting credit-note/correction patterns.

`clinic.billing.payment` orchestrates split payment and creates/links Odoo `account.payment`; Odoo remains the accounting payment owner.

## Wallet/membership

Billing does not hard-depend on a future/downstream wallet addon. If `clinic.wallet` is present, the membership engine calls its supported reserve/release/validate contract. Absence of that model must not break billing registry/install.

## Future AR/AP/Audit/Reports

Billing emits `clinic.billing.integration.event`. Future modules may consume these events. They must not require `clinic_billing` to hard-depend back on them.

## Runtime-safe UI bridge

Smart buttons on Patient, Booking, Encounter, Care Plan, Package Allocation/Usage and eMAR Administration are created only when the target runtime XML ID exists and matches the expected model. Missing/stale external view IDs are logged and skipped safely.



