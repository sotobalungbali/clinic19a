# Runtime Repair 2026-08-19 #01 — `clinic_ar`

## Runtime evidence

Activation of `clinic_ar` 19.0.3.0.0 failed while validating
`views/ar_invoice_views.xml`.

Odoo reported:

`Unknown field "res.currency.company_id" in domain of python field 'currency_id'`

The generated domain came from `check_company=True` on a Many2one to
`res.currency`.

## Root cause

Odoo 19 `res.currency` is a global model. It has no `company_id` field.
`check_company=True` therefore generates an invalid company domain for this
comodel.

The defect existed on three direct owner fields:

- `clinic.ar.invoice.currency_id`
- `clinic.ar.payment.currency_id`
- `clinic.ar.allocation.currency_id`

## Corrective action

Removed `check_company=True` from the three `res.currency` Many2one fields.
Each field now uses an explicit active-currency domain and keeps the company
currency as its default.

Company consistency is enforced where it actually belongs: on company-owned
documents, journals, accounts, payments, billing documents, and other
company-aware relational records. Currency conversion continues to receive
the explicit AR/company context.

## Prevention

The Enterprise Development Guardrail now fails if a direct
`fields.Many2one("res.currency", ...)` in `clinic_ar` uses
`check_company=True`.

A runtime regression test asserts that `res.currency` has no `company_id` and
that the three AR owner currency fields do not enable `check_company`.

## Version

Repair baseline: `19.0.3.0.1`.

Runtime status remains PENDING until activation succeeds on the user's Odoo
19 CE Windows environment.
