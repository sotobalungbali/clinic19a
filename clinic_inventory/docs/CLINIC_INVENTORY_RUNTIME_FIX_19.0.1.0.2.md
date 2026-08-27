# Clinic Inventory Runtime Repair 19.0.1.0.2 — 2026-08-21

## Trigger

Activating `clinic_ecommerce` caused Odoo demo stock delivery confirmation to
enter the already-installed `clinic_inventory` stock move governance hook.

Runtime failure:

```text
TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union
```

The failing pattern was:

```python
Location = self.env["stock.location"]
isinstance(loc, Location)
```

`self.env["stock.location"]` returns an Odoo model recordset/proxy. It is not a
Python class and therefore is invalid as `isinstance()` argument #2.

## Root-cause owner

The defect belongs to **`clinic_inventory`**, not `clinic_ecommerce`.

`clinic_ecommerce` only exposed the latent owner-module defect while Odoo was
confirming stock demo records from a Website Sale/Delivery dependency.

## Repair

Live runtime files repaired:

- `models/stock_move.py`
- `models/stock_picking.py`
- `models/stock_rule.py`

The unimported Odoo-19 legacy source `models/procurement_group.py` is also made
safe so the same anti-pattern cannot return if that source is ever re-enabled.

### Governance checks

For `stock.move` and `stock.picking`, Many2one locations are already
`stock.location` recordsets, so the code now checks the optional ClinicOne
field contract directly.

### Destination resolution

For `stock.rule` and the inactive procurement-group source, callers may pass
either a recordset or an integer ID. The repair now uses the recordset `_name`
contract and otherwise browses the supplied ID.

## Preservation

No model, field, view, menu, ACL, workflow, valuation logic, category policy,
expiration policy, inventory usage logic, or ClinicOne integration ownership is
removed or simplified.

## Required runtime sequence

1. Replace `clinic_inventory` with version 19.0.1.0.2.
2. Restart Odoo.
3. Upgrade `clinic_inventory`.
4. Retry activation of `clinic_ecommerce`.
5. Only after that succeeds, run eCommerce website/cart/checkout/fulfillment
   smoke tests.

Static PASS does not equal runtime completion.
