# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- Project: **ClinicOne**
- Platform: **Odoo 19 Community Edition**
- Addon: `clinic_referral`
- Source-actual order: **#40 / 41**
- Authoritative baseline: `clinic19a(20260826-023332).md`
- Baseline draft version: `19.0.1.0.0`
- Full-corrected version: `19.0.2.0.5`
- Build mode: **Direct Full Addon Build**

The baseline already contained an incomplete historical `clinic_referral` draft.
That draft is treated as a preservation contract, not as a finished addon.

Dependency direction is non-negotiable:

- `clinic_treatment_session` consumes `clinic_referral`;
- `clinic_membership` consumes `clinic_referral` and Treatment Session.

Therefore neither downstream addon is a hard dependency of this module.

