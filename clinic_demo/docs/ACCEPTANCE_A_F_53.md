# Native acceptance A–F (pending)

Use a backed-up demo database, the same run/company/anchor, Safe Mode and existing deterministic identities. Source/static tests are already recorded; the following checks need native Odoo.

| Gate | Execute | Required evidence |
|---|---|---|
| A Legacy migration | Refresh Compatibility → Reconcile Existing Dataset | 40 rows; prior source records retained, ADOPT/PASS only after actual checks; ambiguity BLOCK with model/key/reason; no migration reset |
| B Step execution | Select eligible journey → Execute Current; Execute Next | Exactly one eligible aggregate; dependencies respected; actual created/reconciled counts, last execution and validation evidence |
| C Full execution | Generate Full on the same run | Same registry/order/engine as B; stops at first failed aggregate; reports refreshed after changed sources; technical progress distinct from L1–L8 population |
| D Idempotency | Reconcile then Generate Full again | Existing validated journeys Created=0; same business keys; no extra stock/accounting duplicates |
| E Reset/rebuild | Reset Preview → inspect → confirmed Safe Reset → Rebuild Retained Dataset | Only verified demo ownership processed; posted accounting/stock retained or official reversal per owner policy; retained identities reused; revalidate counts and links |
| F Failure/resume | On a disposable copy, force a scoped owner workflow failure; execute; repair contract; resume | Current aggregate absent after rollback; previous committed journey intact; FAILED evidence has journey/model/operation/scope; dependent journey waits; retry neither duplicates nor skips validation |

Record actual results, versions, company, run ID, evidence counts and traceback where relevant. Do not mark native PASS using static-test output. Reporting floor checks are necessary diagnostics, not proof of comprehensive enterprise reporting coverage. Deficits must be filled through deterministic owner workflows in subsequent population work, not by lowering checks or writing report metrics directly.








