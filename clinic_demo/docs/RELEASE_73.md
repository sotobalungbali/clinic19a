# ClinicOne native supplier receipt preparation — 19.0.1.0.73

The bounded supplier receipt no longer appends a second move line after Odoo
confirmation. It writes the native `stock.move.quantity` field, allowing the
Odoo 19 inverse to create or adjust the confirmation-owned line, then applies
picked state and the frozen business date to exactly that line.

- `clinic_inventory 19.0.1.0.9` owns the corrected receipt transition.
- `clinic_demo 19.0.1.0.73` explicitly adopts the runtime-pass `.72` lineage.
- The 37 completed journeys are retained and `population.inventory.m01`
  resumes without resetting the dataset.



