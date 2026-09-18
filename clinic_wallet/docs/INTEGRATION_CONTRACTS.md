# Integration Contracts

## Billing reservation API

The following public methods are preservation contracts because Clinic Billing consumes them:

- `clinic.wallet.reserve_funds(amount, reference=None, billing_model=None, billing_id=None)`
- `clinic.wallet.release_reserved(reference=None, billing_model=None, billing_id=None)`
- `clinic.wallet.validate_reserved_to_posted(amount, reference=None, billing_model=None, billing_id=None)`

The `(billing_model, billing_id)` pair is traceability metadata; it is intentionally not a relational inverse field because it can refer to multiple document models.

## Patient ownership

`clinic_patient` owns `res.partner.wallet_balance`. `clinic_wallet` extends the upstream compute contract and does not redeclare the field.

## Accounting ownership

Wallet configuration is stored on `res.company`. New code does not read or write `ir.property`; the historical `_upsert_wallet_liability_property()` method name is preserved only as a compatibility wrapper that writes the company field. Wallet journal lookup uses `account.journal.company_id/default_account_id`; account fallback domains use Odoo 19 `account.account.company_ids`.

## Dependency direction

`clinic_wallet` is downstream of ClinicOne addons through `clinic_ap`. No upstream addon is modified to depend on Wallet. Future modules (`clinic_finance`, `clinic_accounting`, etc.) are forbidden dependencies in this baseline.


## Membership plan compatibility

The historical field names `membership_tier_id` / `membership_tier_ids` are preserved for downstream custom code, but their comodel is the current Clinic Membership V6 owner `membership.plan`. Active membership is resolved through `membership_active_contract_id.plan_id`; the removed `clinic.membership.tier` model is never referenced.




