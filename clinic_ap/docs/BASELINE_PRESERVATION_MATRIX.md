# Baseline Preservation Matrix

| Baseline capability | V1 disposition |
|---|---|
| AP header and AP lines | PRESERVED + lifecycle hardened |
| Vendor bill creation/link | PRESERVED + standard `account.move` ownership made explicit |
| AP payment terms | PRESERVED + migrated to Odoo 19 `_compute_terms()` contract |
| Vendor AP controls/KPIs | PRESERVED + namespaced vendor exposure limit |
| Purchase integration | PRESERVED + reverse navigation / create action |
| Inventory/receipt integration | PRESERVED + missing `clinic.ap.line.stock_move_id` repaired |
| Stock valuation traceability | PRESERVED |
| Billing cost traceability | PRESERVED + reverse navigation |
| Finance/accounting navigation | PRESERVED |
| Aging engine | PRESERVED + full enterprise UI |
| Cashflow engine | PRESERVED + full enterprise UI |
| Company settings | PRESERVED + dedicated AP Settings screen |
| Controller/demo scaffolds | REJECTED WITH REASON: no business behavior in active baseline scaffold |
| Generic scaffold templates/views | REPLACED WITH ENTERPRISE UI |
| Core `res.partner.credit_limit` redeclaration | REJECTED WITH REASON: semantic collision with Odoo core customer credit limit |

