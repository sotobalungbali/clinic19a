# Latest Baseline Audit — 2026-08-21

Authoritative bundle: `clinic19a(20260821-063228).md`.

## Result

- file sections: **1,562**
- ClinicOne manifests: **37**
- addon 33: `clinic_telemedicine_secure_messaging 19.0.1.0.1`
- addon 34: **ABSENT / NEW OWNER**

Only live-imported source is authoritative. Numeric-prefix backup files are
ignored. Nested Python packages are followed recursively, including the current
`clinic_emar/models/core` and `models/integrations` import graph.

## Critical ownership result

`clinic_encounter` already owns:
- `clinic.adverse.event`
- `clinic.ae.action`
- `clinic.ae.followup`
- Adverse Event taxonomy/classification/severity
- clinical CAPA/follow-up evidence.

Addon 34 therefore links and escalates those records into a central
`clinic.incident` rather than duplicating them.
