# ClinicOne `clinic_accounting` - Enterprise Development Guardrail

## Codex role

Codex is a **bounded implementation worker** only.

Codex is NOT:
- the architect;
- a feature simplifier;
- an owner of model/dependency decisions;
- an endless retry engine.

Architecture, ownership, preservation boundaries, allowed files, and acceptance
criteria must be decided before Codex is asked to implement a defect.

Codex must never:
- delete or reduce a model, field, workflow, approval, report, search view, list
  view, form view, security rule, smart button, or integration merely to make a
  test pass;
- replace standard Odoo `account.move` / `account.move.line` with a proprietary
  accounting ledger;
- move Billing, AR, AP, Wallet, or Finance ownership into Accounting;
- create a dependency on downstream `clinic_l10n_id`;
- bypass backend workflow/security because a button is hidden;
- reintroduce executable legacy `_sql_constraints`;
- use list-valued `_inherit` without an explicit `_name`.

Retry limit:
- maximum 2 bounded implementation attempts for one proven root cause;
- maximum 1 repeat of the same root cause;
- after that STOP and return to root-cause/architecture review.

## Odoo 19 hard contracts

- Use `models.Constraint` / `models.Index`; never executable `_sql_constraints`.
- `res.groups` uses `privilege_id`, not legacy `category_id`.
- Use `<list>`, not `<tree>`.
- No legacy `attrs=` or `states=`.
- Search `<search>` and direct search `<group>` are attribute-free for the
  ClinicOne Odoo runtime contract.
- `account.account` company ownership follows Odoo 19 `company_ids` semantics.
- Standard Odoo native accounting lock dates remain authoritative.
- Posted accounting records are not made editable by ClinicOne UI.
- Cross-addon integration is model/API based and avoids fragile custom
  inherited-view XML IDs.
