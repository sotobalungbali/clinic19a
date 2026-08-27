# HARD GATE 4 - Full Structural Inventory

## Persistent Clinic Accounting models

1. `clinic.accounting.ledger`
   - named reporting/control scope over Odoo journals/accounts/branches/source types

2. `clinic.accounting.adjustment`
   - controlled manual adjustment header
   - Draft -> Submitted -> Approved -> Posted

3. `clinic.accounting.adjustment.line`
   - debit/credit adjustment lines
   - standard Odoo account references
   - optional partner/analytic context

4. `clinic.accounting.close`
   - period-close preflight
   - evidence and native fiscal lock-date integration

5. `clinic.accounting.close.check`
   - generated preflight evidence and record drill-down

6. `clinic.accounting.statement`
   - persistent statement snapshot
   - Trial Balance
   - General Ledger
   - Profit & Loss
   - Balance Sheet
   - Journal Audit
   - Clinic Source Summary

7. `clinic.accounting.statement.line`
   - generated source lines and drill-down

## Abstract support

- `clinic.accounting.company.mixin`

## Inherited standard/upstream models

- `res.company`
- `res.config.settings`
- `account.move`
- `account.move.line`

## Enterprise services

- 3 sequences
- monthly prior-period Trial Balance scheduler
- Accounting Statement PDF
- Period Close Evidence PDF
- 4-role Odoo 19 privilege hierarchy
- company record rules
- 60 runtime regression/contract tests
- Enterprise Development Guardrail
