# HARD GATE 4 - Full Structural Inventory

## Persistent ClinicOne localization models

1. `clinic.l10n.id.tax.profile`
   - company Indonesia identity/readiness
   - PPN sales/purchase tax scope
   - Coretax and numbering governance

2. `clinic.l10n.id.tax.report`
   - persistent PPN reporting snapshot
   - Output PPN / Input PPN / Net PPN
   - Clinic Accounting source scope
   - branch/journal filters

3. `clinic.l10n.id.tax.report.line`
   - generated native tax-line evidence
   - invoice, partner NPWP/NIK, tax, DPP, PPN
   - Clinic source and Coretax document traceability

4. `clinic.l10n.id.numbering.policy`
   - safe policy over native `account.journal.code`
   - dedicated credit-note sequence
   - secure-posted-entry control
   - refuses sequence mutation after posted entries exist

5. `clinic.l10n.id.compliance.run`
   - Indonesia readiness/compliance run
   - generated/reviewed/locked evidence

6. `clinic.l10n.id.compliance.line`
   - generated blocking/warning/clear checks
   - safe source-record drill-down

## Abstract support

- `clinic.l10n.id.company.mixin`

## Inherited native models

- `res.company`
- `res.config.settings`
- `account.move`
- `account.journal`

## Native Odoo dependencies intentionally consumed

- `account.tax`
- `account.move.line`
- `l10n_id_efaktur_coretax.document`
- `l10n_id_efaktur_coretax.product.code`
- `l10n_id_efaktur_coretax.uom.code`

## Services

- 2 sequences
- prior-month PPN scheduled snapshot
- PPN PDF
- compliance evidence PDF
- 4-role security hierarchy
- 6 company record rules
- 61 runtime contract/regression tests
- Enterprise Development Guardrail

