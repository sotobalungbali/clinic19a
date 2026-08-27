# HARD GATE 11 - Database Identifier & ORM Naming Safety

The guardrail statically validates every owned ORM technical identifier.

## Owned model/table

- model: `clinic.portal.profile`
- PostgreSQL table: `clinic_portal_profile`

## Constraint / index attribute names

- `_partner_company_unique`
- `_company_state_idx`

All generated/declared names remain comfortably below PostgreSQL's 63-byte
identifier ceiling.

## Rules enforced

1. `_name` must use lowercase dotted Odoo model syntax.
2. Derived SQL table name must be <= 63 ASCII bytes.
3. Field technical names must use lowercase snake_case and be <= 63 bytes.
4. Constraint/index Python attribute names must be <= 63 bytes.
5. Explicit Many2many relation names, when present, must be <= 63 bytes.
6. No Python method may collide with a field technical name in the same model.
7. No list-valued `_inherit` may exist without explicit `_name`.
8. No owned model may shadow an upstream model.
9. Reserved/unsafe names such as `select`, `from`, `where`, `table`, and
   `constraint` are rejected as owned field names.
10. XML IDs and model references must resolve without fabricated model names.

This gate is mandatory before runtime installation.
