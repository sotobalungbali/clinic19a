# ClinicOne `clinic_feedback` — Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- owner of model/dependency decisions;
- owner of Booking/Queue/Encounter/Post-Care workflow;
- an endless retry engine.

Preservation rules:
- `booking.feedback.link` remains owned by `clinic_booking`;
- Booking remains owned by `clinic_booking`;
- Queue remains owned by `clinic_queue_room`;
- Encounter remains owned by `clinic_encounter`;
- Post-Care remains owned by `clinic_post_care_followup`;
- Staff/Doctor/Patient masters remain owned upstream;
- future `clinic_incident_event`, `clinic_reports`, `clinic_dashboard`,
  `clinic_marketing`, `clinic_portal`, and `clinic_integration_api`
  MUST NOT become dependencies.

Codex must never:
- delete survey, response, escalation or source integration just to pass tests;
- redefine `booking.feedback.link`;
- create a parallel Patient, Doctor, Staff, Booking, Queue or Encounter master;
- invent SMS/WhatsApp/API delivery without the future provider addon;
- automatically create a future Incident record;
- bypass backend workflow/security because a button is hidden;
- reintroduce executable `_sql_constraints`;
- use list-valued `_inherit` without explicit `_name`.

Retry limit:
- maximum 2 bounded implementation attempts per proven defect;
- maximum 1 repeat of the same root cause;
- then STOP and return to architecture/root-cause review.

Odoo 19 contracts:
- use `models.Constraint` / `models.Index`;
- use `res.groups.privilege` / `privilege_id`;
- use `<list>`, never `<tree>`;
- no legacy `attrs=` / `states=`;
- Search `<search>` and its direct `<group>` are attribute-free;
- computed fields used by domains/grouping must be stored or searchable.
