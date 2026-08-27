# HARD GATE 11 — Database Identifier & ORM Naming Safety

Owned tables:

- `clinic_quality_sop`
- `clinic_quality_sop_version`
- `clinic_quality_sop_acknowledgement`
- `clinic_quality_check_template`
- `clinic_quality_check_template_line`
- `clinic_quality_check`
- `clinic_quality_check_line`
- `clinic_quality_schedule`

Guardrail validates:
- lower-case dotted model names;
- snake_case field names;
- PostgreSQL 63-byte identifier limit;
- Constraint/Index generated names;
- explicit Many2many relation names;
- field/method namespace collisions;
- list-valued `_inherit` only with explicit `_name`;
- no env-model proxy used as an `isinstance()` type;
- Python class-load import/decorator safety;
- View field/object method resolution;
- nested One2many model switching;
- Search-domain searchability;
- no numeric-prefix backup packaging.
