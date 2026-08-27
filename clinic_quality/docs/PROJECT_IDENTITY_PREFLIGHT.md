# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_quality`
- OFFICIAL SEQUENCE: addon 35 of 39
- OFFICIAL RESPONSIBILITY:
  **Documents standard operating procedures and compliance quality checks.**
- AUTHORITATIVE USER BUNDLE:
  `clinic19a(20260821-080252).md`
- PARSED FILE SECTIONS: **1,608**
- CLINICONE MANIFESTS: **38**
- `clinic_incident_event`: **19.0.1.0.0 / installed upstream**
- `clinic_quality`: **ABSENT / NEW OWNER**
- BUILD TARGET: `clinic_quality 19.0.1.0.0`
- RUNTIME STATUS: **PENDING**

## Quality ownership

Addon 35 owns:
- `clinic.quality.sop`
- `clinic.quality.sop.version`
- `clinic.quality.sop.acknowledgement`
- `clinic.quality.check.template`
- `clinic.quality.check.template.line`
- `clinic.quality.check`
- `clinic.quality.check.line`
- `clinic.quality.schedule`

Addon 35 does not own:
- Incident / Investigation / CAPA;
- generic Audit;
- external Integration API;
- predictive Analytics;
- Inventory Lot quality disposition;
- Room, Staff, Doctor or Treatment master lifecycle.

## Architecture interpretation

The blueprint defines SOP documentation and compliance quality checks but does
not prescribe model names or workflows. This build therefore adds only the
enterprise governance required to make those two responsibilities operational:
versioned SOP evidence, acknowledgement, reusable controls, executable checks,
review/closure, recurring schedules and controlled Incident escalation.
