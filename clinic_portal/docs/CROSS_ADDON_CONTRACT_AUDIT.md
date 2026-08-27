# Cross-Addon Contract Audit

Authoritative source: latest ClinicOne bundle supplied on 2026-08-21.

## Baseline

- `clinic_ecommerce`: **19.0.1.0.0**
- `clinic_portal`: absent from baseline -> addon 31 is a new owner.

## Patient identity

`clinic_patient` provides:
- `res.users.patient_id`;
- `res.partner.patient_id`;
- `clinic.patient.partner_id`;
- exact Patient Card / Contact consistency.

Portal does not create a second patient identity.

## Booking

`clinic_booking` owner model:
- `booking.booking`
- patient: `patient_id` -> `res.partner`
- company: `company_id`
- treatment / doctor / room
- `start_datetime`, `end_datetime`
- `state`
- `amount_total`, `currency_id`
- `invoice_id`

Portal routes are read-only against Booking workflow.

## Clinic Billing / Native Accounting Portal

`clinic_billing` owner:
- `clinic.billing.invoice`
- `patient_id`
- `company_id`
- `invoice_date`
- `amount_total`
- `amount_residual`
- `state`
- `move_id`

Portal displays the Clinic Billing summary but hands official invoice
download/payment interaction to the linked native `account.move` portal URL.

## Treatment History

`clinic_encounter` owner:
- `clinic.encounter`
- exact related `partner_id`
- `company_id`
- `date_start`, `date_end`
- `treatment_id`, `doctor_id`
- `amount_total`, `currency_id`
- state `done`

Completed `clinic.procedure.session` records may be shown as procedural history.

The generic portal explicitly excludes:
- SOAP notes;
- assessments;
- diagnosis;
- internal comments;
- triage/vitals;
- unpublished imaging/results;
- staff-only documents.

## Existing companion portal surfaces

`clinic_wallet` already owns:
- `/my/clinic-wallet`

`clinic_consent_legal` already owns:
- `/my/consents`

`clinic_ecommerce` owns:
- `/clinic/shop`

Odoo Sale Portal owns:
- `/my/orders`

Odoo Account Portal owns:
- `/my/invoices`

Addon 31 links to these routes and does not duplicate them.

## Result

- duplicate authentication system: 0
- duplicate Booking workflow: 0
- duplicate invoice/payment portal: 0
- duplicate Encounter workflow: 0
- broad commercial-partner clinical exposure: 0
- future secure-messaging implementation: 0
- future audit ownership: 0
\n## Portal provisioning\n\nNative Portal access alone does not automatically expose treatment history. Existing patient portal users are seeded as Draft Clinic Portal Profiles; staff activation is the default governance path. Optional automatic Active profile creation is disabled by default.\n