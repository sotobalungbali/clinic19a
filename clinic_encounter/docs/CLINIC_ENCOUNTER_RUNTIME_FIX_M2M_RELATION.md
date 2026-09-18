# ClinicOne — clinic_encounter Runtime Fix: Many2many Relation Identifier Length

## Runtime error

Odoo 19 rejected the implicit Many2many relation table generated for:

- model: `clinic.diagnosis.plan.procedure.wizard`
- field: `procedure_ids`
- comodel: `clinic.procedure.catalog`

Implicit relation name:

`clinic_diagnosis_plan_procedure_wizard_clinic_procedure_catalog_rel`

Length: 67 characters.

Odoo 19 validates Many2many relation table names with `check_pg_name()`, which
rejects PostgreSQL identifiers longer than 63 characters.

## Root-cause correction

The wizard field now owns an explicit compact relation schema:

- relation: `clinic_diag_plan_proc_wiz_rel`
- column1: `wizard_id`
- column2: `procedure_id`

Business behavior is unchanged.

## Full-addon audit

All active Many2many fields were analyzed using their effective Odoo 19
relation-table names.

- active Many2many fields over 63 characters before fix: 1
- active Many2many fields over 63 characters after fix: 0
- non-backup source Many2many fields over 63 characters after fix: 0
- duplicate effective relation schemas: 0

## Regression guardrail

Added:

`ODOO19_MANY2MANY_RELATION_IDENTIFIER_GATE`

The gate computes implicit relation names using Odoo 19's alphabetical table
ordering rule, validates relation/column identifiers, checks the 63-character
limit, catches implicit self-Many2many relations, and detects duplicate
relation schemas.

## Preservation

- Models removed: 0
- Fields removed: 0
- Methods removed: 0
- Workflows removed: 0
- Manifest dependencies changed: 0
- Dormant aggregate activated: NO
- Backup `0*` files included: NO

## Static result

- `ODOO19_MANY2MANY_RELATION_IDENTIFIER_GATE: PASS`
- `PASS: 15 / 15 OWNER HARD GATES`
- `CLINIC_ENCOUNTER_STATIC_MOVE_FORWARD_READY: YES`
- `CLINIC_ENCOUNTER_MOVE_FORWARD_READY: PENDING`

A target-PC Odoo 19 activation/upgrade is still required before freeze.

