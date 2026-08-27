# clinic_emar — Runtime Repair 2026-08-18 #02

## Runtime evidence

The 2026-08-17 Odoo log contains two distinct phases.

1. Before the source restart, registry construction still reports the historical
   `ClinicEmarScheduleWorkflowGuard` class-layout error.
2. After Odoo restarts with the corrected source, the registry completes:
   `Registry loaded in 8.000s`.
3. The next HTTP 500 is a database schema mismatch:
   `column res_company.emar_default_warehouse_id does not exist`.
4. The same log also reports:
   `relation "clinic_emar_reschedule_wizard" does not exist`.

This proves that the corrected Python model definitions are loaded while the
database has not yet been upgraded to the current clinic_emar schema.

## Root cause

Source/schema drift. The module source contains persistent fields and models
which are visible to the registry, but the corresponding database columns and
tables have not been created by a successful module upgrade.

This is not corrected by removing eMAR fields. Doing so would amputate the
enterprise configuration and still leave other missing model tables.

## Corrective action

Run a controlled Odoo module upgrade while the normal web server/service is
stopped:

    -d odoo19ce -u clinic_emar --stop-after-init

A Windows PowerShell helper is included at:

    tools/windows_recover_schema.ps1

The script targets the Odoo installation and database evidenced by the supplied
log:

- Odoo root: `C:\Program Files\Odoo 19.0.20260505`
- config: `server\odoo.conf`
- database: `odoo19ce`
- addon workspace: `D:\projects\odoo19v\clinic19a`

## Preservation

No owned eMAR model, field, clinical workflow, security rule, view, button,
inventory integration, prescription safety gate, or prescriber governance is
removed.

## Version

Recovery release: `19.0.2.0.2`

## Acceptance

Runtime is PASS only when all are true:

1. CLI upgrade exits with code 0.
2. The upgrade log has no `UndefinedColumn`, `UndefinedTable`,
   `ClinicEmarScheduleWorkflowGuard object layout`, or module-load traceback.
3. Odoo restarts normally and the web client opens.
4. `clinic_emar` opens without HTTP 500.
5. Configuration, Prescription, Order, Schedule, Administration, Alert, and
   reschedule wizard basic smoke paths can be opened.
