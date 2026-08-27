# ClinicOne — clinic_triage_vitals Cross-Addon XML-ID Audit

## Manifest-loaded sibling ClinicOne XML-ID references

Result: **0**

The addon no longer requires a sibling ClinicOne presentation XML-ID during
manifest XML loading.

Core Odoo XML-IDs such as `base.group_user` and `base.group_multi_company`
remain declarative because they belong to hard framework dependencies.

## Defensive integrations

- Patient form: resolved/installed from `post_init_hook`.
- Patient root menu: local Triage root always loads; post-init re-parenting is
  attempted when a compatible Clinic Patient root exists.
- Encounter integration: `models/encounter_link.py` remains dormant.

## Installation principle

Clinical models, security, actions and Triage menus must remain installable
even if an already-installed sibling addon is at an older XML-data revision.
