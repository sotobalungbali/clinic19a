# ClinicOne — clinic_triage_vitals Runtime Fix: Patient Menu XML-ID

## Runtime failure

Odoo 19 failed while loading `views/clinic_triage_vitals_menus.xml` because
the installed database did not contain:

`clinic_patient.menu_root`

The current ClinicOne source *does* define that XML-ID in
`clinic_patient/views/clinic_patient_menus.xml`, but the installed dependency
may come from an older source revision. Installing a downstream addon does not
upgrade the dependency's XML data automatically.

## Root-cause correction

The Triage root menu is now valid on its own in manifest-loaded XML:

- no external `parent="clinic_patient.menu_root"` is required during data load;
- all child menus still use local `clinic_triage_vitals` XML-IDs;
- `post_init_hook` tries to attach the Triage root below the Patient root after
  the module has installed;
- the hook first tries `clinic_patient.menu_root`;
- if that XML-ID is absent, it inspects menus already owned by module
  `clinic_patient` and uses an unambiguous top-level Patient root when possible;
- if no safe Patient root can be identified, Triage remains a standalone root
  menu instead of failing installation.

The previous defensive Patient form integration remains unchanged.

## Preservation

- Business models removed: 0
- Baseline fields removed: 0
- Baseline methods removed: 0
- Workflow states removed: 0
- Manifest dependencies changed: 0
- `models/encounter_link.py` activated: NO
- Frozen `clinic_patient` edited or force-upgraded: NO
- Backup files beginning with `0`: excluded

## New regression gate

`CROSS_ADDON_XMLID_INSTALLATION_BLOCKER_GATE`

Manifest-loaded XML is scanned for hard ClinicOne sibling XML-ID references.
Presentation integration with a sibling addon must use the approved defensive
runtime pattern instead.

## Runtime status

Static hard gates must pass again after this correction.
Target-PC Odoo 19 install is still required before final freeze.
