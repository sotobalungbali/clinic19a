# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_post_care_followup`
- OFFICIAL SEQUENCE: addon 26 of 39
- AUTHORITATIVE BLUEPRINT RESPONSIBILITY:
  - manage post-treatment care instructions;
  - automate patient follow-up reminders.
- AUTHORITATIVE SOURCE BASELINE:
  - user bundle dated 2026-08-20;
  - upstream verified through `clinic_insurance_authorization` 19.0.1.0.1.
- CURRENT RUNTIME STATUS: PENDING.

## Critical historical contract

The installed `clinic_staff` source already exposes:

- `postcare_task_count`;
- `action_open_postcare_tasks()`;
- expected model `clinic.postcare.task`;
- expected assignee field `assignee_id`.

The source also deliberately leaves the actual count integration at zero until
a Post-Care addon exists.

Therefore addon 26 MUST provide the technical model
`clinic.postcare.task` and preserve `assignee_id`.

## Ownership boundary

Addon 26 owns:
- Post-Care Protocol;
- Protocol Step;
- patient Post-Care Plan;
- Post-Care Task;
- Patient Check-in;
- Post-Care Escalation.

Addon 26 does NOT own:
- Encounter;
- Booking;
- Care Plan;
- Staff / roster / assignment / KPI;
- Patient master;
- Insurance;
- future Feedback, Incident, Portal, Marketing, Telemedicine or API modules.
