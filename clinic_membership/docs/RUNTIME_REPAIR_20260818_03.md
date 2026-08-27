

# Clinic Membership Runtime Repair — 2026-08-18 / 03

## Symptom
Activation failed while validating `membership.plan.form`:

`Unknown field "account.account.company_id" in domain of python field 'income_account_id'`.

## Root cause
Odoo 19 `account.account` no longer owns a scalar `company_id`. It uses
`company_ids` and the model-level `_check_company_domain` contract.

The Membership V3 source still contained two legacy assumptions:

1. `membership.plan.income_account_id` domain referenced `account.account.company_id`.
2. `membership.contract._accounting_income_account()` fallback search also
   searched `account.account.company_id`.

Repairing only the view-facing field domain would have allowed installation to
progress but would have left a later runtime defect during invoice generation.

## Corrective action
- `income_account_id`: `check_company=True`.
- Field domain now filters only `account_type = income`; company compatibility is
  delegated to Odoo's native check-company contract.
- Added ORM constraint validating that the plan company belongs to the selected
  account's `company_ids`.
- Fallback income-account lookup now uses
  `account.account._check_company_domain(company)` under `with_company(company)`.
- Added static guardrail checks and regression test 27.

## Preservation
No Membership functional ownership, workflow, security, UI, entitlement,
voucher, loyalty, hold, clinical traceability, accounting linkage, or integration
contract was removed or simplified.

## Status
SOURCE/STATIC: PASS.
WINDOWS ODOO RUNTIME: PENDING.
