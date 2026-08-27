# Latest Baseline Audit - 2026-08-21

Authoritative attached bundle:
`clinic19a(20260821-031223).md`

## Parsed baseline

- file sections: **1,561**
- ClinicOne addon manifests: **37**
- `clinic_inventory`: 19.0.1.0.2
- `clinic_reports`: 19.0.1.0.0
- `clinic_dashboard`: 19.0.1.0.0
- `clinic_ecommerce`: 19.0.1.0.0
- `clinic_portal`: 19.0.1.0.0
- `clinic_marketing`: 19.0.1.0.1
- `clinic_telemedicine_secure_messaging`: **19.0.1.0.0 (FAILED RUNTIME BASELINE)**

Therefore 19.0.1.0.1 is a surgical runtime repair of the existing addon-33 owner source, not a re-architecture.

## Live-import policy

Only source imported by each existing addon's `models/__init__.py` is treated
as an authoritative runtime contract. Numeric-prefix backup files remain
excluded.

## Historical live contract found

`clinic_staff` already has a live historical Telemedicine placeholder:
- `telemed_thread_count`;
- access to `self.env["clinic.telemedicine.thread"]`;
- `action_open_telemedicine_threads()`;
- domain by `handler_id`.

Addon 33 deliberately supplies the exact expected model:
`clinic.telemedicine.thread`

and the exact expected field:
`handler_id -> clinic.staff`.

The Staff override calls `super()._compute_counts()` first and replaces only the
historical Telemedicine zero, preserving every other Staff/Post-Care counter.

