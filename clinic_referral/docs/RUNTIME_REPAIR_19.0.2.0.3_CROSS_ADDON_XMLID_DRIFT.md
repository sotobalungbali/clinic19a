# Runtime Repair 19.0.2.0.3 — Cross-Addon XML-ID Drift

## Concrete runtime evidence

During `clinic_referral` upgrade Odoo raised:

`ValueError: External ID not found in the system:
clinic_patient.view_clinic_patient_form`

The current source snapshot DOES contain that XML-ID. Therefore the problem is
not a typo in the latest source tree; it is source/database `ir.model.data`
drift in an already-installed ClinicOne environment.

## Repair

`clinic_referral` no longer requires the Patient and Branch primary form
external IDs to exist in the installed database.

Their `inherit_id` values are resolved using Odoo XML field `search=` against:

- model;
- view type;
- primary mode;
- non-inherited primary view.

This is supported by Odoo 19's XML converter for Many2one fields.

The Referral root menu also no longer requires `clinic_patient.menu_root`.
It searches for a top-level `ClinicOne` menu. If none exists in an older
database, Referral remains a top-level menu rather than failing the upgrade.

## Deliberately retained external IDs

The two Booking parent view IDs remain explicit because the user's actual
runtime upgrade already loaded and validated those records successfully:

- `clinic_booking.view_booking_booking_form`
- `clinic_booking.view_booking_booking_search`

The global Settings parent `base.res_config_settings_view_form` is an Odoo base
contract and remains explicit.

## Preserved repairs

- 19.0.2.0.1 bootstrap-safe `res.company` Referral settings;
- 19.0.2.0.2 Odoo 19 no-`@string` inherited-view selector repair.

No business workflow, schema ownership, ACL, rule, sequence, conversion logic
or downstream dependency is changed.

