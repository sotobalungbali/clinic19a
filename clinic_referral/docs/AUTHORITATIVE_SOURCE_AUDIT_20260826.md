# AUTHORITATIVE SOURCE AUDIT — 2026-08-26

- Snapshot: `clinic19a(20260826-023332).md`
- SHA-256: `530110d5809e5c8fe8f0331c633839fe7471884e67cc3a24f5d6d47fc538d924`
- Valid ClinicOne manifests: **41**
- Replacement dependency cycles: **0**

## Legacy contract preservation

- `clinic.referral` — missing fields: `NONE`; missing methods: `NONE`
- `clinic.referral.program` — missing fields: `NONE`; missing methods: `NONE`
- `clinic.referral.source` — missing fields: `NONE`; missing methods: `NONE`

## Upstream field contracts

- `booking.booking` — required fields `patient_id, doctor_id, company_id` — **PASS**
- `clinic.patient` — required fields `partner_id, company_id` — **PASS**
- `clinic.doctor` — required fields `company_id` — **PASS**
- `clinic.branch` — required fields `company_id` — **PASS**
- `membership.contract` — required fields `referral_id` — **PASS**
- `clinic.treatment.session.line` — required fields `referral_id, session_id` — **PASS**
- `clinic.audit.event` — required fields `ref_model, ref_res_id, company_id, branch_id` — **PASS**
- `res.partner` — required fields `patient_id, branch_id` — **PASS**

## External XML IDs

- `clinic_booking.view_booking_booking_form` — **PASS**
- `clinic_booking.view_booking_booking_search` — **PASS**
- `clinic_patient.view_clinic_patient_form` — **PASS**
- `clinic_branch.view_clinic_branch_form` — **PASS**
- `clinic_patient.menu_root` — **PASS**

## Dependency direction

- `clinic_treatment_session` depends on `clinic_referral`: **YES**
- `clinic_membership` depends on `clinic_referral`: **YES**
- The full-corrected `clinic_referral` does not depend on those downstream addons.

## Baseline defects confirmed and corrected

- Historical manifest loaded security ACL: **NO**.
- Historical referral sequence data was not loaded by the manifest.
- Historical booking counter referenced `clinic.booking`; actual owner model is `booking.booking`.
- Runtime legacy `_sql_constraints` files: `['models/referral_source.py']`.
- Full-corrected build loads security, sequences and cron; uses `booking.booking`; and converts the source uniqueness rule to Odoo 19 `models.Constraint`.

## Result

**PASS** — latest source contracts required by the addon are present; historical owned fields/methods are preserved; no custom dependency cycle is introduced.

