# CROSS-ADDON CONTRACT AUDIT

The authoritative ClinicOne source was inspected before implementation.

Confirmed contracts used by this addon:

- real Booking model: `booking.booking`;
- Booking patient: `patient_id -> res.partner`;
- Booking doctor: `doctor_id -> clinic.doctor`;
- Clinic Patient owner: `clinic.patient`, linked to Contact by `partner_id`;
- Contact branch scope is supplied by Clinic Branch integration;
- `membership.contract` already carries `referral_id -> clinic.referral`;
- `clinic.treatment.session.line` already carries `referral_id -> clinic.referral`;
- Clinic Audit authoritative evidence model is `clinic.audit.event`;
- stable inherited views exist for Booking, Patient and Branch.

No inverse hard dependency was added to Membership or Treatment Session.


## Authoritative source re-audit — 2026-08-26 02:33:32 snapshot

The full-corrected source was re-audited against `clinic19a(20260826-023332).md`.
All historical fields are preserved. The legacy public `name_get()` methods on
Referral, Program and Source are preserved alongside Odoo 19
`_compute_display_name` implementations. No ClinicOne dependency cycle is
introduced by this addon.

