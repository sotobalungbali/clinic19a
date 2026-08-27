# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_l10n_id`
- OFFICIAL SEQUENCE: addon 24 of 39
- BLUEPRINT RESPONSIBILITY:
  - localizes system for Indonesia;
  - adds PPN;
  - adds tax reports;
  - adds invoice numbering rules.
- AUTHORITATIVE CLINICONE BASELINE: user bundle dated 2026-08-20
- VERIFIED UPSTREAM THROUGH: `clinic_accounting`
- NATIVE INDONESIA OWNERS:
  - `l10n_id`
  - `l10n_id_efaktur_coretax`

## Preservation rule

ClinicOne localization must consume native Indonesian tax and Coretax capabilities.
It must not duplicate Odoo tax definitions, chart of accounts, or e-Faktur XML logic.

## Allowed ownership

`clinic_l10n_id` owns:
- Clinic Indonesia Tax Profile;
- Clinic PPN report snapshots;
- Clinic invoice-numbering governance policy;
- Clinic Indonesia compliance evidence.

## Forbidden ownership

It must not own:
- a replacement `account.tax`;
- a replacement legal invoice ledger;
- a replacement Coretax/e-Faktur XML generator;
- a parallel Indonesia chart of accounts.

## Current status

SOURCE / STATIC: under validation  
ODOO RUNTIME: PENDING

