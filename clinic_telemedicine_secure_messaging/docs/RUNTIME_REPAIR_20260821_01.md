# Runtime Repair 2026-08-21 / 01

## Failed baseline

`clinic_telemedicine_secure_messaging` 19.0.1.0.0

## Runtime error

```text
ValueError:
External ID not found in the system:
clinic_patient.view_clinic_patient_form
```

Failing source:

```xml
<field name="inherit_id"
       ref="clinic_patient.view_clinic_patient_form"/>
```

in:

`views/integration_views.xml`

## Proven root cause

The current source snapshot of `clinic_patient` does contain a record
named `view_clinic_patient_form`, and `patient_views.xml` is present in
its manifest. However, the user's installed Odoo database does **not**
have the corresponding `ir.model.data` external ID.

A dependent addon installation does not automatically upgrade/reload
all data records of an already-installed upstream addon. Therefore a
downstream module must not assume that a newly/currently present custom
upstream XML ID necessarily exists in the runtime database.

This is a **runtime external-ID compatibility defect**, not a missing
model or field contract.

## Repair

The addon no longer inherits:

`clinic_patient.view_clinic_patient_form`

Patient smart navigation is preserved by:
- extending `res.partner` additively with Telemedicine/Secure-Thread
  counters and actions;
- inheriting the stable native Odoo view:
  `base.view_partner_form`;
- showing the buttons only when the Contact has `patient_id`.

No Patient identity ownership, Patient workflow, Telemedicine Session,
Secure Thread, Message, Attachment, Portal, Booking, Appointment,
Encounter, Queue, Consent, or security capability was removed.

## Regression prevention

HARD GATE 12 now rejects
`clinic_patient.view_clinic_patient_form` from addon-33 integration XML.

The repair package permits only:
- `clinic_booking.view_booking_booking_form`, already proven to resolve
  earlier in the same runtime installation attempt; and
- stable native `base.view_partner_form`.

## Repair target

`clinic_telemedicine_secure_messaging` 19.0.1.0.1

Runtime status remains PENDING until activation succeeds.
