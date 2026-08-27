# Cross-addon Audit — 18 Aug 2026

Audit basis: latest supplied ClinicOne snapshot.

- 25 addon folders represented.
- 877 active/non-backup files extracted.
- 133 files ignored because basename begins with digit `0`.
- 27 custom `clinic.*` / `booking.*` comodel references used by final `clinic_package`.
- Missing referenced custom models: 0.
- Missing owning-addon dependencies for those references: 0.
- Dependency cycles detected in the parsed current ClinicOne dependency graph relevant to `clinic_package`: 0.

Verified current-source runtime-safe parent view IDs:
- `clinic_patient.view_clinic_patient_form`
- `clinic_booking.view_booking_booking_form`
- `clinic_care_plan.view_clinic_care_plan_form`
- `clinic_emar.view_emar_order_form`
- `clinic_emar.view_emar_schedule_form`
- `clinic_emar.view_emar_administration_form`
- `clinic_emar.view_emar_prescription_form`

These remain runtime-safe lookups rather than hard load-time cross-addon XML inheritance.
