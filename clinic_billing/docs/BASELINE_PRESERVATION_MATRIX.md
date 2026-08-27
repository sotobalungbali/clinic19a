# Baseline Preservation Matrix — `clinic_billing`

| Baseline intent / artefact | Decision | Final treatment |
|---|---|---|
| Clinical billing invoice | KEEP_AND_HARDEN | Full lifecycle, explicit line ownership, accounting bridge, source traceability, ORM lock |
| Billing line | KEEP_AND_HARDEN | Stored totals, typed clinical source fields, One2many/action support |
| Split payment | KEEP_AND_HARDEN | Odoo 19 `account.payment` contract and reconciliation |
| Discount engine | KEEP_AND_HARDEN | Rule/redemption domain retained |
| Voucher engine | KEEP_AND_HARDEN | Program/voucher/redemption retained |
| Membership/wallet | DEFER_WITH_CONTRACT | `clinic.wallet` consumed softly; no forward hard dependency |
| Insurance claim | KEEP_AND_HARDEN | Claim/line lifecycle, settlement traceability |
| Provider commission | KEEP_AND_HARDEN | Rule/line/settlement lifecycle |
| Gateway transaction/event | KEEP_AND_HARDEN | Provider TX/event traceability and payment links |
| Accounting builder | KEEP_AND_HARDEN | Odoo 19 accounting integration |
| Historical `clinic.booking.appointment` / `clinic.treatment.session` names | MOVE_TO_NAMED_OWNER | Replaced by actual `booking.booking`, `clinic.encounter`, care plan/package/eMAR contracts |
| Historical `clinic.membership.wallet` hard assumption | DEFER_WITH_CONTRACT | Mapped to actual soft `clinic.wallet` API |
| Legacy `_sql_constraints` | REWRITE | Converted to `models.Constraint` |
| Empty scaffold controllers/templates/sample model | REJECT_WITH_REASON | Comment-only Odoo scaffold; no business function, removed to prevent maintenance noise |
| Forward AR/AP/Audit/Reports integration | DEFER_WITH_CONTRACT | Integration-event outbox; downstream modules consume without circular dependency |
| Upstream form decoration | KEEP_AND_HARDEN | Runtime-safe optional UI bridge avoids hard external-XML-ID failure |
