# clinic_referral — Codex Boundary

Codex is a **bounded implementation worker**. Codex is not the architect, not a
simplifier, and not an endless retry engine.

1. Preserve historical `clinic.referral`, `clinic.referral.program`, and
   `clinic.referral.source` contracts unless a concrete defect is documented.
2. Never move ownership of Patient, Doctor, Booking, Branch, CRM, Membership,
   Treatment Session, Wallet, Billing, Audit or Marketing into this addon.
3. `clinic_treatment_session` and `clinic_membership` are downstream consumers;
   they must not become hard dependencies here.
4. Cross-addon optional navigation must fail safely when a downstream model is
   unavailable.
5. Security is enforced by ACL, record rules and Python workflow guards.
6. Executable `_sql_constraints` is forbidden; use Odoo 19 `models.Constraint`.
7. Digit-prefixed backup basenames are never packaged.
8. Maximum bounded implementation repair attempts for this build: **3**.
