# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_portal`
- OFFICIAL SEQUENCE: addon 31 of 39
- AUTHORITATIVE BLUEPRINT:
  - **Provides web portal for patients to view bookings, invoices, and treatment history.**
- AUTHORITATIVE UPSTREAM BASELINE:
  - latest user bundle dated 2026-08-21;
  - `clinic_ecommerce` 19.0.1.0.0 installed/frozen.
- CURRENT RUNTIME STATUS: PENDING.

## Ownership boundary

Addon 31 owns:
- the ClinicOne Patient Portal landing page;
- secure portal routes for Booking summaries/details;
- secure portal routes for Clinic Billing summaries/details;
- secure portal routes for completed Treatment History;
- `clinic.portal.profile` application-level access governance;
- portal feature toggles and access telemetry.

Addon 31 does **not** own:
- Odoo authentication or portal invitation;
- Booking workflow/state;
- Clinic Billing or accounting;
- invoice payment/download mechanics;
- Encounter/Procedure workflow;
- clinical SOAP notes, diagnosis, assessments, vitals, or unpublished files;
- Wallet portal requests;
- Consent portal signing;
- eCommerce checkout;
- secure doctor-patient messaging;
- regulatory audit.

Native Odoo `portal.wizard` remains the owner of portal-user grant/revoke/invite.

## Exact-patient security boundary

Healthcare portal data is scoped to the authenticated user's **exact**
`res.partner` / `clinic.patient` linkage. It deliberately does not use broad
commercial-partner family scope, because that could expose another person's
clinical records.
\n## Provisioning default\n\nInstallation seeds Draft profiles for existing patient portal users. Automatic Active-profile creation is opt-in and disabled by default.\n