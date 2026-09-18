# ClinicOne Patient Wallet — 19.0.3.0.3

Enterprise patient prepaid wallet for ClinicOne on Odoo 19 CE.

## Operational model

A patient/contact has at most one wallet per company. The wallet ledger is composed of immutable posted transactions and auditable draft/reserved transactions. Billing integrates through the stable `reserve_funds`, `release_reserved`, and `validate_reserved_to_posted` API.

## Main capabilities

- top-up, redeem, refund, adjustment-in/out;
- balance reservation before billing finalization;
- Odoo accounting entries for top-up/refund/adjustments and optional redeem;
- usage rules, quota limits, product/treatment scope, membership tier scope, and expiry;
- multi-company record rules and company-specific settings;
- portal top-up/refund requests with approval audit;
- patient and Billing smart integration;
- PDF statement, list/search/form views, pivot/graph analysis, reminders and rule-expiry cron;
- backend workflow hardening against direct RPC state manipulation.

## Install / upgrade

This addon is downstream of `clinic_ap`. Install only after the authoritative upstream ClinicOne modules are installed. Runtime acceptance must be performed on the target Odoo 19 CE database; static guardrail PASS is not a substitute for runtime PASS.




