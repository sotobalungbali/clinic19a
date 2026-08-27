# ClinicOne — `clinic_imaging` Odoo 19 Review

## Baseline stance
`clinic_imaging` is treated as a finished functional baseline. This hardening does not redesign the clinical imaging domain.

## Odoo 19 corrections
- Migrated executable legacy `_sql_constraints` declarations to class-level `models.Constraint` objects.
- Reconciled duplicate owner declarations of `clinical.imaging.type` and `clinical.imaging.device` into same-model extensions; the dedicated files remain the canonical owners.
- Replaced active legacy `name_get()` customizations with Odoo 19 `_compute_display_name()` where appropriate.
- Preserved `clinical.imaging.finding.display_name` as an intentional business Title field because the baseline explicitly stores and edits that field.
- Migrated Python action view terminology from `tree` to `list`.
- Removed the obsolete Product Type value `product` from active Goods domains; Odoo 19 Goods use `consu`.
- Verified all active Many2many effective relation-table identifiers fit the PostgreSQL/Odoo identifier limit.
- Added missing sequences already referenced by `next_by_code()`.
- Added the QWeb imaging-result report and mail template already referenced by source methods.
- Replaced placeholder presentation/security with complete Search/List/Form/action/menu/ACL/rule layers for all persistent custom imaging models.

## Ownership and dormant source
- `models/models.py` remains dormant.
- `models/xxx_clinic_imaging.py` remains dormant.
- No sibling ClinicOne addon is modified.
- The Imaging menu is local at install time. `post_init_hook` optionally reparents it under ClinicOne when the compatible parent menu exists, preventing source/database presentation XML-ID drift from blocking installation.

## Status
`CLINIC_IMAGING_STATIC_MOVE_FORWARD_READY` may be YES after the machine guardrail passes. `CLINIC_IMAGING_MOVE_FORWARD_READY` remains PENDING until target-PC Odoo 19 install/upgrade passes.
