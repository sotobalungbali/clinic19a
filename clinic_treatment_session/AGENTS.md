# clinic_treatment_session — Codex Boundary

Codex is a **bounded implementation worker**.

Codex is NOT:
- the architect;
- a simplifier;
- a business-workflow rewriter;
- an endless retry engine.

## Non-negotiable boundaries

1. Preserve historical public contracts of:
   - `clinic.treatment.session`
   - `clinic.treatment.session.line`
   - `clinic.treatment.session.stage`
   - existing Booking/Patient/Doctor/Room extension methods.
2. Do not move ownership of Booking, Referral, Package, Billing, Accounting,
   Inventory, Membership, AR, Wallet, Audit or Analytics into this addon.
3. Downstream consumers (`clinic_membership`, `clinic_ar`, `clinic_wallet`,
   `clinic_reports`, `clinic_dashboard`, `clinic_analytics`, etc.) must never
   become hard dependencies and create dependency cycles.
4. State transitions and inventory consumption are backend-enforced.
5. UI visibility is not a substitute for ACL/record-rule/Python security.
6. Odoo 19 executable `_sql_constraints` is forbidden; use
   `models.Constraint`.
7. Digit-prefixed backup basenames are never packaged.
8. Optional cross-addon form decorations must not block module install/upgrade.
9. Maximum bounded implementation repair attempts during source build: **3**.
