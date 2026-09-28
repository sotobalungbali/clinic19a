# ClinicOne bounded Billing owner contract — 19.0.1.0.69

## Runtime finding

The source-proven Income account was passed through the Billing context, but
the final population check compared Odoo recordsets directly.  The same
account ID under different contexts can compare as a different recordset,
causing a false `explicit Income account was not honored` failure on the first
posted document.

The runtime log also showed queued mail attempting SMTP during HTTP
post-commit.  Population journeys must never create outbound side effects.

## Closure

- `clinic_billing 19.0.3.0.8` provides a private bounded owner API.
- The owner validates the source-proven Income account, builds exactly one
  draft move, verifies company/product, and freezes account plus
  `clinic_billing_line_id` provenance before posting.
- Identity checks use stable integer IDs rather than context-sensitive
  recordset equality.
- The same contract applies to all 12 Billing population periods.
- Population actor context now disables email notification and force-send for
  every Booking, Procedure, Billing, Insurance, Membership, Inventory, Wallet
  and Incident batch.
- Production callers retain their existing account fallback and notification
  behavior.
- The failed Billing period is rolled back by its savepoint; no Reset or
  cleanup is required.







