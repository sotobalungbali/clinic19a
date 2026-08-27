# ClinicOne — clinic_room_device Enterprise Completeness Matrix

| Area | Status | Evidence |
|---|---|---|
| Functional baseline preservation | PASS | Baseline model/field/method contract |
| Backup `0*` exclusion | PASS | Manifest/distribution guard |
| Odoo 19 SQL constraints | PASS | Legacy `_sql_constraints` removed; `models.Constraint` used |
| Odoo 19 name search | PASS | `domain=None` signatures |
| Odoo 19 action view modes | PASS | Python actions use `list`, not `tree` |
| Odoo 19 Product Type compatibility | PASS | Goods=`consu`; legacy `product` removed from active logic |
| Accounting soft-coupling | PASS | No `supplier_rank` dependency; manifest unchanged |
| Sequence contract | PASS | Device/assignment/movement/session sequences loaded |
| Search coverage | PASS | 8/8 persistent custom models |
| List coverage | PASS | 8/8 persistent custom models |
| Form coverage | PASS | 8/8 persistent custom models |
| Professional lifecycle UI | PASS | Existing states/actions surfaced |
| ACL coverage | PASS | 8/8 persistent custom models |
| Multi-company record rules | PASS | 8/8 persistent custom models |
| Cross-contract static validation | PASS when validator passes | model↔field↔method↔view↔XML-ID |
| Windows Odoo 19 fresh/install upgrade | PENDING | Must be run on target PC |
| Final freeze | PENDING | Only after target runtime PASS |
