# clinic_emar — Runtime Repair 2026-08-14

## Runtime evidence

Target runtime: Odoo 19.0.20260505 CE, database `odoo19ce`.

The user-provided `odoo.log` repeatedly fails registry setup with:

`TypeError: __bases__ assignment: 'ClinicEmarScheduleWorkflowGuard' object layout differs from 'ClinicEmarSchedule'`

The failure occurs during `odoo.orm.model_classes._prepare_setup()` while Odoo
rebuilds model class bases.

## Root cause

`models/integrations/workflow_guard.py` defined a plain Python helper class
`_EmarWorkflowGuard` and then used Python multiple inheritance for concrete Odoo
extensions:

- `ClinicEmarPrescriptionWorkflowGuard(_EmarWorkflowGuard, models.Model)`
- `ClinicEmarOrderWorkflowGuard(_EmarWorkflowGuard, models.Model)`
- `ClinicEmarScheduleWorkflowGuard(_EmarWorkflowGuard, models.Model)`
- `ClinicEmarAdministrationWorkflowGuard(_EmarWorkflowGuard, models.Model)`

That class shape is incompatible with Odoo 19 registry base reconstruction in
this runtime.

## Corrective action

The plain Python mixin base is removed from model inheritance. A module-level
`_check_direct_state_write(records, vals)` helper now contains the shared
validation. Each concrete workflow extension inherits only from
`models.Model`.

The existing model API is preserved:

- `_emar_check_direct_state_write(vals)`
- `_emar_guarded_write(vals)`
- `write(vals)`

Approved workflow actions still use `_emar_guarded_write()` to continue below
the guard layer through the normal Odoo MRO. Direct state writes still raise
`UserError`.

## Regression protection

`tools/clinic_emar_guardrail.py` now AST-scans model source and fails if a
concrete Odoo model class uses Python multiple inheritance beside
`models.Model`, `models.AbstractModel`, or `models.TransientModel`.

`tests/test_emar_enterprise.py` adds
`test_26_workflow_guard_registry_contract_is_loaded`.

## Scope

No owned model, field, workflow, action, view, ACL, record rule, inventory
integration, billing integration, clinical safety rule, prescriber governance,
or downstream contract was removed.

## Status

- Source/static: PASS after repair.
- Windows Odoo registry load: PENDING user verification.
- Module upgrade/install: PENDING user verification.
- Clinical smoke workflow: PENDING user verification.
