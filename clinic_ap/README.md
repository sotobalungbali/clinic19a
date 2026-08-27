# ClinicOne Accounts Payable (`clinic_ap`)

Enterprise Accounts Payable for ClinicOne on Odoo 19 Community Edition.

## Scope
- governed AP document lifecycle and vendor bill generation;
- AP lines with product, tax, analytic, purchase, receipt, native Odoo 19 `stock.move.value` valuation, clinical and Billing traceability;
- three-way matching with company tolerances and optional receipt enforcement;
- vendor AP exposure, hold, risk and portfolio KPIs;
- AP payment-term policy built on the Odoo 19 payment-term engine;
- standard Odoo vendor bills and standard payment registration;
- AP aging snapshots;
- treasury cashflow forecasts with AP/AR sources and manual adjustments;
- runtime-safe reverse Smart Buttons on Vendor, Vendor Bill, Purchase Order and Clinic Billing;
- bounded integration-event outbox;
- multi-company security and enterprise Search/List/Form UI.

## Accounting ownership
`clinic.ap` is the ClinicOne AP orchestration and operational control document. Legal vendor invoices remain standard Odoo `account.move` records with `move_type='in_invoice'`. Payments are registered through standard Odoo accounting flows.

## Installation
Place the folder directly under the ClinicOne addons path, update the Apps list, and install **ClinicOne - Accounts Payable**.

Authoritative build version: `19.0.3.0.2`.
