# HARD GATE 11 - Database Identifier & ORM Naming Safety

Owned Odoo models / default SQL tables:

- `clinic.marketing.preference` -> `clinic_marketing_preference`
- `clinic.marketing.segment` -> `clinic_marketing_segment`
- `clinic.marketing.promotion` -> `clinic_marketing_promotion`
- `clinic.marketing.campaign` -> `clinic_marketing_campaign`
- `clinic.marketing.recipient` -> `clinic_marketing_recipient`
- `clinic.marketing.message` -> `clinic_marketing_message`

Explicit M2M relation identifiers:
- `clinic_marketing_segment_stage_rel`
- `clinic_marketing_segment_tag_rel`
- `clinic_marketing_segment_plan_rel`

Hard Gate 11 checks:
1. lowercase dotted Odoo `_name`;
2. default SQL table <= PostgreSQL 63-byte identifier ceiling;
3. snake_case field identifiers <= 63 bytes;
4. Constraint/Index attribute and generated identifiers <= 63 bytes;
5. explicit Many2many relation names <= 63 bytes;
6. no field/method technical-name collision;
7. no list-valued `_inherit` without explicit `_name`;
8. no owner-model shadowing;
9. no unsafe SQL reserved field identifiers;
10. no env-model recordset used as `isinstance()` type;
11. XML view model/field/button contracts resolve.

This gate is executable inside `tools/clinic_marketing_guardrail.py`.

