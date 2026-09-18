# Runtime Repair 2026-08-20 — Odoo 19 Search View Architecture

## Symptom

Activating `clinic_wallet` failed while loading:

`views/wallet_views.xml`

with:

`Invalid view clinic.wallet.search definition`

## Root cause

Wallet search views still used legacy search-view attributes:

```xml
<search string="...">
...
<group expand="0" string="Group By">
```

For Odoo 19 search architecture, the root `<search>` element takes no
attributes and the `<group>` element used to separate search filters also takes
no attributes.

The problem existed in five Wallet search views, not just the first one loaded:
- Wallets
- Wallet Transactions
- Wallet Usage Rules
- Wallet Approvers
- Wallet Portal Requests

## Repair

All five search architectures now use:

```xml
<search>
...
<group>
```

Filter labels remain on the `<filter string="...">` elements, so user-facing
search/filter text and Group By options are preserved.

The Enterprise Development Guardrail now parses every XML search architecture
and fails if any `<search>` or direct search `<group>` carries attributes.

No Wallet business model, field, method, workflow, security rule, accounting
integration, Billing API, portal flow, report, or cron feature is removed.


