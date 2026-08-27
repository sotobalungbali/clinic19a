# ClinicOne `clinic_finance` — Enterprise Development Guardrail

Codex is a **bounded implementation worker** only. Codex is not the architect,
not a simplifier, and not an endless retry engine.

Codex may implement only a verified defect after architecture, ownership,
preservation boundary, allowed files, and acceptance criteria have been defined.

Codex must never delete or reduce models, fields, methods, views, security,
approvals, reports or integrations to make a test pass. It must never move
AR/AP/Wallet ownership into Finance, introduce a dependency to future
`clinic_accounting`, bypass backend security, or reintroduce legacy
`_sql_constraints`.

Retry limit: maximum 2 bounded implementation attempts for one verified root
cause; maximum 1 repeat of the same root cause; then STOP and return to
architecture/root-cause review.

Odoo 19 rules:
- private `models.Constraint` / `models.Index`, no `_sql_constraints`;
- `res.groups` uses `privilege_id`;
- `<search>` and its direct `<group>` use no legacy attributes;
- `<list>`, never `<tree>`;
- no legacy `attrs=` or `states=`;
- list-valued `_inherit` always has explicit `_name`;
- standard `account.journal` / `account.move` remain the accounting backbone.
