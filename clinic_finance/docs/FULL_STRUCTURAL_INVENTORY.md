# Full Structural Inventory

Persistent models:
1. `clinic.finance.category`
2. `clinic.finance.account`
3. `clinic.finance.transaction`
4. `clinic.finance.transfer`
5. `clinic.finance.fund.request`
6. `clinic.finance.cash.session`
7. `clinic.finance.cash.count.line`
8. `clinic.finance.position`
9. `clinic.finance.position.line`

Inherited standard models: `res.company`, `res.config.settings`, `account.move`, `account.journal`.

Abstract support: `clinic.finance.company.mixin`.

Enterprise services: sequences, cron, PDF treasury report, security privilege/groups/record rules,
Search/List/Form matrix, transaction and treasury Pivot/Graph analysis.
