# Cross-Addon Contract Audit

Authoritative baseline: ClinicOne bundle supplied 2026-08-20.

## `clinic_billing`

Already owns:
- `clinic.insurance.claim`
- `clinic.insurance.claim.line`
- claim sequence `clinic.insurance.claim`
- claim settlement through `clinic.billing.payment`
- invoice insurance hints:
  - `insurer_partner_id`
  - `insurance_policy_number`
  - `insurance_coverage_percent`
  - `insurance_copay_percent`
  - `insurance_claim_state`

Result:
- ownership moved: **0**
- settlement ledger duplicated: **0**
- existing claim lifecycle removed: **0**

New addon only extends structured Policy/Authorization/payer evidence.

## `clinic_queue_room`

The latest source bundle still contains historical insurance bridge
definitions in:

- `models/appointment_inherit.py`
- `models/treatment_inherit.py`
- `models/res_partner_inherit.py`

However, **all three imports are commented out** in the current
`clinic_queue_room/models/__init__.py`. They are therefore dead source and are
not runtime contracts.

`clinic_insurance_authorization` now owns the live bridge fields it requires:

- `clinic.appointment.insurance_policy_id`
- `clinic.appointment.authorization_id`
- `clinic.treatment.insurance_policy_id`
- `clinic.treatment.authorization_id`
- `res.partner.insurance_policy_id`

This preserves `clinic_queue_room` without re-enabling historical integration
files.

The addon also defines the referenced technical models:

- `clinic.insurance.policy`
- `clinic.insurance.authorization`

## `clinic_patient`

Historical Patient source contains disabled/anticipated integration with:
- model `clinic.insurance.authorization`;
- action XML IDs ending in:
  - `action_clinic_insurance_authorization`;
  - `action_clinic_insurance_authorization_from_patient`.

Both action contracts are supplied.

## `clinic_booking`

Verified `booking.booking`:
- patient is `res.partner`;
- `line_ids` use `booking.line`;
- line service context includes product/treatment/quantity/price/subtotal.

The addon adds structured Policy and Authorization fields and can prepare
Authorization service lines from Booking lines.

## `clinic_encounter`

Verified:
- Patient model is `clinic.patient`;
- procedures are `clinic.encounter.procedure`;
- procedure lines provide procedure/product/treatment/quantity/price/subtotal.

The addon adds Policy/Authorization links and prepares request lines from
Encounter procedures.

## `clinic_treatment_catalog`

Verified:
- `clinic.treatment.catalog`;
- `clinic.procedure.catalog`;
- service product links;
- `insurance_applicable` exists in the treatment catalog baseline.

Benefit rules reference those existing service catalogs instead of duplicating
a treatment master.

## Finance / Accounting / Localization

Claim settlement remains in Billing, which already integrates with accounting.
No insurance-specific parallel payment/accounting ledger is created.
`clinic_accounting` and `clinic_l10n_id` ownership is preserved.

## Cross-addon result

- missing required upstream technical models: 0
- unresolved live Insurance bridge contracts after this addon: 0
- duplicated Billing Claim ownership: 0
- parallel insurance accounting ledger: 0
- future addon dependency: 0

