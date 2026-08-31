# Runtime Repair 19.0.2.0.2 — Bootstrap-Safe Referral Settings

## Concrete runtime evidence

Odoo registered the new Referral fields on `res.company`, but the database
still lacked their stored columns. Web-session startup therefore failed with:

`psycopg2.errors.UndefinedColumn:
column res_company.clinic_referral_default_valid_days does not exist`

## Repair

The exact public field names remain available:

- `clinic_referral_default_valid_days`
- `clinic_referral_require_source`
- `clinic_referral_require_program_for_reward`

They are now non-stored computed/inverse fields persisted through
company-scoped `ir.config_parameter` keys.

Normal Odoo startup therefore does not require these three PostgreSQL columns
before the module upgrade.

## Compatibility

`migrations/19.0.2.0.2/pre-migrate-company-settings.py` copies values from old
stored columns when those columns exist. It safely does nothing if the columns
were never created.

No Referral workflow, Source/Program contract, Booking attribution, security,
sequence, Audit navigation, or downstream dependency is redesigned.

