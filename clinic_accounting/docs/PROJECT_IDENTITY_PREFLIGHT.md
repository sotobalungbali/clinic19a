# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_accounting`
- OFFICIAL SEQUENCE: addon 23 of 39
- BLUEPRINT RESPONSIBILITY: "Integrates clinic finance with accounting ledgers, journal entries, and reports."
- AUTHORITATIVE SOURCE BASELINE: user-supplied ClinicOne bundle dated 2026-08-20
- VERIFIED UPSTREAM THROUGH: `clinic_finance`
- NEXT DOWNSTREAM ADDON: `clinic_l10n_id`

## Preservation rule

Accounting consumes and classifies standard accounting outcomes from:
- Clinic Billing
- Accounts Receivable
- Accounts Payable
- Patient Wallet
- Clinic Finance

It must not move or duplicate their business-model ownership.

## Legal ledger rule

The authoritative accounting ledger remains:
- `account.move`
- `account.move.line`
- `account.account`
- `account.journal`

`clinic_accounting` may govern, classify, report, and create controlled
adjustments into that ledger, but it must not replace it.

## Allowed changes

- new Clinic Accounting ledger-scope configuration;
- controlled manual accounting adjustment workflow;
- accounting source classification on native journal entries/items;
- period-close evidence and preflight;
- use of native Odoo fiscal lock date;
- generated accounting statement snapshots and PDF reports.

## Forbidden changes

- dependency on downstream `clinic_l10n_id`;
- Indonesia-specific PPN/tax/local invoice rules;
- deletion or reduction of upstream Finance/AR/AP/Wallet/Billing capabilities;
- parallel proprietary GL tables replacing Odoo accounting;
- hard-lock bypasses;
- legacy `_sql_constraints`.

## Current verified status

SOURCE / STATIC: under build validation  
ODOO RUNTIME: PENDING
