# ClinicOne clinic_incident_event - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- Patient/Doctor/Staff master owner;
- Encounter or Adverse Event owner;
- eMAR owner;
- Booking/Queue/Room owner;
- Telemedicine or Secure Messaging owner;
- Quality-management owner;
- regulator/API-provider architect;
- generic Audit owner;
- Analytics owner;
- an endless retry engine.

Ownership rules:
- `clinic_encounter` remains owner of `clinic.adverse.event`,
  `clinic.ae.action`, and `clinic.ae.followup`.
- addon 34 owns `clinic.incident`, Incident taxonomy, Investigation,
  Incident CAPA, and Incident timeline evidence.
- `clinic_staff` historical contract `clinic.incident` + `occurred_at` +
  `involved_staff_ids` must be fulfilled exactly.
- Secure Telemedicine message bodies/internal notes must never be copied
  automatically into Incident records.
- future `clinic_quality`, `clinic_integration_api`, `clinic_audit`, and
  `clinic_analytics` must not become dependencies for convenience.

Forbidden:
- duplicate `_name = "clinic.adverse.event"` or `"clinic.ae.action"`;
- upstream workflow overrides that change Encounter/Booking/Queue/eMAR/
  Feedback/Telemedicine state;
- fake regulator transmission;
- security implemented only through invisible/read-only UI attributes;
- executable legacy `_sql_constraints`;
- `<tree>`, legacy `attrs=`, or legacy `states=`;
- unsafe DB identifiers;
- list-valued `_inherit` without explicit `_name`;
- `self.env["model"]` recordset proxies passed as Python `isinstance()` types;
- fragile custom upstream form XML IDs where stable native Odoo boundaries or
  standalone actions are sufficient.

Retry limit:
- maximum 2 bounded implementation attempts for one verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause / architecture review.
