# ClinicOne — clinic_booking Odoo 19 Enterprise Hardening Review

## Baseline policy
- Functional status: FINISHED baseline.
- User backup files whose filenames begin with digit `0`: excluded.
- Active runtime source is defined by `models/__init__.py`; dormant `models/xxx_clinic_booking.py` remains preserved but is not activated.
- No model, field, method, workflow, ownership, or manifest dependency is removed or simplified.

## Odoo 19 technical hardening
1. Migrated all **19 active legacy `_sql_constraints`** to class-level `models.Constraint` declarations.
2. Migrated the preserved dormant aggregate's legacy constraints as well, for **37 total `models.Constraint` declarations** and zero remaining `_sql_constraints` in non-backup model files.
3. Updated active Python action view modes from legacy `tree` to Odoo 19 `list`; removed `search` from action `view_mode` where it had been incorrectly included.
4. Updated Stock validation helpers from legacy `qty_done` / `quantity_done` / `move_lines` patterns to Odoo 19 quantity/move-line fields used by the active stock API.
5. Corrected booking invoice quantity mapping to use existing `booking.line.product_uom_qty` rather than falling back to `1.0`.
6. Added Odoo 19-native `_compute_display_name()` bridges where the existing source used legacy `name_get()` custom labels; compatibility wrappers are preserved.
7. Kept the active booking-line analytic distribution design and did not reintroduce the removed `account.analytic.tag` comodel.
8. Added the module-default feedback email template already referenced by `_get_mail_template()`, closing an existing local XML-ID contract instead of introducing a new workflow.

## Enterprise completeness layer
- 24 persistent custom models inventoried.
- Search/List/Form: 24/24.
- `booking.booking` also has Calendar.
- Main Booking form includes workflow Action Buttons, state Statusbar, Invoice/Appointment Smart Buttons, embedded Booking Lines, One2many row navigation, deposit/integration sections, notes and chatter.
- ACL coverage: 24/24 persistent custom models.
- Company record-rule coverage: 24/24 persistent custom models.
- No public/portal ACL introduced.
- Booking and feedback sequences supplied for sequence codes already consumed by existing source.

## Machine-checkable regression gates
The validator also checks:
- field/method namespace collisions;
- effective custom decorator dependencies;
- compute/inverse/search/selection method existence;
- booking-model relational comodel and One2many inverse contracts;
- active removed-comodel usage;
- XML model/field/button contracts including nested One2many rows;
- searchable computed fields in Search views;
- local XML-ID/action/`env.ref()` references;
- active import contract and dormant aggregate non-activation;
- exact manifest dependency preservation.

## Final static hard-gate result
- OWNER HARD GATES: 15 / 15 PASS.
- Python compile: PASS.
- XML parse: PASS.
- Odoo 19 import-XML structural gate: PASS.
- Manifest file-reference contract: PASS.
- Field/method namespace collision gate: PASS.
- Compute/inverse/search method gate: PASS.
- Relation/inverse gate: PASS.
- XML custom model field/button gate: PASS.
- Searchable computed-field gate: PASS.
- Local XML-ID/action/env.ref gate: PASS.

## Runtime status
Static PASS permits runtime testing only. Real Odoo 19 install, repeat upgrade and focused booking workflow smoke on the target PC remain required before freeze.
