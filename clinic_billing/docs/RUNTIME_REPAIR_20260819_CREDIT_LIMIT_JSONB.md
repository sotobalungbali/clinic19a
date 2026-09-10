# Runtime Repair — Odoo 19 `res.partner.credit_limit` JSONB

## Symptom

During module upgrade Odoo aborts with:

`psycopg2.errors.CannotCoerce: cannot cast type numeric to jsonb`

for `res_partner.credit_limit`.

## Root cause

Odoo 19 `account` owns `res.partner.credit_limit` as a company-dependent Float.
Company-dependent fields are stored as JSONB. Historical ClinicOne Billing code
redeclared the same shared field as Monetary, which allowed a legacy scalar
numeric column to remain in the database.

## Repair

- ClinicOne no longer redeclares the core `credit_limit` field.
- Billing credit-control logic continues to use Odoo's core field.
- A pre-migration converts legacy scalar numeric data to the Odoo 19 JSONB
  company-dependent representation.
- The legacy scalar value is copied to every company that exists at migration
  time, preserving the former global behavior as closely as possible.
- Migration is idempotent when the database already uses JSONB.
- Unknown column types fail closed instead of coercing/destructively guessing.

## Runtime gate

Static validation does not prove database migration success. Upgrade of
`clinic_billing` on the target Windows/Odoo 19 database remains the runtime
acceptance gate.



