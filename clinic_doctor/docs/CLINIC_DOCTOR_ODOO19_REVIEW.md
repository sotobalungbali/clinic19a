
# ClinicOne — clinic_doctor Odoo 19 Technical Hardening Review

## Baseline
- Functional baseline: FINISHED (user-declared)
- Review mode: TECHNICAL_HARDENING_ONLY
- Target: Odoo 19 Community Edition
- Target path: `/mnt/d/projects/odoo19v/clinic19a/clinic_doctor`
- Files whose filename begins with digit `0`: excluded as user backups
- Upstream frozen/installed on PC: `clinic_base`, `clinic_staff`

## Source reviewed
- Non-backup addon files preserved: 23
- Active imported model modules: 7
- Persistent business models defined here: 6
- Active inherited model extensions: 1 (`res.partner`)
- Active declared business fields in structural contract: 150
- Active declared methods in hardened structural contract: 132

## Odoo 19 hardening applied
1. Migrated 7 legacy `_sql_constraints` entries to `models.Constraint`.
2. Added Odoo 19-native `_compute_display_name()` implementations for doctor, specialty, leave, and appointment while retaining `name_get()` compatibility wrappers.
3. Migrated custom `name_search()` signatures from legacy `args=None` to Odoo 19 `domain=None`.
4. Migrated active Python window action `view_mode` values from `tree` to `list`.
5. Added explicit core dependencies `account` and `sale` because active appointment fields reference `account.move` and `sale.order`.
6. Restored the already-authored/commented `clinic.appointment.patient_id -> clinic.patient` field because active onchange and constraint code dereferences it and `clinic_patient` is already a hard dependency.
7. Guarded optional `treatment_session_id` use so the base addon cannot crash when a downstream treatment-session field is absent.
8. Guarded the Primary Patients action when the optional patient-side `primary_doctor_id` extension is absent.
9. Reworked Specialty → Doctors navigation to use the specialty's own `employee_ids` relation rather than requiring optional `hr.employee.is_doctor` / `hr.employee.specialty_ids` fields from another addon.
10. Preserved all existing ClinicOne dependencies; none were removed.

## Explicit non-changes
- No model removed/renamed/merged/split.
- No existing active business field removed.
- No existing active business method removed.
- No workflow state removed.
- No dormant/commented model module activated.
- No sibling ClinicOne addon changed.
- No core247 integration added.
- `security/ir.model.access.csv` remains unloaded exactly as in the active baseline; security architecture was not invented during this technical-hardening pass.
- Scaffold views/templates/demo remain as supplied except no active business view architecture was invented.

## Important dependency note
The existing manifest already hard-depends on `clinic_audit`, `clinic_branch`, `clinic_room_device`, `clinic_treatment_catalog`, and `clinic_patient`. This hardening does not remove/reassign those dependencies because that would be an architecture decision. Installing `clinic_doctor` on a database where those dependencies are not installed may cause Odoo to install their current source versions as dependency closure.

## Guardrail
Included in the addon:
- `AGENTS.md`
- `docs/CLINIC_DOCTOR_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md`
- `docs/CLINIC_DOCTOR_BASELINE_CONTRACT.json`
- `tools/clinic_doctor_guardrail.py`

Codex role: `LIMITED_IMPLEMENTATION_WORKER`.
Maximum focused repair attempts per blocker/root-cause class: 3.
After attempt 3 fails: STOP, report blocker, `MOVE_FORWARD_READY: NO`.

## Static hard-gate result
- PYTHON_COMPILE: PASS
- XML_PARSE: PASS
- MANIFEST_CONTRACT: PASS
- ACTIVE_IMPORT_CONTRACT: PASS
- MODEL_FIELD_METHOD_CONTRACT: PASS
- ODOO19_CONSTRAINT_CONTRACT: PASS
- ODOO19_API_STATIC_COMPATIBILITY: PASS
- CRITICAL_HARDENING_CONTRACT: PASS
- ENTERPRISE_DEVELOPMENT_GUARDRAIL: PASS

`CLINIC_DOCTOR_STATIC_MOVE_FORWARD_READY: YES`

## Remaining target-PC runtime gate
Static PASS is not runtime completion. Before freeze:
1. Run `python3 tools/clinic_doctor_guardrail.py`.
2. Install/upgrade `clinic_doctor` on the target Odoo 19 PC.
3. Repeat upgrade.
4. Confirm registry load.
5. Run focused doctor/specialty/schedule/availability/leave/appointment smoke.
6. Re-run the guardrail.

Only after runtime PASS:
`CLINIC_DOCTOR_MOVE_FORWARD_READY: YES`

