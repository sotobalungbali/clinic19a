# Enterprise Completeness Matrix

| Gate | Status before PC runtime | Acceptance |
|---|---|---|
| Source inventory | PASS | all non-backup files accounted for |
| Preservation | PASS | no baseline business capability removed |
| Python compile | PASS target | all `.py` compile |
| XML parse | PASS target | all `.xml` parse |
| Odoo 19 constraints | PASS target | no executable `_sql_constraints` |
| Action methods | PASS target | no unresolved package object actions |
| Primary Search/List/Form matrix | PASS target | 8/8 models |
| Multi-company rules | PASS target | all company-owned owner models protected |
| Package settings schema safety | PASS target | `res.company.clinic_pkg_*` fields non-stored |
| Legacy settings migration | PASS target | pre-migration preserves values |
| eMAR traceability | PASS target | package usage ↔ eMAR contract present |
| Runtime registry | PENDING | Odoo Windows registry loads |
| Upgrade/install | PENDING | module upgrade/install completes |
| UI smoke | PENDING | actions/forms/lists open |
| Workflow smoke | PENDING | package→allocation→redemption and voucher flows work |
| eMAR integration smoke | PENDING | linked redemption navigates both directions |
