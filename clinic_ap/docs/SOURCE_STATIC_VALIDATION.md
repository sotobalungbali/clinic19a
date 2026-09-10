# Source / Static Validation — `clinic_ap` 19.0.3.0.2

This report is source/static acceptance only. It does **not** assert Odoo registry/runtime installation success.

## Final static results
- Python files: 18
- XML files: 12
- Persistent owner models: 9/9
- Search/List/Form UI matrix: 9/9
- `models.Constraint`: 9
- SQL table objects: 9
- Object buttons in owner-model XML views: 40
- ACL rows: 18
- Regression test methods: 39
- executable legacy `_sql_constraints`: 0
- SQL object attributes without leading `_`: 0
- `res.groups.category_id` on AP groups: 0
- AP groups missing `privilege_id`: 0
- unnamed search filters: 0
- legacy search `<group expand/string>`: 0
- direct `res.currency` Many2one with `check_company=True`: 0
- AP redeclaration of core `res.partner.credit_limit`: 0
- AP redeclaration of core `property_supplier_payment_term_id`: 0
- missing `clinic.ap.line.stock_move_id`: 0
- legacy `account.payment.state == 'posted'` assumption: 0
- legacy `account.payment.term.compute(...)`: 0
- legacy `stock.valuation.layer` contract: 0
- legacy `stock_move.stock_valuation_layer_ids` contract: 0
- native Odoo 19 `stock_move_id.value` valuation contract: present
- hard cross-addon ClinicOne inherited form views: 0
- context-aware object-button ownership mismatches: 0
- prefix-0 backup files in release: 0

## Cross-addon audit
- direct relational references: 54
- unique custom ClinicOne comodels: 11
- missing custom comodels: 0
- missing owning-addon dependencies: 0
- dependency cycles reachable from `clinic_ap`: 0

Authoritative command:

```text
python tools/clinic_ap_guardrail.py
```

Expected terminal result:

```text
RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)
```

