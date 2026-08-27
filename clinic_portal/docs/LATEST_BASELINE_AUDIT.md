# Latest Baseline Audit - 2026-08-21

Authoritative attached bundle:
`clinic19a(20260821-000508).md`

## Parsed project state

- bundle sections: 1,438
- ClinicOne addon manifests: 34
- `clinic_inventory`: 19.0.1.0.2
- `clinic_reports`: 19.0.1.0.0
- `clinic_dashboard`: 19.0.1.0.0
- `clinic_ecommerce`: 19.0.1.0.0
- `clinic_portal`: absent -> addon 31 is a new owner.

## Official blueprint extract

The embedded `ClinicOne_39_Addons_Specifications.pdf` states:

> `clinic_portal` - Provides web portal for patients to view bookings, invoices,
> and treatment history.

The implementation keeps those three surfaces as the core scope and links to
existing Wallet, Consent, Orders, and Clinic Shop pages without taking their
ownership.

## Runtime-source policy

Only files imported by each addon's `models/__init__.py` are treated as live
runtime contracts. Numeric-prefix backup files remain excluded.
