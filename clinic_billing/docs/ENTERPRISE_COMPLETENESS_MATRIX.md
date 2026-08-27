# Enterprise Completeness Matrix — `clinic_billing`

| Dimension | Source/static status | Runtime status |
|---|---|---|
| Project identity / authoritative baseline | PASS | N/A |
| Existing functional preservation | PASS | Pending smoke |
| Structural inventory | PASS | N/A |
| Human-friendly code structure | PASS | N/A |
| Odoo 19 manifest/dependencies | PASS | Pending Odoo load |
| Legacy `_sql_constraints` removal | PASS | Pending DB constraint creation |
| Clinical billing lifecycle | PASS source | PENDING |
| Accounting invoice generation/sync | PASS source | PENDING |
| Split-payment / reconciliation | PASS source | PENDING |
| Discount/voucher engine | PASS source | PENDING |
| Membership/wallet soft contract | PASS source | PENDING |
| Insurance claim lifecycle | PASS source | PENDING |
| Provider commission lifecycle | PASS source | PENDING |
| Gateway transaction lifecycle | PASS source | PENDING |
| Clinical source traceability | PASS source | PENDING |
| Multi-company ACL / record rules | PASS source | PENDING |
| Search/List/Form matrix 19/19 | PASS | PENDING render |
| Statusbar/action/smart/body/O2M controls | PASS source | PENDING render |
| Static regression suite | PASS syntax/contract | PENDING Odoo test execution |
| Windows install/upgrade | N/A | PENDING |
| Financial/clinical smoke | N/A | PENDING |

**Release rule:** do not mark the addon frozen solely from this matrix's source/static PASS entries.
