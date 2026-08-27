# Runtime Repair 2026-08-20 — Abstract Billing Mixin Monetary Currency Contract

## Symptom
Activating `clinic_wallet` failed while Odoo 19 built the model registry:

`AssertionError: Field clinic.wallet.billing.mixin.wallet_amount with unknown currency_field 'currency_id'`

## Root cause
`clinic.wallet.billing.mixin` is an `AbstractModel`.  Its `wallet_amount` and
`wallet_reserved` fields were defined as `fields.Monetary` with
`currency_field="currency_id"`, but the abstract model itself does not own a
`currency_id` field.  Odoo validates Monetary fields while setting up each
model class, including abstract models.

Adding a generic `currency_id` to the mixin would be unsafe because the mixin is
combined with `clinic.billing.invoice` and `account.move`, both of which already
own the authoritative document currency.

## Repair
- keep `wallet_amount` and `wallet_reserved` on the abstract mixin as neutral
  `fields.Float` fields so its registry contract is self-contained;
- redeclare both fields as `fields.Monetary(currency_field="currency_id")` on
  `clinic.billing.invoice`;
- redeclare both fields as `fields.Monetary(currency_field="currency_id")` on
  `account.move`;
- preserve all existing Wallet methods, views and Billing integration APIs;
- add runtime regression and static guardrail checks for the contract.

No Wallet business feature, reservation API, accounting flow, security rule,
portal workflow or reporting capability is removed by this repair.



