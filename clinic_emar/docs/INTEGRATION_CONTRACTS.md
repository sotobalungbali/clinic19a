# clinic_emar — Integration Contracts

## Upstream hard contracts

- `clinic.patient`, `clinic.patient.allergy` — patient identity and medication allergy safety.
- `clinic.doctor` — prescriber identity/license/governance.
- `booking.booking`, `clinic.encounter`, `clinic.vitals.intake` — clinical context.
- `clinic.room.session` — administration/schedule care-location context.
- `clinic.treatment.product.usage` — canonical ClinicOne inventory consumption record.
- Odoo `stock.*`, `account.*`, `hr.employee`, `res.partner`, `product.product`, `uom.uom` — logistics/accounting/workforce primitives.

## Order dual-reference contract

`clinic.emar.order` deliberately carries both:

- `patient_id` → `res.partner` and `doctor_id` → `hr.employee` for existing downstream compatibility; and
- `clinic_patient_id` → `clinic.patient` and `clinic_doctor_id` → `clinic.doctor` as canonical clinical identity.

All stock/account bridge code resolves the canonical ClinicOne records explicitly; it must never copy a raw ID from one comodel into another.

## Prescription contract

`clinic.emar.prescription.patient_id` remains `clinic.patient`; `doctor_id` remains `clinic.doctor`. This preserves clinical ownership and the existing care-plan integration contract.

## Medication line contract

`clinic.emar.medication.line` can belong to exactly one header (`order_id` XOR `prescription_id`) and always stores canonical `clinic.patient`/`clinic.doctor` context. Prescription → Order generation copies complete medication intent rather than only product/quantity.

## Downstream boundary

`clinic_emar` must **not** hard-depend on `clinic_imaging`, `clinic_care_plan`, `clinic_package`, `clinic_reports`, `clinic_dashboard`, `clinic_audit` or `clinic_branch`. Those addons may extend eMAR later. This one-way contract prevents circular/forward dependencies.

## Odoo 19 UoM and quantity contract

`uom.uom.relative_uom_id` defines Odoo 19 UoM hierarchy. `product_uom_id` is an inventory quantity unit and must share the product's root UoM. `dose_uom_id` is a clinical dose unit and is intentionally independent from the product inventory unit; profile dose limits are compared only after validating/converting within the same clinical UoM hierarchy.

Administration stores clinical dose separately from physical inventory use:

- `administered_qty` + `dose_uom_id` — actual clinical dose.
- `inventory_qty` + `inventory_uom_id` — stock/billing quantity.

ClinicOne inventory consumption must use the physical inventory pair, never the clinical dose pair.

## Company configuration compatibility contract — 19.0.3.0.0

Business code may continue to read:

- `company.emar_default_warehouse_id`
- `company.emar_auto_generate_schedules`
- `company.emar_require_patient_scan`
- `company.emar_require_product_scan`
- `company.emar_require_double_check_high_alert`
- `company.emar_overdue_grace_minutes`

These names are stable API contracts. They are intentionally non-stored on
`res.company`; storage is company-scoped through `ir.config_parameter`.
Consumers must not assume a physical `res_company.emar_*` column exists.
