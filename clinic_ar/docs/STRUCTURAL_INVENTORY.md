# Structural Inventory

Persistent owner models:
1. `clinic.ar.invoice`
2. `clinic.ar.invoice.line`
3. `clinic.ar.payment`
4. `clinic.ar.allocation`
5. `clinic.ar.allocation.line`
6. `clinic.ar.followup.level`
7. `clinic.ar.followup`
8. `clinic.ar.statement`
9. `clinic.ar.statement.line`
10. `clinic.ar.integration.event`

Extensions:
- `res.partner`: credit policy, aging metrics, statement/follow-up portfolio
- `account.move` / `account.move.line`: reverse AR traceability
- `clinic.billing.invoice` / `clinic.billing.payment`: upstream billing bridge
- `res.config.settings`: company-scoped AR operating parameters

Accounting authority:
- Billing-linked AR reuses Billing's `account.move`.
- Manual AR creates standard Odoo customer invoice.
- AR receipt creates standard Odoo `account.payment` and requires successful receivable reconciliation.
- Open-credit allocation is represented by actual Odoo receivable reconciliation.



