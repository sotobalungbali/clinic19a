# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_incident_event`
- OFFICIAL SEQUENCE: addon 34 of 39
- OFFICIAL RESPONSIBILITY:
  - log adverse events;
  - log clinical incidents;
  - govern corrective actions for compliance.
- AUTHORITATIVE LATEST USER BUNDLE:
  - `clinic19a(20260826-001541).md`
  - **1,562 parsed file sections**
  - **37 ClinicOne addon manifests**
  - `clinic_inventory`: 19.0.1.0.2
  - `clinic_reports`: 19.0.1.0.0
  - `clinic_dashboard`: 19.0.1.0.0
  - `clinic_ecommerce`: 19.0.1.0.0
  - `clinic_portal`: 19.0.1.0.0
  - `clinic_marketing`: 19.0.1.0.1
  - `clinic_telemedicine_secure_messaging`: **19.0.1.0.1**
  - `clinic_incident_event`: **ABSENT**
- BUILD TARGET: `clinic_incident_event` 19.0.1.0.1 runtime repair
- RUNTIME STATUS: PENDING after Odoo User Settings privilege-label repair.

## Ownership boundary

Addon 34 owns:
- `clinic.incident`;
- `clinic.incident.category`;
- `clinic.incident.investigation`;
- `clinic.incident.action`;
- `clinic.incident.timeline`.

Addon 34 does not own:
- Patient, Doctor or Staff masters;
- Booking, Queue, Room or Encounter workflows;
- `clinic.adverse.event`;
- `clinic.ae.action`;
- `clinic.ae.followup`;
- eMAR Administration;
- Feedback Escalation;
- Telemedicine Session/Thread or Secure Message content;
- future Quality, Integration API, generic Audit or Analytics ownership.

## Historical compatibility

Live `clinic_staff` source already anticipates:
- model `clinic.incident`;
- field `occurred_at`;
- field `involved_staff_ids`;
- Staff `incident_count`;
- KPI `incidents_count`;
- KPI `incidents_rate_per_100_assign`.

Addon 34 fulfils those contracts rather than inventing replacement names.

## Runtime Repair 19.0.1.0.1 — User Settings

The authoritative 2026-08-26 snapshot and the browser traceback show that
the Odoo 19 dynamic User Access Rights template receives the database label
`ClinicOne Incident & Event`. The raw ampersand makes the generated XML
template invalid. The module category and privilege labels are therefore
renamed to `ClinicOne Incident and Event`. External IDs and access hierarchy
are unchanged.
