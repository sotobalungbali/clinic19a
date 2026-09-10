# Source / Static Validation — clinic_ar 19.0.3.0.2

Build date: 2026-08-19  
Runtime assertion: **NOT RUN / NOT ASSERTED**

Guardrail result:
- Python files: 17
- XML files: 14
- Persistent owner models: 10/10
- `models.Constraint`: 9
- Legacy executable `_sql_constraints`: 0
- SQL object attributes without `_` prefix: 0
- Loadable-XML object buttons: 51
- Runtime-safe Billing Smart Buttons: 2
- Search/List/Form UI matrix: 10/10
- ACL rows: 19
- Regression test methods: 37
- Odoo 19 `res.groups.category_id`: 0
- Search filters without technical `name`: 0
- Legacy search `<group expand/string>`: 0
- Context-aware object-button ownership mismatches: 0
- Direct `res.currency` Many2one fields using `check_company=True`: 0
- Numeric-prefix backup files packaged: 0

Cross-addon audit against the supplied ClinicOne snapshot:
- Relational references examined: 86
- Unique custom comodels: 18
- Missing custom comodels: 0
- Missing owning-addon dependencies: 0
- Dependency cycles from `clinic_ar`: 0
- Hard dependency on downstream `clinic_ap`: 0
- Hard dependency on downstream `clinic_wallet`: 0

Odoo 19 currency hardening:
- `res.currency` is treated as a global model and is not subjected to `check_company=True`.
- `clinic.ar.invoice.currency_id`, `clinic.ar.payment.currency_id`, and `clinic.ar.allocation.currency_id` default to the active company currency but may use another active currency.
- Company consistency remains enforced on company-owned accounting documents, accounts, journals, payments, billing records, and other company-aware relations.
- Runtime regression coverage asserts that `res.currency` has no `company_id` and that the three direct AR owner currency fields do not enable `check_company`.

Accounting hardening:
- Billing-linked AR reuses Billing's posted `account.move` rather than duplicating the legal invoice.
- Manual AR creates a standard Odoo customer invoice through `invoice_line_ids`.
- Receipts are standard Odoo `account.payment` records and require strict receivable reconciliation.
- Open-credit allocation must equal the maximum current reconcilable amount before standard reconciliation is invoked.
- Small-residual write-off is preserved and strict; foreign-currency write-off is blocked until a dedicated exchange-rate policy exists.

RESULT: **PASS — SOURCE/STATIC ONLY; WINDOWS ODOO RUNTIME PENDING**

## V3 Runtime-Repair Static Gate

- hard `clinic_billing.*` `inherit_id` references in loadable AR XML: **0**
- runtime-safe Billing bridge helper: **present**
- Billing Invoice bridge candidates: existing `button_box` + sheet fallback
- Billing Payment bridge candidates: existing `button_box` + sheet fallback
- bridge creation is savepoint-isolated and idempotent
- regression tests include idempotence and missing-parent non-blocking behavior



