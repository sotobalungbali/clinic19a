# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_insurance_authorization`
- OFFICIAL SEQUENCE: addon 25 of 39
- BLUEPRINT RESPONSIBILITY:
  - insurance policies;
  - pre-authorization;
  - claim processing.
- AUTHORITATIVE BASELINE: user-supplied ClinicOne bundle dated 2026-08-20
- VERIFIED UPSTREAM THROUGH: `clinic_l10n_id` 19.0.1.0.1

## Critical pre-existing ownership

The latest installed baseline already defines:

- `clinic.insurance.claim`
- `clinic.insurance.claim.line`

inside `clinic_billing`.

Those models are frozen upstream ownership and MUST NOT be moved, renamed,
redefined, or replaced by this addon.

This addon owns Policy, Plan, Eligibility and Authorization, then extends the
Billing claim models to integrate those objects into claim processing.

## Historical Queue/Room insurance bridge source

The latest Queue/Room bundle still contains insurance fields in historical
`appointment_inherit.py`, `treatment_inherit.py`, and `res_partner_inherit.py`,
but all three imports are commented out in `models/__init__.py`.

Therefore addon 25 must supply both:
- the live Partner/Appointment/Treatment insurance bridge fields; and
- the referenced `clinic.insurance.policy` / `clinic.insurance.authorization`
  technical models.

## Explicit anticipated Patient action XML IDs

The historical Patient source anticipated:

- `clinic_insurance_authorization.action_clinic_insurance_authorization`
- `clinic_insurance_authorization.action_clinic_insurance_authorization_from_patient`

Both are provided.

## Runtime status

SOURCE / STATIC: under validation  
ODOO RUNTIME: PENDING

