# ClinicOne — clinic_queue_room Odoo 19 Enterprise Hardening Review

## Baseline
- Functional baseline: **FINISHED / PRESERVED**
- Target: Odoo 19 Community Edition
- Target path: `/mnt/d/projects/odoo19v/clinic19a/clinic_queue_room`
- Backup rule: files whose filename begins with digit `0` are excluded.
- Active import graph remains unchanged.
- Manifest dependency list remains unchanged.

## Active structural scope
- Persistent custom models: **8**
- Odoo-native extension: **1** (`hr.employee`)
- Active legacy `_sql_constraints` before hardening: **9**
- Active legacy `_sql_constraints` after hardening: **0**
- Active `models.Constraint` declarations: **9**

## Odoo 19 technical hardening
1. Migrated all active legacy `_sql_constraints` to `models.Constraint`.
2. Migrated backend `read_group()` usage to `_read_group()`.
3. Migrated custom `name_search()` signatures to the Odoo 19 `domain` contract and added `_compute_display_name()` bridges where the legacy source relied on `name_get()`.
4. Replaced Python action `tree` view modes with `list`.
5. Fixed queue-token sequence allocation so concurrency is serialized on the company row before reading the next daily number.
6. Removed the active `booking_id` dereference from token queue creation because the corresponding fields are intentionally dormant/commented.
7. Guarded optional feedback integration so a not-yet-installed feedback addon cannot break the queue baseline.
8. Reworked room assignment/release/transfer to use the existing `clinic.room.assignment` pivot instead of nonexistent helpers on the frozen `clinic.room` model.
9. Aligned room capacity policy with the frozen room contract: `booking_policy` + `capacity`; removed the nonexistent `allow_multi_patient` assumption.
10. Commercial room defaults (`surcharge_product_id`, `analytic_account_id`) are soft-read only when those optional fields actually exist on room or room type.
11. Fixed visit/ticket batch sequence allocation so each record receives its own sequence.
12. Fixed ticket print counter increment without relying on a nonexistent integer helper.

## Enterprise presentation layer
All 8 persistent custom models have:
- Search view
- List view
- Form view

Workflow/state models expose existing lifecycle actions and statusbars where appropriate:
- `clinic.queue`
- `clinic.queue.token`
- `clinic.room.assignment`
- `clinic.queue.visit`
- `clinic.queue.ticket`

Additional enterprise navigation:
- Queue/Token/Room Assignment smart/body navigation
- Channel smart button to queues
- Event audit navigation
- HR Employee queue-operation extension with queue/room smart buttons

No business state was invented merely to obtain a statusbar.

## Security
- ACL coverage: **8 / 8** persistent custom models
- Company record-rule coverage: **8 / 8**
- Public/portal access added: **none**
- UI visibility is not treated as authoritative security.

## Cross-contract static gates
The machine-checkable guardrail validates:
- project/addon identity
- Codex bounded role and retry limit
- exact manifest dependency preservation
- exact active import graph preservation
- baseline file/model/field/method preservation
- Python compile and XML parse
- legacy SQL-constraint elimination
- Odoo 19 `read_group` / `name_search` / `list` compatibility
- field/method namespace collisions
- compute/inverse/search method references
- decorator field dependencies
- One2many inverse contracts
- frozen `clinic.room` contract assumptions
- XML field/button contracts
- search architecture and computed-field searchability
- Search/List/Form coverage
- ACL and company-rule coverage
- local XML-ID/action references
- manifest file references
- backup-file exclusion
- all owner-defined 15 hard gates

## Runtime status
Source/enterprise hardening is ready for target-PC runtime validation.
A real Odoo 19 install + repeat upgrade + focused queue/room smoke is still required
before `CLINIC_QUEUE_ROOM_MOVE_FORWARD_READY: YES` and freeze can be declared.


## Final static gate result before packaging
- Python compile: **PASS (19 files)**
- XML parse: **PASS (13 files)**
- Owner hard gates: **15 / 15 PASS**
- `FIELD_METHOD_NAMESPACE_COLLISION_GATE`: **PASS**
- `FIELD_COMPUTE_INVERSE_SEARCH_METHOD_GATE`: **PASS**
- `CUSTOM_DECORATOR_FIELD_CONTRACT_GATE`: **PASS**
- `RELATIONAL_MODEL_INVERSE_CONTRACT_GATE`: **PASS**
- `FROZEN_CLINIC_ROOM_CONTRACT_GATE`: **PASS**
- `XML_MODEL_FIELD_BUTTON_CONTRACT_GATE`: **PASS**
- `ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE`: **PASS**
- `ODOO19_SEARCHABLE_COMPUTED_FIELD_GATE`: **PASS**
- `LOCAL_XMLID_ACTION_REFERENCE_CONTRACT_GATE`: **PASS**
- `MANIFEST_FILE_REFERENCE_CONTRACT_GATE`: **PASS**

`CLINIC_QUEUE_ROOM_STATIC_MOVE_FORWARD_READY: YES`

`CLINIC_QUEUE_ROOM_MOVE_FORWARD_READY: PENDING` until the target-PC Odoo 19 runtime gate passes.
