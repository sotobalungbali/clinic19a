# Baseline Preservation Matrix

| Baseline capability | Decision | Result |
|---|---|---|
| Package catalog lifecycle | KEEP_AND_HARDEN | preserved |
| Package component lines | KEEP_AND_HARDEN | preserved |
| Pricing profiles/rules | KEEP_AND_HARDEN | preserved |
| Policy / pause / transfer / refund | KEEP_AND_HARDEN | preserved |
| Reusable benefit templates | KEEP_AND_HARDEN | preserved |
| Allocation + immutable snapshot | KEEP_AND_HARDEN | preserved |
| Redemption ledger | KEEP_AND_HARDEN | preserved |
| Voucher + batch | KEEP_AND_HARDEN | preserved |
| Booking bridge | KEEP_AND_HARDEN | preserved |
| Care-plan bridge | KEEP_AND_HARDEN | preserved |
| Patient/contact portfolio | KEEP_AND_HARDEN | preserved |
| Durable integration events | KEEP_AND_HARDEN | preserved |
| Stored `res.company.clinic_pkg_*` configuration | MOVE_WITHOUT_API_LOSS | moved to company-qualified parameter storage to eliminate global schema-drift blast radius |
| `clinic_emar` manifest dependency with no functional contract | COMPLETE_EXISTING_INTENT | explicit redemption↔eMAR traceability added |
| Legacy `_sql_constraints` | REPLACE | executable legacy declarations forbidden; Odoo 19 `models.Constraint` used where SQL-persistent fields apply |
