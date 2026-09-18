# clinic_inventory — Native Odoo Product Boundary Fix (2026-08-19)

## Runtime symptom
While activating a later ClinicOne addon with demo data enabled, Odoo attempted
to load the official `project_purchase/data/project_purchase_demo.xml` dataset
and raised:

`Clinical goods must use Odoo 19 inventory-tracked Goods configuration.`

## Root cause
`clinic_inventory` extends the shared Odoo model `product.template`. The custom
field `usage_type` had `default="medical"`. Therefore every newly-created Odoo
product — including products created by unrelated official modules and their
demo data — was silently classified as a ClinicOne Medical Consumable.

The ClinicOne constraint then correctly enforced the clinical stock rule against
a record that should never have been clinical in the first place. The defect was
therefore scope leakage at the product extension boundary, not a defect in
`project_purchase` and not a reason to weaken clinical validation.

## Corrective design
- `usage_type` is now opt-in (`default=False`).
- Native Odoo products remain unclassified by ClinicOne unless a Clinic Usage
  Type is explicitly assigned.
- Category-driven ClinicOne defaults remain supported through
  `product.category.clinic_get_category_default_template_vals()`.
- Clinical products still receive the existing strict rules for Service,
  Package, Medical, Cosmetic, Device, and Retail classifications.
- The main classification constraint now explicitly skips records with no
  Clinic Usage Type, documenting the ownership boundary in executable code.

## Guardrail added
`ODOO_NATIVE_PRODUCT_BOUNDARY_GATE` statically rejects any future truthy default
on `product.template.usage_type`, preventing recurrence of this cross-module
installation failure.

## Preservation
No model, field, workflow, dependency, ACL, view, sequence, or clinical business
rule was removed. The correction only prevents ClinicOne from claiming ordinary
Odoo products that were never explicitly classified as clinical.

## Status
- Source/static gate: must PASS before delivery.
- Windows Odoo runtime gate: PENDING until upgrade/restart and re-test on the
  target database.




