# Cross-Addon Contract Audit

## Patient identity — `clinic_patient`

Marketing audiences are `clinic.patient` records and retain exact
`clinic.patient.partner_id -> res.partner` ownership.

Patient source fields consumed:
- `company_id`
- `partner_id`
- `stage_id`
- `tag_ids`
- `gender`
- `birth_date` (age boundaries via `dateutil.relativedelta`)
- `email`, `mobile`, `phone`
- `active`

Partner source fields consumed:
- `is_patient`
- `patient_id`
- `branch_id`
- native Odoo `email`, `phone`
- `mobile` is intentionally read from `clinic.patient.mobile` because this ClinicOne/Odoo 19 baseline does not rely on `res.partner.mobile`

## Branch — `clinic_branch`

Marketing enforces `res.company.policy_branch_scope_marketing` in Python.
A Branch selected on Campaign/Segment/Promotion must belong to the same company.

## Behavior — `clinic_booking`

Only completed Booking history is used for segmentation:
- `booking.booking.patient_id -> res.partner`
- `company_id`
- `start_datetime`
- `state = done`

Marketing does not change Booking state.

## Membership — `clinic_membership`

Active membership segmentation consumes:
- `membership.contract.patient_id -> clinic.patient`
- `company_id`
- `plan_id`
- `state = active`

Marketing does not create/renew/activate membership contracts.

## Feedback — `clinic_feedback`

The latest Feedback record may provide NPS Promoter/Detractor segmentation:
- `patient_id -> res.partner`
- `submitted_at`
- stored `nps_class`
- submitted/review/escalated/closed workflow states

Marketing does not alter Feedback.

## Promotion source owners

A Promotion is a presentation wrapper and never computes a commercial discount.

Supported owner references:
- `clinic.billing.voucher.program`
- `clinic.package.voucher.batch`
- `clinic.treatment.pricelist.item`
- `clinic.ecommerce.catalog.item`

The owner record remains authoritative for pricing/eligibility/redemption.

## Email Marketing — Odoo `mass_mailing`

`mailing.mailing` is extended only with
`clinic_marketing_campaign_id` provenance.

Email recipients are selected through the linked
`res.partner.clinic_marketing_recipient_ids` snapshot and native mailing domain.
Odoo owns:
- exclusion list / global blacklist behavior;
- email queue/send;
- opens;
- clicks;
- replies;
- bounces;
- mailing state.

## Existing patient surfaces

`clinic_portal` and `clinic_ecommerce` remain independent patient-facing owners.
Marketing may promote an eCommerce Catalog Item but does not alter its checkout
or fulfillment lifecycle.

## Result

- duplicate patient model: 0
- duplicate Booking workflow: 0
- duplicate pricing/voucher engine: 0
- duplicate email delivery engine: 0
- third-party WhatsApp dependency: 0
- future-addon hard dependency: 0

### Billing Voucher Program runtime detail

The current owner contract uses `active`, `date_start`, and `date_end`; it does **not** define a Program `state` field. Marketing therefore never references a fabricated Billing Voucher Program state.

