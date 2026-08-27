# ClinicOne clinic_quality — Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- Incident/Investigation/CAPA owner;
- Inventory/stock-lot quality-disposition owner;
- Room/Staff/Doctor/Treatment owner;
- generic Audit owner;
- Integration API owner;
- Analytics owner;
- an endless retry engine.

Preservation rules:
- addon 34 remains owner of `clinic.incident`, Investigation and CAPA;
- `clinic_inventory` remains owner of `stock.lot.clinic_quality_state`,
  `clinic_quarantine_reason`, and Inventory operational workflows;
- `clinic_room_device` remains Room owner;
- `clinic_staff` remains Staff/KPI owner;
- `clinic_doctor` remains Doctor owner;
- `clinic_treatment_catalog` remains Treatment/Catalog owner;
- Quality may link those sources but must not mutate source lifecycle merely to
  make a Quality check pass;
- future `clinic_integration_api`, `clinic_audit`, and `clinic_analytics`
  must not become hard dependencies for convenience.

Forbidden:
- duplicate `_name = "clinic.incident"` or Incident CAPA models;
- duplicate stock-lot quality-state ownership;
- fake external regulator or accreditation submission;
- security implemented only by invisible/read-only UI;
- executable legacy `_sql_constraints`;
- `<tree>`, legacy `attrs=`, legacy `states=`;
- unsafe DB identifiers;
- list-valued `_inherit` without explicit `_name`;
- `self.env["model"]` recordset proxies used as Python `isinstance()` types;
- fragile custom upstream inherited-view XML IDs;
- retrying the same root cause indefinitely.

Retry limit:
- maximum 2 bounded implementation attempts for one verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause / architecture review.
