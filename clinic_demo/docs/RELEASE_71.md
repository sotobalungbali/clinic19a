# ClinicOne bounded Inventory receipt contract — 19.0.1.0.71

## Runtime finding

The population receipt combined creation of `stock.move.line` and
`picked=True` in one ORM write.  On Odoo 19 the picked computation can be
evaluated before the new x2many row becomes the move's effective done line.
The move then reaches `_action_done()` without a stable completed-quantity
contract and period 01 fails with `stock receipt not complete`.

## Closed owner contract

- `clinic_inventory 19.0.1.0.7` owns the private bounded receipt API.
- It requires Demo Safe Mode, a positive quantity, a Draft empty move,
  supplier-to-internal locations, and an allowed company.
- Confirmation explicitly uses `merge=False`.
- Move-line creation and `picked=True` are separate ordered writes.
- Native `_action_done()` remains the only completion transition.
- Completed quantity is proven from the sum of native move lines using the
  product UoM rounding; the mutable `stock.move.quantity` cache is not used as
  acceptance evidence.
- The original source journey and all twelve population Inventory periods use
  the same owner API and the same receipt/consumption quantity proof.

## Continuation

Upgrade `clinic_inventory` before `clinic_demo`, reuse the same Demo Run,
refresh compatibility, reconcile, then execute next/resume.  Do not reset the
dataset; the failed Inventory period was rolled back by its journey savepoint.





