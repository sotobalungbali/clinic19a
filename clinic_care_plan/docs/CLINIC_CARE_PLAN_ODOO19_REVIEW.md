# ClinicOne — clinic_care_plan Odoo 19 Review

## Preservation-first result
The functional baseline is retained. Existing core models remain:
- `clinic.care.plan`
- `clinic.care.plan.line`
- `clinic.care.protocol`
- `clinic.care.protocol.step`

Existing Procedure Session, eMAR Prescription and Practitioner integration remains active. Patient, Doctor and Encounter reverse navigation is additive.

## Odoo 19 hardening
- Migrated four executable `_sql_constraints` declarations to `models.Constraint` while preserving their SQL semantics.
- Replaced deprecated `group_operator="avg"` with `aggregator="avg"`.
- Replaced invalid `fields.DateUtils.relativedelta` usage with Python `timedelta`.
- Replaced Python action `tree,form` with `list,form`.
- Preserved stored business `display_name` fields on Care Plan and Protocol rather than replacing their business titles with framework-computed labels.
- Added `_compute_display_name` only to Protocol Step, preserving its historical `[sequence] title` label.
- Removed the speculative `practioner_ids` domain reference from Practitioner delete protection.

## Integration hardening
Procedure Session and eMAR Prescription now carry both `care_plan_id` and `care_plan_line_id`. Direct line links synchronize back to `session_id` / `prescription_id`.

Patient, Doctor and Encounter gain reverse Care Plan navigation. Their form enhancements are optional post-init integrations so an older sibling presentation XML revision cannot block installation.

## Enterprise presentation
All four persistent custom models have Search/List/Form views. Care Plan and Care Plan Line also have Calendar views. Operational lifecycle buttons and smart navigation expose existing business methods. A QWeb Care Plan Summary report is included.

## Security
Four ACL rows and four multi-company rules cover all persistent custom models. No public/portal ACL is introduced.

## Runtime status
Static source gate is intended to pass before packaging. Final status remains runtime-pending until installed/upgraded on the target Odoo 19 PC.
