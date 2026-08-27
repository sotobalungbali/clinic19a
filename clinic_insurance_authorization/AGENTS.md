# ClinicOne `clinic_insurance_authorization` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- the architect;
- a simplifier;
- owner of model/dependency decisions;
- owner of clinical/payer policy;
- an endless retry engine.

Existing-function preservation is absolute:
- `clinic_billing` already owns `clinic.insurance.claim` and
  `clinic.insurance.claim.line`;
- this addon must extend those models, not redefine/move/delete them;
- Billing claim settlement must continue to use the existing
  `clinic.billing.payment` workflow;
- patient, booking, encounter, treatment, accounting and localization ownership
  remain in their upstream modules.

Codex must never:
- delete Policy, Eligibility, Authorization, Plan, Benefit Rule or Claim features
  merely to make a test pass;
- duplicate the Billing claim models;
- create a parallel accounting/payment ledger for insurer settlements;
- silently approve an authorization or claim;
- bypass backend workflow/security because a button is hidden;
- reintroduce executable `_sql_constraints`;
- use list-valued `_inherit` without explicit `_name`;
- retry one root cause endlessly.

Retry limit:
- maximum 2 bounded implementation attempts for one proven root cause;
- maximum 1 repeat of the same root cause;
- then STOP and return to root-cause/architecture review.

Odoo 19 contracts:
- `models.Constraint` / `models.Index`;
- `res.groups.privilege` / `privilege_id`;
- `<list>`, never `<tree>`;
- no legacy `attrs=` / `states=`;
- Search `<search>` and its direct `<group>` are attribute-free;
- computed fields used in search domains must be stored or implement `search=`;
- cross-addon integration is model/API based and avoids fragile inherited custom
  view XML IDs wherever a standalone enterprise action/view is sufficient.

