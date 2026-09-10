# Integration Contracts

## Accounting
- `clinic.ap.move_id` → standard `account.move` Vendor Bill.
- AP posting creates/posts the legal vendor bill; AP does not invent a parallel accounting ledger.
- Payment registration opens standard `account.payment.register` on the posted Vendor Bill.
- `account.move` and `account.payment` receive reverse Clinic AP navigation.

## Purchase and Inventory
- `clinic.ap.purchase_id` and `clinic.ap.line.purchase_line_id` provide procurement traceability.
- `clinic.ap.line.stock_move_id` is the explicit receipt/move contract used for three-way match.
- Receipt valuation is read from native Odoo 19 `stock.move.value`; ClinicOne does not depend on the pre-19 `stock.valuation.layer` API.
- `stock.move` receives reverse AP-line navigation.

## Clinic Billing
- AP lines may reference `clinic.billing.invoice` / `clinic.billing.line` to attribute clinic-side costs.
- Billing receives reverse AP cost navigation.
- Billing form decoration is optional/runtime-safe; relational ownership is hard.

## Accounts Receivable
`clinic_ar` is a dependency because the cashflow forecast can include AR inflows. AP does not alter AR ownership.

## Runtime-safe UI bridge
Partner, Vendor Bill, Purchase Order and Billing Smart Buttons are created idempotently at runtime. Missing or structurally changed parent views may skip decoration but must not abort AP installation.

