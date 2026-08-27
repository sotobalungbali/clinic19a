# ClinicOne `clinic_post_care_followup` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- owner of model/dependency decisions;
- owner of clinical follow-up policy;
- endless retry engine.

Existing Function Preservation:
- Encounter remains owned by `clinic_encounter`.
- Booking remains owned by `clinic_booking`.
- Care Plan remains owned by `clinic_care_plan`.
- Staff / roster / assignment / KPI remain owned by `clinic_staff`.
- Insurance remains owned by `clinic_insurance_authorization`.
- Future `clinic_feedback`, `clinic_incident_event`,
  `clinic_telemedicine_secure_messaging`, `clinic_portal`,
  `clinic_marketing`, and `clinic_integration_api` MUST NOT become dependencies.
- This addon satisfies the historical `clinic.postcare.task` model contract
  anticipated by `clinic_staff`; it must not rename that technical model.

Codex must never:
- delete reminder/check-in/escalation functionality just to pass a test;
- replace clinical Encounter or Care Plan workflow;
- silently mark a patient contacted when no contact channel was actually sent;
- pretend SMS/WhatsApp/API delivery without an installed provider;
- bypass backend workflow/security because UI hides a button;
- create an Incident in a future addon that is not installed;
- reintroduce executable `_sql_constraints`;
- use list-valued `_inherit` without explicit `_name`.

Retry limit:
- maximum 2 bounded implementation attempts for one proven defect;
- maximum 1 repeat of the same root cause;
- then STOP and return to root-cause/architecture review.

Odoo 19:
- `models.Constraint` / `models.Index`;
- `res.groups.privilege` / `privilege_id`;
- `<list>`, not `<tree>`;
- no legacy `attrs=` / `states=`;
- Search `<search>` and direct child `<group>` are attribute-free;
- computed fields used in search domains must be stored or implement search.
