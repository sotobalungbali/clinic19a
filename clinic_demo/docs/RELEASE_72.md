# ClinicOne native Stock quantity closure — 19.0.1.0.72

The bounded inventory receipt now follows the Odoo 19 stock quantity contract
end to end. Its single move line is created with an explicit picked state and
business date, quantity comparisons use Odoo's native UoM conversion, native
completion suppresses backorders, and the returned completed move recordset is
validated before journey provenance is accepted.

- `clinic_inventory 19.0.1.0.8` owns the corrected private receipt API.
- `clinic_demo 19.0.1.0.72` retains all completed Model-by-Model journeys.
- Existing Draft/failed `population.inventory.m01` records are resumed; no
  dataset reset is required.




