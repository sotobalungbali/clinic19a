# Runtime Repair — Missing `clinic_base.menu_root` XML-ID

## Runtime blocker

Odoo 19 upgrade failed while loading `views/treatment_catalog_menus.xml` because
`clinic_base.menu_root` is not registered in the current ClinicOne database/source
revision. In `clinic_base/views/views.xml`, that legacy scaffold menu is commented.

## Repair decision

- Preserve `clinic_treatment_catalog.menu_treatment_catalog` as the stable root XML-ID.
- Remove the manifest-loaded hard parent `clinic_base.menu_root`.
- Keep all existing Treatment Catalog child menus and actions unchanged.
- On fresh installation only, use a defensive post-init hook to attach the local
  Treatment Catalog root below `clinic_patient.menu_root` when a safe ClinicOne
  root is actually available.
- If the optional parent is unavailable, Treatment Catalog remains usable as its
  own application root.

This is a presentation-layer repair. It does not alter treatment, pricing, consent,
security, accounting, branch, patient, or inventory business contracts.
