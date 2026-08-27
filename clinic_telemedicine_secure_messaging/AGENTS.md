# ClinicOne `clinic_telemedicine_secure_messaging` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- Patient owner;
- Doctor owner;
- Staff/roster owner;
- Booking/Appointment owner;
- Queue owner;
- Encounter/clinical-documentation owner;
- Consent owner;
- Patient Portal authentication owner;
- third-party video-provider architect;
- encryption/key-management architect;
- Incident owner;
- Integration API owner;
- Audit owner;
- an endless retry engine.

Architecture authority:
- `clinic_patient` owns Patient identity.
- `clinic_doctor` owns Doctor, Appointment, telemedicine doctor capability, and schedule.
- `clinic_staff` owns Staff/roster/assignment/KPI and historically expects
  `clinic.telemedicine.thread` with `handler_id`.
- `clinic_booking` owns Booking.
- `clinic_queue_room` owns Queue/Room.
- `clinic_consent_legal` owns legal Consent.
- `clinic_encounter` owns SOAP/diagnosis/clinical documentation.
- `clinic_portal` owns native patient portal profile/authentication boundary.
- addon 33 owns teleconsultation Session, secure Thread, secure Message, and secure Attachment.
- future `clinic_integration_api` may override the video meeting provisioning hook.
- future `clinic_incident_event`, `clinic_quality`, `clinic_audit`, and
  `clinic_analytics` remain downstream owners.

Forbidden:
- exposing a Telemedicine Session/Thread because a browser supplied a valid ID;
- using commercial-partner family scope for patient clinical messaging;
- allowing Portal/Public backend ACL to telemedicine owner models;
- sending secure chat content through generic email/chatter as a substitute for secure messaging;
- claiming end-to-end encryption;
- fabricating a third-party meeting provider;
- mutating Booking/Appointment/Encounter lifecycle from telemedicine merely for convenience;
- storing clinical diagnosis/SOAP notes inside the chat model;
- bypassing `clinic_portal` active profile and explicit feature grants;
- unrestricted file types or unbounded upload size;
- executable legacy `_sql_constraints`;
- `<tree>`, legacy `attrs=`, legacy `states=`;
- unsafe database identifiers or field/method collisions;
- `self.env["model"]` used as an `isinstance()` type;
- future-addon hard dependencies.

Retry limit:
- maximum 2 bounded implementation attempts for one verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause/architecture review.

