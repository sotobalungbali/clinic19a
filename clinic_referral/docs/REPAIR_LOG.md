# BOUNDED IMPLEMENTATION REPAIR LOG — HARD GATE 14

Maximum bounded implementation repair attempts: **3**.

Initial implementation is validated before counting a repair.

- Repair #1: PASS — split Referral navigation/drill-down methods into `referral_navigation.py` after HARD GATE 5 rejected a >950-line God-class threshold. No business contract changed.
- Repair #2: PASS — source-contract audit restored the historical `is_applicable()` company semantics: `company_id` remains administrative ownership, while `allowed_company_ids` is the explicit eligibility restriction. The new Branch eligibility check remains additive.
- Repair #3: PASS — latest authoritative-source preservation audit restored the legacy public `name_get()` methods on Referral, Program and Source in addition to Odoo 19 `_compute_display_name`, preventing downstream compatibility loss.

After the third implementation repair, further implementation changes require
concrete Odoo runtime evidence.

## Runtime Evidence Repair — 19.0.2.0.2

The original 3/3 bounded implementation attempts remain closed. This runtime repair is permitted only because the user's Odoo log provides concrete PostgreSQL `UndefinedColumn` evidence. The repair removes the bootstrap dependency on new `res_company` columns while preserving the public Referral settings field names.

## Runtime Evidence Repair — 19.0.2.0.2

Concrete Odoo 19 ParseError proved that the Booking inherited view used `@string` as an XPath selector. The selector was replaced with the stable technical `patient_id` field anchor. A suite-local regression gate now rejects any future `@string` inheritance selector in `clinic_referral` XML.

## Runtime Evidence Repair — 19.0.2.0.3

Concrete upgrade evidence proved a source/database XML-ID drift: `clinic_patient.view_clinic_patient_form` exists in current source but not in the installed database. Patient/Branch inherited views now resolve their parent `ir.ui.view` through Odoo XML `search=` using technical model/type/mode contracts. Referral root-menu placement similarly avoids a hard dependency on `clinic_patient.menu_root`.

## Runtime Evidence Repair — 19.0.2.0.4

Concrete Odoo ParseError proved that XML `search=` returned no inherited Patient parent, turning an `<xpath>` architecture into an invalid primary view. Patient/Branch smart buttons are now optional idempotent runtime UI bridges following the already-proven ClinicOne triage/package pattern. An incompatible historical view can no longer abort Referral upgrade.

## Runtime Evidence Repair — 19.0.2.0.5

Concrete Odoo 19 runtime evidence showed that `ir.ui.menu` does not accept `groups_id`; Odoo 19 uses `group_ids`. The Referral root is now declared with native `<menuitem groups=...>` syntax, allowing Odoo's converter to write the correct menu visibility field while preserving the parentless/bootstrap-safe root and 19.0.2.0.4 runtime reparenting.

