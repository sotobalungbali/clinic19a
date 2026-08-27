# Latest Baseline + Addon 33 Combined Contract Audit

Authoritative user bundle:
`clinic19a(20260821-031223).md`

## Baseline identity

- parsed sections: 1561
- ClinicOne manifests: 37
- clinic_portal: 19.0.1.0.0
- clinic_marketing: 19.0.1.0.1
- clinic_telemedicine_secure_messaging in baseline: 19.0.1.0.0 (failed runtime baseline)
- addon 33 repair target: 19.0.1.0.1

## Dependency / ownership result

- direct ClinicOne dependencies available: 10/10
- duplicate Telemedicine owner models in baseline: 0
- future-addon hard dependencies: 0
- numeric-prefix backup files shipped: 0

## Live source contracts

PASS:
- historical clinic_staff `telemed_thread_count`;
- historical `clinic.telemedicine.thread` + `handler_id` expectation;
- Doctor `telemedicine_enabled`;
- Patient exact Contact/Card contract;
- Appointment Patient/Doctor/Telemedicine/start/end/state contract;
- Booking Patient/Doctor/Appointment/start/end/state contract;
- Queue -> Telemedicine Session extension contract;
- Encounter Patient/Card contract;
- Consent Patient Contact + Signed workflow;
- Clinic Portal Profile exact Patient/Company contract;
- Company `policy_branch_scope_telemedicine`.

Important spelling preserved:
- Appointment terminal state: `canceled`
- Booking terminal state: `cancelled`

## View integration

PASS:
- `clinic_booking.view_booking_booking_form` exists and has Header/Button Box anchors;
- `clinic_patient.view_clinic_patient_form` exists and has Button Box anchor;
- all addon-owned/inherited View field references resolve against the combined graph;
- all `type="object"` button methods resolve;
- nested One2many model switching resolves.

## Patient Portal / security

PASS:
- active Clinic Portal Profile required;
- explicit Teleconsultation grant required;
- explicit Secure Messaging grant required;
- grants default False;
- browser Session/Thread ID intersected with exact Patient + Company domain;
- no commercial-partner family scope;
- controlled patient read/join evidence includes exact patient context;
- HTTPS external meeting redirect uses native Odoo 19 `request.redirect(..., local=False)`.

## Secure communication/file handling

PASS:
- no generic chatter/email duplication of secure message body;
- immutable message evidence;
- immutable attachment evidence;
- PDF/JPEG/PNG allowlist;
- MIME + extension + binary magic-signature validation;
- configured size ceiling;
- SHA-256 evidence;
- authorization-controlled download;
- no-cache/nosniff response controls;
- no unsupported end-to-end-encryption claim.

## Enterprise Development Guardrail

HARD GATE 0-15: PASS (source/static only)

Runtime contract/regression tests declared: 507

**Odoo runtime install and smoke testing remain PENDING.**


## Runtime XML-ID compatibility repair

- failed external ID: `clinic_patient.view_clinic_patient_form`
- current source contains that ID, but installed DB does not
- downstream dependency removed
- Patient smart navigation preserved on stable `base.view_partner_form`
