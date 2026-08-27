
# ClinicOne — clinic_triage_vitals Odoo 19 Enterprise Hardening Review

## Baseline
- Project: ClinicOne
- Addon: `clinic_triage_vitals`
- Functional baseline: FINISHED
- Target: Odoo 19 Community Edition
- Target path: `/mnt/d/projects/odoo19v/clinic19a/clinic_triage_vitals`
- Backup policy: files whose basename begins with digit `0` are excluded.
- Review mode: technical hardening + enterprise completeness only.

## Preservation result
- Active custom persistent models preserved: 4 / 4
- Active inherited model extension preserved: `clinic.patient`
- Active import graph preserved: YES
- Dormant `models/encounter_link.py`: preserved and intentionally NOT imported
- Manifest dependency list: preserved exactly
- Existing fields removed: 0
- Existing methods removed: 0
- Existing lifecycle states removed: 0

## Odoo 19 compatibility hardening
1. Migrated 9 legacy `_sql_constraints` entries to 9 class-level `models.Constraint` declarations.
2. Added Odoo 19 `_compute_display_name()` implementations while retaining `name_get()` wrappers for older ClinicOne callers.
3. Migrated `clinic.triage.session.name_search()` from legacy `args=None` to `domain=None`.
4. Migrated active patient metrics from deprecated `read_group()` to `_read_group()`.
5. Migrated access guard from deprecated `check_access_rights()` to `has_access()`.
6. Hardened stored compute dependencies for SLA and priority against `triage_level_id.sla_minutes` and `triage_level_id.weight`.
7. Added explicit dependencies to patient-side non-stored metrics/latest-link computes.
8. Removed the unsafe global result limits in latest-session/latest-vitals lookup so one high-volume patient cannot hide another patient's latest record.
9. Added navigation-only helpers `action_open_invoice()` and `action_open_triage_session()`.
10. Modernized dormant encounter source from `read_group()` / `check_access_rights()` without activating the encounter integration.
11. Modernized the dormant scaffold XML vocabulary from `tree` to `list`.

## Existing sequence contract completed
The source already calls `next_by_code("clinic.triage.session")`. The addon now includes:
- `data/triage_sequence.xml`
- sequence code: `clinic.triage.session`
- reference format: `TRG/%(year)s/#####`

## Enterprise UI
Persistent models:
- `clinic.triage.level`
- `clinic.triage.tag`
- `clinic.triage.session`
- `clinic.vitals.intake`

Coverage:
- Search: 4 / 4
- List: 4 / 4
- Form: 4 / 4
- Triage Session Calendar: YES
- Triage Session Statusbar: YES
- Operational lifecycle buttons: YES
- Invoice smart navigation: YES
- Triage Tag session smart button: YES
- Vitals parent-session button: YES
- Patient smart buttons + Triage/Vitals notebook extension: YES
- One2many vitals navigation button: YES

## Security
- ACL: 4 / 4 persistent custom models
- Multi-company record rule: 4 / 4 persistent custom models
- Public ACL added: NO
- Portal ACL added: NO
- UI visibility is not used as a replacement for ORM security.

## Guardrail
The addon includes:
- `AGENTS.md`
- `docs/CLINIC_TRIAGE_VITALS_BASELINE_CONTRACT.json`
- `docs/CLINIC_TRIAGE_VITALS_STRUCTURAL_INVENTORY.md`
- `docs/CLINIC_TRIAGE_VITALS_UI_UX_MATRIX.md`
- `docs/CLINIC_TRIAGE_VITALS_ENTERPRISE_COMPLETENESS_MATRIX.md`
- `docs/CLINIC_TRIAGE_VITALS_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md`
- `tools/clinic_triage_vitals_guardrail.py`

Codex role:
`LIMITED IMPLEMENTATION WORKER`

Maximum focused repair attempts per blocker/root-cause class:
`3`

## Static result
- Python compile: PASS
- XML parse: PASS
- Constraint migration gate: PASS
- Active import preservation: PASS
- Manifest dependency preservation: PASS
- Field/method namespace collision: PASS
- Compute/inverse/search method contract: PASS
- Decorator field contract: PASS
- Relational inverse contract: PASS
- XML field/button contract: PASS
- Searchable computed-field contract: PASS
- Local XML-ID/action contract: PASS
- ACL + record-rule coverage: PASS
- Backup exclusion: PASS
- Owner hard gates: 15 / 15 PASS

`CLINIC_TRIAGE_VITALS_STATIC_MOVE_FORWARD_READY: YES`

## Runtime status
Target-PC Odoo 19 install/upgrade is still required.

`CLINIC_TRIAGE_VITALS_MOVE_FORWARD_READY: PENDING`

Do not declare the addon FINAL/FROZEN until the target Odoo runtime gate passes.

## Runtime Repair — Missing clinic_patient Parent View XML-ID

### Target runtime error
Odoo 19 rejected `views/patient_triage_views.xml` because the target database
did not contain:

`clinic_patient.view_clinic_patient_form`

The current ClinicOne source does contain that XML-ID in
`clinic_patient/views/patient_views.xml`, but installing a downstream addon does
not automatically upgrade an already-installed dependency. Therefore the
database and source revision can legitimately drift.

### Root-cause fix
- `views/patient_triage_views.xml` remains the human-maintainable inheritance
  template.
- It is intentionally removed from manifest `data`.
- `hooks.py` installs the optional patient-form extension from `_post_init_hook`.
- The hook first resolves the expected XML-ID and then falls back to the current
  primary `clinic.patient` form view.
- The hook validates `button_box` and `notebook` anchors before creating the
  extension.
- A savepoint prevents a partial optional view from leaking into the install
  transaction.
- Failure of this optional patient-form enhancement is logged but does not block
  installation of the core triage models, menus, security or workflows.

### Regression gate
`CROSS_ADDON_PATIENT_VIEW_RUNTIME_RESILIENCE_GATE: PASS`

This gate rejects a future change that puts `patient_triage_views.xml` back into
manifest data as a hard cross-addon XML-ID dependency.



## Runtime resilience update — Patient menu XML-ID

The target database demonstrated source/database drift for
`clinic_patient.menu_root`.  The Triage root menu is therefore now created
without a sibling parent XML-ID during manifest data loading.  `post_init_hook`
reparents it to a compatible Clinic Patient root menu when one can be resolved.
This prevents a navigation-only XML-ID mismatch from blocking the clinical
module installation.

Regression gate: `CROSS_ADDON_XMLID_INSTALLATION_BLOCKER_GATE`.
