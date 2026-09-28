# ClinicOne bounded warehouse owner contract — 19.0.1.0.67

## Runtime finding

`population.setup` creates three dimension warehouses through the functional
Stock Manager.  Odoo 19's native `stock.warehouse.create()` provisions
configuration-owned resources and can create `res.config.settings`.  Granting
the demo actor `base.group_system` would expand every later journey and is not
an acceptable least-privilege repair.

## Contract

- `clinic_inventory` owns a private `_clinic_demo_create_bounded_warehouse()`
  adapter; underscore methods are not public RPC endpoints.
- The caller must be a Stock Manager, Demo Safe Mode and the Demo Run ID must
  be explicit, and the company must already be in the actor's company scope.
- The payload is closed to `name`, `code`, `company_id`, and `branch_id`.
- Only the exact identities DP1, DP2 and DP3 are accepted.
- `branch_id=False` is mandatory, preventing a mutable user/company branch
  default from changing generated data.
- Collision checks are fail-closed.  Existing unbound warehouses are never
  adopted.
- Privilege elevation covers only the native warehouse create transaction.
  The actor receives neither Administrator nor Config Settings access.

All locations, Wallets and later monthly population documents continue through
their existing functional owner APIs and provenance contracts.  Resume the
same failed journey; do not reset the dataset.









