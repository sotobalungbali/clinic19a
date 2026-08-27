# Enterprise Completeness Matrix

| Capability | Ownership | Source/static status | Runtime gate |
|---|---|---|---|
| Wallet identity + one/company uniqueness | `clinic.wallet` | PASS | Pending target Odoo |
| Top-up / redeem / refund / adjustment ledger | transaction + wizard | PASS | Pending |
| Reservation/release/finalize API | wallet | PASS | Pending Billing scenario |
| Concurrent balance protection | wallet row lock | PASS | Pending concurrent test |
| Accounting journal integration | transaction/company settings | PASS | Pending configured chart |
| Billing invoice integration | billing mixin | PASS | Pending |
| Patient integration | res.partner extension | PASS | Pending |
| Usage rules / quotas / expiry | wallet.rule | PASS | Pending |
| Portal request approval | portal request + controller | PASS | Pending portal test |
| Multi-company isolation | record rules + check_company | PASS | Pending multi-company test |
| Workflow RPC protection | model methods | PASS | Pending security test |
| Search/List/Form coverage | 5/5 persistent models | PASS | Pending UI smoke test |
| Statusbar / Smart / Body / O2M buttons | Wallet UI | PASS | Pending UI smoke test |
| Reporting | PDF + pivot + graph | PASS | Pending report render |
| Cron / notifications | expiry + rule expiry | PASS | Pending scheduler run |
| Regression suite + 15 hard gates | tests/tools | PASS static | Pending Odoo test runner |

**Enterprise completion is not declared until runtime install/upgrade and smoke tests pass on the user's Odoo 19 CE database.**



