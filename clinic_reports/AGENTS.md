# ClinicOne `clinic_reports` — Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- owner of report semantics;
- owner of upstream source models;
- an endless retry engine.

Preservation rules:
- Billing remains owned by `clinic_billing`;
- AR remains owned by `clinic_ar`;
- AP remains owned by `clinic_ap`;
- Finance remains owned by `clinic_finance`;
- Accounting remains owned by `clinic_accounting`;
- Tax remains owned by `clinic_l10n_id`;
- Insurance remains owned upstream;
- Booking/Queue/Encounter/Triage/Post-Care/Feedback remain owned upstream;
- source workflows are READ ONLY from this addon;
- future `clinic_dashboard`, `clinic_portal`, `clinic_quality`,
  `clinic_integration_api`, and `clinic_analytics` MUST NOT become dependencies.

Codex must never:
- replace transactional source models with report-owned copies;
- mutate source states to make a report pass;
- delete a report family just to pass tests;
- change KPI definitions without architecture review;
- add future-dashboard coupling;
- reintroduce executable `_sql_constraints`;
- use list-valued `_inherit` without explicit `_name`;
- retry the same root cause indefinitely.

Retry limit:
- maximum 2 bounded implementation attempts per proven defect;
- maximum 1 repeat of the same root cause;
- then STOP and return to root-cause/architecture review.

Odoo 19 contracts:
- use `models.Constraint` / `models.Index`;
- use `res.groups.privilege` / `privilege_id`;
- use `<list>`, never `<tree>`;
- no legacy `attrs=` / `states=`;
- Search `<search>` and its direct `<group>` are attribute-free;
- computed fields used by domains/grouping must be stored or searchable.
