# Source / Static Validation — clinic_package 19.0.3.0.0

Authoritative source audit basis: ClinicOne snapshot supplied 18 Aug 2026.

Snapshot inventory:
- active non-backup files extracted: 877
- ClinicOne addon folders represented: 25
- files ignored because basename begins with digit `0`: 133

Final `clinic_package` hard-gate result:

- Python compile: PASS
- XML strict parse: PASS
- manifest/data file existence: PASS
- executable legacy `_sql_constraints`: 0
- `models.Constraint`: 20
- object buttons: 55
- missing package Python object methods: 0
- primary Search/List/Form matrix: 8/8
- stored `res.company.clinic_pkg_*` fields: 0
- unsafe concrete Odoo classes with multiple Python bases: 0
- regression test methods: 24
- migration scripts: 2
- backup-prefix files packaged: 0
- custom ClinicOne/booking comodel references checked against supplied snapshot: 27
- missing custom comodels: 0
- missing owning addon dependencies for those comodels: 0
- hard loadable cross-ClinicOne XML inherited-view references: 0
- runtime-safe parent view IDs checked in supplied source: patient, booking, care plan,
  eMAR order, eMAR schedule, eMAR administration, eMAR prescription — all present in current source

Status: **PASS — SOURCE/STATIC ONLY**.

Windows Odoo registry, module upgrade/install, UI smoke, security smoke, package workflow smoke,
voucher smoke, and eMAR traceability smoke remain runtime gates.
