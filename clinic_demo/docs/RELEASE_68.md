# ClinicOne explicit warehouse branch contract — 19.0.1.0.68

## Runtime finding

The bounded warehouse adapter supplied `branch_id=False`, but the owner
override in `clinic_branch` used `if not vals.get('branch_id')`.  It therefore
treated an explicit no-branch decision as an omitted field and silently
substituted the acting user's mutable default branch.

## Closure

- `clinic_branch 19.0.2.0.1` applies a default only when `branch_id` is absent.
- An explicit `branch_id=False` is preserved for company-wide warehouses.
- `population.setup` continues to require the exact frozen value, so validation
  has not been weakened.
- The private Inventory owner adapter, company scope, Stock Manager role,
  collision protection and deterministic DP1–DP3 identities remain mandatory.
- The failed journey savepoint rolls back the attempted warehouse and its
  provenance; no cleanup, Reset, or manual record edit is required.

Upgrade `clinic_branch`, retain exact `clinic_inventory 19.0.1.0.6`, then
upgrade `clinic_demo`.  Refresh Compatibility, Reconcile Existing Dataset and
resume the same journey.








