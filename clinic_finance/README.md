# ClinicOne Finance

Authoritative build: **19.0.1.0.0**

`clinic_finance` is the treasury and internal-finance orchestration layer that
follows `clinic_wallet`.

Finance owns Finance Accounts, Internal Transactions, Internal Transfers, Fund
Requests, Cash Sessions, Cash Counts, and Treasury Positions. It consumes
Billing/AR/AP/Wallet operational results without replacing them. The future
`clinic_accounting` addon is deliberately not a dependency.

Static PASS is not runtime completion. Final completion requires installation
and smoke testing in the user's Odoo 19 CE runtime.
