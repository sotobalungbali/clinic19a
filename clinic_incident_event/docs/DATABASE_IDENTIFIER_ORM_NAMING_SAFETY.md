# HARD GATE 11 — Database Identifier & ORM Naming Safety

Owned model/table names:

- `clinic.incident.category` -> `clinic_incident_category`
- `clinic.incident` -> `clinic_incident`
- `clinic.incident.investigation` -> `clinic_incident_investigation`
- `clinic.incident.action` -> `clinic_incident_action`
- `clinic.incident.timeline` -> `clinic_incident_timeline`

Guardrail checks:
1. lowercase dotted model names;
2. PostgreSQL 63-byte identifier limit;
3. safe snake_case field names;
4. Constraint/Index generated identifier lengths;
5. explicit Many2many relation lengths;
6. field/method collisions;
7. list-valued `_inherit` safety;
8. no upstream owner shadowing;
9. SQL reserved-word protection;
10. no Odoo recordset proxy used as an `isinstance()` type;
11. class-load decorator/base/import validation;
12. View field and object-method resolution;
13. nested One2many model switching;
14. no numeric-prefix backup packaging.
