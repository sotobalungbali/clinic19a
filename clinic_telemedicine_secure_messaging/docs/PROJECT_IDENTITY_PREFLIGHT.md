# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_telemedicine_secure_messaging`
- OFFICIAL SEQUENCE: addon 33 of 39
- AUTHORITATIVE BLUEPRINT:
  - **Teleconsultation and secure doctor-patient chat system with file sharing.**
- AUTHORITATIVE LATEST BASELINE:
  - `clinic19a(20260821-031223).md`
  - 1,561 parsed file sections
  - 37 ClinicOne addon manifests
  - `clinic_portal`: 19.0.1.0.0 installed/frozen
  - `clinic_marketing`: 19.0.1.0.1 installed/frozen
  - `clinic_telemedicine_secure_messaging`: 19.0.1.0.0 present as failed runtime baseline
- FAILED RUNTIME BASELINE: `clinic_telemedicine_secure_messaging` 19.0.1.0.0
- REPAIR TARGET: `clinic_telemedicine_secure_messaging` 19.0.1.0.1
- CURRENT RUNTIME STATUS: PENDING.

## Ownership boundary

Addon 33 owns:
- Telemedicine Session lifecycle/provenance;
- exact-patient Secure Messaging Thread;
- immutable Secure Message evidence;
- secure file-sharing evidence;
- explicit Patient Portal Telemedicine/Messaging feature grants;
- patient join-window authorization;
- provider-neutral meeting provisioning extension hook.

Addon 33 does **not** own:
- Patient identity;
- Doctor registry/scheduling capability;
- Staff/roster/KPI architecture;
- Booking or Appointment lifecycle;
- Queue lifecycle;
- clinical Encounter/SOAP/diagnosis;
- legal Consent model;
- Clinic Portal authentication/profile lifecycle;
- third-party video conferencing provider;
- encryption/key management;
- Incident, Quality, Integration API, Audit, or Analytics.

## Security language

The product term **Secure Messaging** means authenticated and authorized
application access with exact-patient/company isolation and controlled file
delivery. This addon does **not** claim end-to-end encryption. Deployment still
requires HTTPS/TLS and appropriate database/filestore/server security.

