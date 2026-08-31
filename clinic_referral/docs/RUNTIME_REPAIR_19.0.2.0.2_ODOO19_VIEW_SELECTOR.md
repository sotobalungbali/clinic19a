# Runtime Repair 19.0.2.0.2 — Odoo 19 View Selector Safety

## Concrete runtime evidence

Upgrading `clinic_referral` reached XML view validation and failed on:

`View inheritance may not use attribute 'string' as a selector.`

The failing expression was:

`//group[@string='Patient & Clinical']`

inside the inherited Booking form.

## Root cause

`string` is a translatable display label and Odoo 19 explicitly rejects it as
a view inheritance selector. It is not a stable structural contract.

## Repair

The Booking integration now anchors on the technical field:

`//form//field[@name='patient_id']`

and inserts Referral attribution immediately after that field.

The authoritative `clinic_booking.view_booking_booking_form` contains the
canonical `patient_id` field in the Patient/Clinical group, so the resulting UI
placement is preserved without relying on a display label.

## Scope audit

All `clinic_referral` XML files were scanned after the repair. No inherited
`<xpath>` expression contains `@string`.

No Python business workflow, schema, ACL, rule, sequence, migration, booking
model ownership, or downstream dependency is changed in this release.

