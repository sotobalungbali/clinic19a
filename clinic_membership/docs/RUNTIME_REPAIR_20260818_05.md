# Runtime Repair 2026-08-18 #05 — Settings Action External ID

## Runtime symptom
Activation stopped while loading `views/menu_views.xml` with:

`External ID not found in the system: base.action_res_config_settings`

## Root cause
The Membership Configuration > Settings menu referenced a historical/nonexistent
Odoo core XML ID:

`base.action_res_config_settings`

Odoo 19 core defines:
- `base.res_config_setting_act_window` in base; and
- `base_setup.action_general_configuration` in base_setup.

Relying on a global settings action is unnecessary for an addon-owned Settings
entry and makes the module vulnerable to XML-ID drift.

## Corrective architecture
Membership now owns:

`clinic_membership.action_membership_settings`

The action:
- opens `res.config.settings`;
- uses `view_mode = form`;
- stays in the current window;
- sets context `module = clinic_membership` and `bin_size = False`.

`menu_membership_settings` now references this local action.

## Preservation
No Membership business model, workflow, entitlement, voucher, point, hold,
clinical traceability, accounting integration, security rule, or enterprise UI
capability was removed.

## Guardrail addition
Static guardrail rejects the historical `base.action_res_config_settings`
reference and verifies that the Membership Settings menu resolves to the local
owned action with the expected `res.config.settings` contract.

## Status
Source/static PASS only. Windows Odoo runtime activation remains pending.
