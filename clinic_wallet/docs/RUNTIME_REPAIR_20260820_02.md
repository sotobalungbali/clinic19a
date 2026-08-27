# Runtime Repair 2026-08-20 — Multiple Inheritance Shadow Models

## Symptom

Activation failed during registry field setup:

`TypeError: Many2many fields clinic.billing.invoice.wallet.voucher_ids and
clinic.billing.invoice.voucher_ids use the same table and columns`

## Root cause

The Wallet integration classes used list-valued `_inherit` declarations without
an explicit `_name`:

- `ClinicBillingInvoiceWallet`
- `AccountMoveWallet`

In Odoo 19, automatic `_name = _inherit` only applies when `_inherit` is a
string.  With list-valued `_inherit` and no explicit `_name`, the ORM derives
the technical model name from the Python class name.  This accidentally created:

- `clinic.billing.invoice.wallet`
- `account.move.wallet`

The first shadow model inherited `clinic.billing.invoice.voucher_ids` and tried
to reuse the same Many2many relation table as the real Billing model, which the
Odoo registry correctly rejects.

## Repair

The integration classes now explicitly target the existing models:

```python
_name = "clinic.billing.invoice"
_inherit = ["clinic.billing.invoice", "clinic.wallet.billing.mixin"]
```

and:

```python
_name = "account.move"
_inherit = ["account.move", "clinic.wallet.billing.mixin"]
```

This preserves the Wallet mixin API while extending the real financial models
in-place. No voucher relation, billing field, accounting field, Wallet feature,
or upstream model ownership is duplicated or renamed.

A guardrail now rejects every list-valued `_inherit` without an explicit
`_name` inside `clinic_wallet`.


