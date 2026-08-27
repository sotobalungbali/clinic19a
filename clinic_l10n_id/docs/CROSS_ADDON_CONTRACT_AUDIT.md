# Cross-Addon Contract Audit

Authoritative custom-source baseline: ClinicOne bundle supplied by the user on
2026-08-20 after `clinic_accounting` was installed.

## Verified upstream ClinicOne contracts

### `clinic_accounting`
Provides stored source classification on:
- `account.move.clinic_accounting_source`
- `account.move.line.clinic_accounting_source`

The PPN report uses this contract for Clinic Finance/Billing/AR/AP/Wallet/
Adjustment source filtering.

### `clinic_branch`
Provides:
- `account.move.branch_id`
- `account.move.line.branch_id`

The PPN report therefore supports multi-branch source filtering without moving
branch ownership.

### `clinic_billing`, `clinic_ar`, `clinic_ap`, `clinic_wallet`, `clinic_finance`
These modules remain upstream owners of their operational financial records.
Clinic localization reports only from posted legal accounting entries.

## Native Odoo 19 Indonesia contracts used

The addon is intentionally dependent on:
- `l10n_id`
- `l10n_id_efaktur_coretax`

Expected native runtime contracts include:
- partner NPWP through `vat`;
- `res.partner.l10n_id_pkp`;
- `res.partner.l10n_id_nik`;
- `res.partner.l10n_id_tku`;
- `res.partner.l10n_id_buyer_document_number`;
- `account.move.l10n_id_kode_transaksi`;
- `account.move.l10n_id_coretax_document`;
- `product.template.l10n_id_product_code`;
- `uom.uom.l10n_id_uom_code`;
- native Coretax document XML generation.

## Boundary results

- replacement Indonesian tax engine: 0
- replacement Coretax XML generator: 0
- proprietary invoice numbering engine: 0
- posted-number rewrite behavior: 0
- upstream ClinicOne ownership duplication: 0
- fragile custom upstream inherited-view XML IDs: 0

