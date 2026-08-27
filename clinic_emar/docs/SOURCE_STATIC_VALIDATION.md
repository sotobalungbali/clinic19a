# clinic_emar — Source / Static Validation Report

## Verdict

**SOURCE / STATIC: PASS**  
**WINDOWS ODOO 19 CE UPGRADE: PENDING**  
**CLINICAL SMOKE WORKFLOW: PENDING**

Static success is not treated as runtime completion.

## Release

`19.0.3.0.0`

## Authoritative baseline

The 2026-08-18 user-supplied ClinicOne combined source was used as the
authoritative integration baseline.

- active files extracted for cross-addon audit: **874**
- active addon folders present in the supplied snapshot: **25**
- basename-prefix-`0` backup files ignored: **133**

## Local hard-gate result

`python tools/clinic_emar_guardrail.py`

Result:

- Python files: **33**
- XML files: **14**
- manifest data files: **15**
- manifest dependencies: **21**
- Odoo 19 `models.Constraint`: **9**
- executable legacy `_sql_constraints`: **0**
- object-action buttons: **43**
- regression test methods: **30**
- packaged backup-prefix-`0` files: **0**
- unsafe concrete Odoo Python multiple-base classes: **0**
- stored `res.company.emar_*` configuration fields: **0**
- schema-recovery migration scripts: **2**

**RESULT: PASS (SOURCE/STATIC ONLY; ODOO RUNTIME NOT ASSERTED)**

## Cross-addon contract audit

Clinic comodel references used by `clinic_emar` were found in the supplied
ClinicOne source, and their owning addons are declared dependencies where
required:

- `clinic.appointment` → `clinic_doctor`
- `clinic.doctor` → `clinic_doctor`
- `clinic.encounter` → `clinic_encounter`
- `clinic.patient` → `clinic_patient`
- `clinic.room.session` → `clinic_room_device`
- `clinic.treatment` → `clinic_treatment_catalog`
- `clinic.treatment.product.usage` → `clinic_inventory`
- `clinic.vitals.intake` → `clinic_triage_vitals`
- all `clinic.emar.*` comodels → owned by `clinic_emar`

Missing clinic comodels: **0**  
Missing required owner dependencies: **0**

The only hard external XML view reference in `clinic_emar` is:

`base.res_config_settings_view_form`

No hard ClinicOne cross-addon inherited-view XML ID is required for installation.

## Runtime-specific hardening in this release

- Six eMAR company settings keep the existing `res.company.emar_*` API but are
  non-stored proxies backed by company-scoped parameters.
- Legacy company-column values are preserved by an Odoo 19 migration script if
  those columns exist.
- Post-upgrade schema assertions cover all eight owned eMAR tables.
- Schedule cron and transient wizard vacuum are safe during the source/schema
  synchronization window.
- All 14 XML files parse after declaration normalization.
- Security CSV header parsing is robust to BOM/leading blank source artifacts.

## Final runtime gate

Do not mark `clinic_emar` completed/frozen until the user proves a successful
Odoo module upgrade and clinical smoke workflow on the target database.


## 2026-08-19 migration portability gate

The guardrail now rejects imports from `odoo.upgrade` inside addon migration
scripts and requires the Odoo-core `Environment(cr, SUPERUSER_ID, {})`
construction in both schema-recovery scripts.  This prevents a source/static
PASS from hiding an undeclared runtime dependency on the optional upgrade-util
library.
