# Latest Baseline Audit - 2026-08-21

Authoritative attached bundle:
`clinic19a(20260821-014536).md`

## Parsed project state

- bundle sections: 1,515
- ClinicOne addon manifests: 36
- `clinic_inventory`: 19.0.1.0.2
- `clinic_reports`: 19.0.1.0.0
- `clinic_dashboard`: 19.0.1.0.0
- `clinic_ecommerce`: 19.0.1.0.0
- `clinic_portal`: 19.0.1.0.0
- `clinic_marketing`: 19.0.1.0.0 present as the failed runtime baseline.
- repaired target: `clinic_marketing` 19.0.1.0.1.

## Live-import contract policy

Only source imported by each owner's `models/__init__.py` is authoritative for
runtime contracts. Numeric-prefix backup files are excluded.

Verified source contracts:
- exact Patient Card / Contact linkage;
- Branch and company marketing-scope policy;
- Booking completion history;
- active Membership Contract;
- Feedback NPS classification;
- Billing Voucher Program;
- Package Voucher Batch;
- Treatment Pricelist Item;
- published Clinic eCommerce Catalog Item.

No future addon is required to install addon 32.

