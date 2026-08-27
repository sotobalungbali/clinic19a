# ClinicOne — clinic_emar (Odoo 19 CE)

Enterprise Electronic Medication Administration Record for ClinicOne.

Version: `19.0.3.0.2`

## Scope

`clinic_emar` owns medication clinical profiles, prescriptions, executable medication orders, medication lines, administration schedules, verified administrations and medication safety alerts. It integrates upstream with patient, doctor, booking, encounter, triage/vitals, room/device and ClinicOne inventory models. Stock/account extensions provide traceability without changing model ownership.

## Core workflow

1. Create a prescription and medication plan.
2. Run patient-safety and prescriber-governance checks.
3. Validate/sign/cosign as policy requires.
4. Generate an eMAR Order without losing dose/SIG/route/frequency/duration/pricing intent.
5. Confirm the order and generate scheduled doses (PRN is intentionally unscheduled).
6. Verify each administration, including optional barcode, lot/expiry and independent double-check gates.
7. Record the actual clinical dose separately from physical stock quantity, then complete administration through the governed ClinicOne inventory consumption flow.
8. Close the order only when all schedules are terminal.

## Odoo 19 hardening

- Legacy `_sql_constraints` removed; SQL constraints use `models.Constraint`.
- Odoo 19 UoM hierarchy uses `relative_uom_id`; inventory UoM compatibility is validated against the product root unit.
- Clinical dose and physical inventory quantity are separate so dosage units cannot accidentally become stock-consumption units.
- List views use `<list>` and `view_mode="list,form"`.
- State transitions are ORM guarded; direct RPC/import `write({"state": ...})` cannot bypass the business actions.
- Company record rules cover all owned operational ledgers.
- Medication-line audit tracking is backed by `mail.thread` / `mail.activity.mixin` and a dedicated chatter, so `tracking=True` fields are valid Odoo 19 mail-tracked fields.
- No hard dependency on downstream `clinic_imaging`, `clinic_care_plan`, `clinic_package`, `clinic_branch` or `clinic_audit`.
- Audit remains available through the internal eMAR audit mixin and can soft-link to `clinic.audit.log` when that downstream addon exists.

## Runtime repair 2026-08-14

- Fixed Odoo 19 registry crash caused by Python multiple inheritance in
  `models/integrations/workflow_guard.py`.
- The four workflow-guard extensions now inherit only from `models.Model`.
- The shared state-write check is a module-level helper, while the public/private
  model method contracts remain available.
- ORM state protection is preserved; this is not a security simplification.
- Static guardrail now rejects any future class shaped like
  `class X(PlainPythonHelper, models.Model)` inside model source.

## Installation status

Source/static validation can be performed with:

```bash
python tools/clinic_emar_guardrail.py
```

See `docs/SOURCE_STATIC_VALIDATION.md` for the evidence matrix.

Windows/Odoo runtime install or upgrade remains a separate acceptance gate.


## Schema-safe source replacement — 19.0.3.0.0

The 2026-08-18 runtime evidence showed that a stored eMAR field added directly
to `res.company` could make every Website/web-client request fail before the
module upgrade had synchronized PostgreSQL. Release `19.0.3.0.0` removes that
single-point-of-failure without removing the public configuration API:

- `res.company.emar_*` field names are preserved for business-code compatibility.
- The six eMAR company settings are **non-stored computed proxies**.
- Values are persisted in company-scoped `ir.config_parameter` keys.
- `res.config.settings` loads/saves those values explicitly.
- An upgrade script preserves values from legacy physical company columns when
  those columns exist, and is a no-op when they never existed.
- The reschedule wizard vacuum and eMAR schedule cron are guarded during the
  brief source→schema synchronization window.

After replacing source, restart Odoo. The web shell should no longer depend on
`res_company.emar_*` columns. Then perform the normal module upgrade. For a
controlled command-line upgrade, use `tools/windows_recover_schema.ps1`.


## Runtime repair 2026-08-19 — migration API portability

Release `19.0.3.0.2` removes the migration layer's undeclared dependency on
`odoo.upgrade.util`.  Both the pre- and post-upgrade scripts use Odoo core
`Environment(cr, SUPERUSER_ID, {})`, so the source can upgrade on the target
Odoo 19 CE Windows runtime while preserving the same migration behavior.
