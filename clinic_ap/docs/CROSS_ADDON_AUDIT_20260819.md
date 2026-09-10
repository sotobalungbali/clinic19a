# Cross-Addon Audit — ClinicOne `clinic_ap` — 19 Aug 2026

Authoritative source basis: latest user-supplied ClinicOne aggregate snapshot for this build; files whose basename begins with digit `0` are excluded as backups.

## Upstream versions observed in the snapshot
- `clinic_ar`: 19.0.3.0.2
- `clinic_billing`: 19.0.3.0.1
- `clinic_membership`: 19.0.3.0.5

## Final ClinicOne dependencies
- `clinic_base`
- `clinic_treatment_catalog`
- `clinic_billing`
- `clinic_ar`

The addon does not hard-depend on unrelated ClinicOne domains merely because they coexist in the repository.

## Relational audit
- Direct relational field references in final AP Python source: 54
- Unique custom ClinicOne comodels referenced: 11 (including AP-owned models)
- Missing custom comodels: 0
- Missing owning-addon dependencies: 0
- Dependency cycles reachable from `clinic_ap`: 0

External custom comodel ownership used by AP:
- `clinic.billing.invoice` → `clinic_billing`
- `clinic.billing.line` → `clinic_billing`
- `clinic.treatment` → `clinic_treatment_catalog`

## UI bridge audit
The Billing parent form XML ID `clinic_billing.view_clinic_billing_invoice_form` exists in the supplied snapshot. Vendor, Accounting and Purchase form decorations use standard Odoo XML IDs. All decorations are runtime-safe/idempotent; a missing or changed parent view skips decoration rather than aborting AP installation.

## Dependency direction
`clinic_ap` consumes AR only for treasury cashflow projections; it does not take ownership of AR records. No reverse dependency from the supplied `clinic_ar` baseline creates a cycle.

