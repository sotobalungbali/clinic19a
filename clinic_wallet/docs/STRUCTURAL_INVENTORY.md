# Full Structural Inventory

## Persistent models

1. `clinic.wallet` — wallet identity, lifecycle, balances, reservation API, accounting settings access, expiry reminders.
2. `clinic.wallet.transaction` — auditable ledger, accounting traceability, reservation/post/cancel/reversal lifecycle.
3. `clinic.wallet.rule` — eligibility, quota, date/time, membership/product/category controls.
4. `clinic.wallet.portal.mgr.approver` — per-company approval routing.
5. `clinic.wallet.portal.request` — top-up/refund request workflow and approval audit.

## Abstract / transient models

- `clinic.wallet.billing.mixin` — reusable Billing/account.move settlement contract.
- `clinic.wallet.portal.mixin` — programmatic portal helper contract.
- `clinic.wallet.operation.wizard` — controlled manual financial operation wizard.

## Inherited models

- `res.partner` — wallet navigation and current-company summary; extends the `clinic_patient` integration counter instead of redeclaring `wallet_balance`.
- `res.company`, `res.config.settings` — company-scoped wallet accounting/lifecycle settings.
- `clinic.billing.invoice`, `account.move`, `clinic.billing.payment.line` — downstream settlement bridges.

## Data / UI / reporting

- 3 sequences; 2 scheduled jobs; 1 expiry mail template.
- Search/List/Form for every persistent Wallet-owned model.
- Transaction pivot and graph.
- Patient form and Clinic Billing form integrations.
- Wallet settings app, operational wizard, PDF statement, backend menus, portal self-service page.
- 3-role security hierarchy plus multi-company and portal-own record rules.



