
# clinic_treatment_session — Codex Boundary

Codex is a bounded implementation worker.

1. Preserve public contracts of Treatment Session, Session Line, Session Stage,
   and Booking/Patient/Doctor/Room extensions.
2. Do not move ownership of Booking, Referral, Package, Billing, Accounting,
   Inventory, Membership, AR, Wallet, Audit or Analytics into this addon.
3. Downstream consumers remain downstream; no dependency-cycle creation.
4. State transitions and inventory consumption remain backend-enforced.
5. Odoo 19 executable `_sql_constraints` is forbidden; use models.Constraint.
6. Digit-prefixed backup basenames are never packaged.
7. Optional cross-addon UI decoration must not block installation.
