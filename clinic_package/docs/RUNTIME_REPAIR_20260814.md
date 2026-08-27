
# Runtime Repair — 14 Aug 2026

## Observed runtime failure

The Windows Odoo 19 CE install stopped while loading the package patient form
extension because the already-installed `clinic_patient` database did not
contain the external identifier expected by the source currently on disk.

The latest 14 Aug 2026 source export also proved that the runtime folder still
contained `clinic_package` version **19.0.2.0.0**, i.e. the pre-repair source.

## Root cause classification

This is a **source/runtime external-ID drift** problem, not a package business
model problem:

- the `clinic.patient` model exists and remains a mandatory dependency;
- the current `clinic_patient` source contains the expected patient form;
- the installed database can nevertheless predate that XML data record;
- a hard cross-addon `inherit_id` therefore becomes an avoidable installation
  single point of failure.

A second latent issue was also removed: the package root menu previously
depended on a `clinic_base` menu record that is commented out in the active
`clinic_base` source and therefore is not guaranteed to exist in the database.

## V3 correction

Version: **19.0.2.1.0**

1. Cross-addon patient, booking, and care-plan form decorations are now handled
   by `models/package_view_bridge.py`.
2. `data/optional_view_bridge.xml` invokes one private, idempotent setup method
   during module data loading.
3. Parent views are resolved with `raise_if_not_found=False`.
4. View creation/update is isolated in a database savepoint. A missing or older
   incompatible parent view is logged and skipped; it cannot abort the package
   domain installation.
5. Model-level integration remains mandatory and unchanged.
6. Legacy cross-addon view XML files remain as human-readable architectural
   markers but are not loaded by the manifest.
7. The package root menu is self-owned and no longer requires an upstream menu
   external identifier.
8. No package business model, workflow, security rule, allocation snapshot,
   redemption ledger, voucher workflow, booking logic, or care-plan logic was
   removed.

## Deployment hard gate

Before retrying installation, verify the runtime directory really contains V3:

```powershell
Get-Content "D:\projects\odoo19v\clinic19a\clinic_package\__manifest__.py" |
    Select-String "19.0.2.1.0"

Select-String `
    -Path "D:\projects\odoo19v\clinic19a\clinic_package\views\*.xml" `
    -Pattern "clinic_patient[.]view_clinic_patient_form","clinic_base[.]menu_root"
```

Expected result:

- the version command finds `19.0.2.1.0`;
- the second command returns **no matches**.

Only after those checks should Odoo be restarted and the install retried.

## Status

- Source/static gate: PASS.
- Windows fresh-install runtime gate: PENDING.
- Windows upgrade runtime gate: PENDING.
- Enterprise completion: PENDING runtime evidence.
