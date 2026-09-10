# Runtime Repair 2026-08-20 — Odoo 19 Settings Action XML ID

## Symptom
`clinic_emar` upgrade failed while loading `views/emar_menu_views.xml` because
the Settings menu referenced `base.action_res_config_settings`, which is not
available in this Odoo 19 runtime.

## Root cause
The eMAR menu carried a legacy/invalid cross-addon Settings action reference.
Odoo 19 Settings infrastructure is owned by `base_setup`, while ClinicOne eMAR
needs an app-scoped settings entry.

## Repair
- add direct dependency on `base_setup`;
- define `clinic_emar.action_emar_config_settings` locally;
- open `res.config.settings` with `module = clinic_emar`;
- point `menu_emar_settings` to the local action;
- add static and runtime regression gates against
  `base.action_res_config_settings`.

No clinical, medication, inventory, billing, safety, workflow, security, or
multi-company feature is removed by this repair.

