# ClinicOne — clinic_inventory Odoo 19 Enterprise Hardening Review

## Identity & Scope
- PROJECT: ClinicOne
- ADDON: `clinic_inventory`
- TARGET: Odoo 19 Community Edition
- TARGET PATH: `/mnt/d/projects/odoo19v/clinic19a/clinic_inventory`
- FUNCTIONAL BASELINE: FINISHED
- CHANGE MODE: technical hardening + enterprise completeness only
- BACKUP RULE: filenames beginning with digit `0` are excluded

## Existing Function Preservation
The active supplied model/field/method structure is preserved. No business model,
field, method, state, or workflow was removed to obtain a PASS. Manifest dependency
order/content remains identical to the supplied active baseline.

## Odoo 19 Hardening Applied
1. Migrated three effective SQL constraints from legacy `_sql_constraints` declarations to `models.Constraint`.
2. Replaced active `stock.move.line.qty_done` use with Odoo 19 `quantity`.
3. Reconciled ClinicOne `usage_type` taxonomy with the existing Product Template selection without changing stored business selection values.
4. Mapped stockable ClinicOne goods to Odoo 19 goods semantics (`type='consu'` with `is_storable=True`) instead of legacy `type='product'`.
5. Preserved service/package behavior as service semantics.
6. Added Odoo 19 display-name computation for custom labels while retaining compatibility `name_get()` wrappers for older ClinicOne callers.
7. Replaced Python action `tree,form` terminology with `list,form`.
8. Added safe category-to-template usage mapping so older category policy selections do not write invalid Product Template `usage_type` values.
9. Added two sequence records already required by existing `next_by_code()` calls.

## Enterprise Presentation
User-facing persistent models:
- `clinic.treatment.product.usage`
- `clinic.treatment.product.usage.line`
- `clinic.inventory.adjustment`
- `clinic.inventory.adjustment.line`
- `clinic.patient.product.history`
- `clinic.doctor.allowed.product`
- `clinic.integration.event.log`

All seven have Search/List/Form surfaces. Business documents use their existing
states as statusbars. Existing methods are exposed through bounded action/smart
buttons. Embedded lines include open-parent buttons. Core Odoo product, warehouse,
location, and lot forms receive dedicated ClinicOne inventory sections.

## Security
ORM ACL and multi-company record rules are active for user-facing ClinicOne inventory
records. No public or portal access is introduced. UI visibility never replaces ORM
security. Technical service/catalog models remain non-user-facing by design.

## Codex Guardrail
Codex is a LIMITED IMPLEMENTATION WORKER:
- not architect,
- not simplifier,
- not ownership/dependency decision maker,
- not autonomous refactorer,
- not endless retry engine.

Maximum focused attempts for one blocker/root-cause class: 3. Attempt 3 failure
requires STOP + blocker report + `MOVE_FORWARD_READY: NO`.

## Static Status
Static source, structural-preservation, UI, security, and guardrail validation are
performed by:

`python3 tools/clinic_inventory_guardrail.py`

Target-PC Odoo runtime install/upgrade/repeat-upgrade and focused inventory smoke
remain mandatory before freeze.

## Runtime Repair Attempt 1 — 2026-08-12

### Runtime failure
Odoo 19 registry installation failed while resolving dependencies for `stock.lot.display_name`:

`ValueError: Wrong @depends on '_compute_display_name' ... Dependency field 'life_date' not found in model stock.lot.`

### Root cause
`models/stock_lot.py` treated `life_date` correctly as an optional compatibility fallback inside `_get_expiration_field_name()`, but the same optional field was incorrectly declared literally in `@api.depends` for `_compute_display_name`.

Odoo resolves decorator dependencies eagerly while building the registry. The helper fallback cannot run before that resolution, so an absent optional field aborts module installation.

### Surgical repair
Removed `life_date` from the `_compute_display_name` dependency decorator. The display-name dependency remains on:
- `name`
- `product_id`
- `clinic_expiration_state`

`clinic_expiration_state` already depends on the active Odoo 19 expiration field (`expiration_date`), preserving invalidation without hard-binding the registry to an optional legacy field.

### Guardrail regression protection
`tools/clinic_inventory_guardrail.py` now fails when `life_date` is declared in `@api.depends` or `@api.constrains`, including nested dependencies such as `lot_id.life_date`. Dynamic compatibility checks such as `if "life_date" in record._fields` remain allowed.

### Attempt accounting
`RUNTIME_REPAIR_ATTEMPT: 1 / 3`

Static hard gate after repair: PASS.
Runtime re-install/upgrade on the target Odoo 19 PC is still required.


## Runtime repair history (2026-08-12)
- Attempt 1: removed optional `stock.lot.life_date` from hard-coded compute decorator dependencies; dynamic fallback retained.
- Attempt 2: removed legacy search-group `expand` from all affected Clinic Inventory search views and added `ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE`.

