# ClinicOne Accounting

Authoritative build: **19.0.1.0.0**

Blueprint responsibility:
> Integrates clinic finance with accounting ledgers, journal entries, and reports.

## Ownership

`clinic_accounting` owns:
- Clinic Accounting Ledgers (reporting/control scopes);
- Accounting Adjustment Vouchers;
- Accounting Period Close evidence and preflight;
- generated Accounting Statements and Statement Lines.

It does **not** own a second general ledger. Legal accounting entries remain in
Odoo `account.move` and `account.move.line`.

It integrates upstream:
- `clinic_billing`
- `clinic_ar`
- `clinic_ap`
- `clinic_wallet`
- `clinic_finance`

`clinic_l10n_id` is intentionally not a dependency because localization follows
Accounting in the ClinicOne addon sequence.

## Runtime status

The packaged guardrail proves source/static readiness only. Final completion
requires install and runtime smoke tests in the user's Odoo 19 CE environment.
