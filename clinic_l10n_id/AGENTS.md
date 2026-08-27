# ClinicOne `clinic_l10n_id` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- owner of tax/localization architecture;
- owner of upstream/downstream model ownership;
- an endless retry engine.

Codex must never:
- replace Odoo `l10n_id` taxes or chart of accounts with ClinicOne duplicates;
- replace Odoo Coretax XML generation with a custom e-Faktur engine;
- hard-code a statutory PPN rate into ClinicOne business logic when native
  `account.tax` records already define the legal tax;
- rewrite posted invoice numbers;
- silently change a journal sequence prefix after posted entries exist;
- delete or reduce upstream Billing/AR/AP/Wallet/Finance/Accounting features;
- bypass backend permissions because a button is hidden;
- reintroduce executable `_sql_constraints`;
- use list-valued `_inherit` without explicit `_name`.

Retry limit:
- maximum 2 bounded implementation attempts for one proven defect;
- maximum 1 repeat of the same root cause;
- then STOP and return to root-cause/architecture review.

Odoo 19 hard contracts:
- use `models.Constraint` / `models.Index`;
- use `res.groups.privilege` / `privilege_id`;
- use `<list>`, never `<tree>`;
- no legacy `attrs=` / `states=`;
- ClinicOne search `<search>` and direct `<group>` remain attribute-free;
- `account.move` / `account.move.line` remain the legal ledger;
- `l10n_id` remains owner of Indonesian fiscal localization;
- `l10n_id_efaktur_coretax` remains owner of Coretax XML generation.

