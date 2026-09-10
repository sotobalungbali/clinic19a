# clinic_emar — Full Structural Inventory

## Baseline inventory

The active non-backup baseline supplied by the user contained **37 files**. It mixed:

- an imported `models/core/*` generation;
- a richer root `models/emar_*.py` / integration generation that was largely not imported;
- stock/account bridge prototypes;
- minimal ACL data;
- scaffold `views/views.xml`, `views/templates.xml`, controller/demo artifacts.

Files whose basename starts with digit `0` are excluded from all design/preservation decisions.

## Final ownership map

### Owned persistent models

1. `clinic.emar.medication.profile` — clinical medication policy per product/company.
2. `clinic.emar.prescription` — prescribing source of truth.
3. `clinic.emar.medication.line` — medication intent shared by prescription/order.
4. `clinic.emar.order` — executable medication order.
5. `clinic.emar.schedule` — planned administration event.
6. `clinic.emar.administration` — verified actual administration event.
7. `clinic.emar.alert` — safety/operational alert ledger.

### Transient model

- `clinic.emar.reschedule.wizard` — governed schedule rescheduling.

### Abstract mixins

- `clinic.emar.mixin.audit`
- `clinic.emar.mixin.inventory`
- `clinic.emar.mixin.billing`
- `clinic.emar.patient.safety.mixin`

### Odoo / ClinicOne extensions

- `res.company`, `res.config.settings`
- `clinic.patient`, `clinic.doctor`, `clinic.encounter`, `booking.booking`
- `clinic.treatment.product.usage`
- `account.move`, `account.move.line`, `account.payment`
- `stock.picking`, `stock.move`, `stock.move.line`

## Python structure

- `models/core/` — owned eMAR model behavior.
- `models/integrations/` — ClinicOne clinical/inventory/config/governance contracts and workflow guards.
- `models/mixins/` — reusable audit/inventory/billing helpers.
- `models/external_bridges/` — stock/account traceability extensions.
- `wizard/` — transient operational wizard.
- `tests/` — enterprise regression contracts.
- `tools/clinic_emar_guardrail.py` — source/static hard gate.

## Data / security

- eMAR role hierarchy: User, Prescriber, Medication Administrator, Manager/Pharmacist.
- ACL matrix in `security/ir.model.access.csv`.
- company record rules for all seven owned persistent models.
- RX / Order / Administration sequences.
- schedule due/missed cron.

## UI matrix

Every primary persistent model has dedicated **search + list + form** views. Schedule additionally has calendar execution context. Forms contain lifecycle statusbars and workflow actions where applicable; operational row/body/smart buttons are used only for real business actions.

## Critical integrity contracts

- Odoo 19 SQL constraints use `models.Constraint`; no executable legacy `_sql_constraints` remains.
- Order maintains downstream compatibility fields (`patient_id=res.partner`, `doctor_id=hr.employee`) plus canonical `clinic_patient_id`/`clinic_doctor_id`.
- Schedule/Administration/stock/account bridges resolve canonical clinical identities rather than copying raw IDs across comodels.
- Odoo 19 inventory UoM compatibility uses the `uom.uom.relative_uom_id` hierarchy.
- Clinical dose UoM is separate from physical inventory quantity/UoM; e.g. 500 mg may consume 1 tablet.
- Prescription/Order/Schedule/Administration state changes are ORM guarded.
- Schedule is not marked administered merely because a draft administration record exists.
- Completed administration and schedule finalization are atomic; schedule-state failure is not swallowed.


## Odoo 19 registry inheritance hardening

Concrete workflow-guard extensions are single-base `models.Model` classes. Shared validation uses a module-level helper; plain Python mixins are not combined with Odoo model bases. This preserves the guard behavior while avoiding Odoo 19 dynamic `__bases__` layout conflicts.

## Release 19.0.3.0.0 additions

- `migrations/19.0.3.0.0/pre-10-preserve_company_settings.py`
  preserves legacy stored company configuration into company-scoped parameters.
- `migrations/19.0.3.0.0/post-90-verify_schema.py`
  asserts all eight eMAR-owned tables exist after upgrade.
- `models/integrations/res_config_settings.py`
  keeps six `res.company.emar_*` compatibility fields as non-stored proxies.
- `wizard/emar_reschedule_wizard.py`
  contains an upgrade-window-safe transient vacuum.
- `models/core/emar_schedule.py`
  contains a schema-ready guard for the scheduled cron.

