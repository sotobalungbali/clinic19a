# Cross-Addon Contract Audit

## `clinic_staff`

Live historical contract:
- `telemed_thread_count`
- `clinic.telemedicine.thread`
- `handler_id`
- `action_open_telemedicine_threads`

Addon 33 fulfils this exact contract and does not move Staff/roster ownership.

## `clinic_doctor`

Consumed live contracts:
- `clinic.doctor.company_id`
- `clinic.doctor.partner_id`
- `clinic.doctor.user_id`
- `clinic.doctor.active`
- `clinic.doctor.telemedicine_enabled`

`clinic.appointment` consumed contracts:
- patient Contact + Patient Card;
- Doctor;
- `telemedicine`;
- `start` / `end`;
- lifecycle states including `draft`, `confirmed`, `checked_in`,
  `in_treatment`, `done`, `no_show`, `canceled`.

Appointment uses **`canceled`** with one `l`.

Addon 33 creates/links a Session but does not override Appointment workflow.

## `clinic_booking`

Consumed:
- `booking.booking.patient_id -> res.partner`
- `doctor_id -> clinic.doctor`
- `appointment_id -> clinic.appointment`
- `start_datetime`, `end_datetime`
- states including `draft`, `confirmed`, `in_progress`, `done`, `cancelled`.

Booking uses **`cancelled`** with two `l`.

Addon 33 can create one Session from an eligible Booking and can reuse an
Appointment-created Session. It does not alter Booking state.

## `clinic_queue_room`

Addon 33 activates the historical technical relation:
- `clinic.queue.telemedicine_session_id -> clinic.telemedicine.session`

Queue lifecycle remains owned by `clinic_queue_room`.

## `clinic_consent_legal`

Consumed:
- `clinic.consent.form.patient_id -> res.partner`
- company;
- Doctor/Encounter linkage;
- lifecycle including `signed`.

Company policy may require a signed linked Consent before a Session reaches
Ready. Consent ownership/signing remains upstream.

## `clinic_encounter`

Consumed:
- exact `patient_id -> clinic.patient`
- Contact relation;
- Doctor;
- company.

Addon 33 adds reverse Session navigation only. SOAP notes, diagnosis,
assessment, treatment documentation, prescriptions, and clinical record
workflow remain Encounter/eMAR-owned.

## `clinic_portal`

Frozen addon 31 remains Patient Portal authentication/profile owner.

Addon 33 extends `clinic.portal.profile` with two explicit grants:
- `allow_telemedicine_access`
- `allow_secure_messaging`

Both default to **False**.

All patient-facing Session/Thread IDs are intersected with:
- active Clinic Portal Profile;
- exact Patient Contact;
- exact Company;
- explicit feature grant.

No `commercial_partner_id` family scope is used for clinical communication.

## Future owners

No hard dependency on:
- `clinic_incident_event`
- `clinic_quality`
- `clinic_integration_api`
- `clinic_audit`
- `clinic_analytics`

Future `clinic_integration_api` may override meeting-provider provisioning but
addon 33 remains installable without it.

