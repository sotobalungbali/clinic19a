
# ClinicOne — clinic_patient Odoo 19 Enterprise Hardening Review

## Baseline policy
- Functional baseline: **FINISHED**
- Addon number: **4 / 39**
- Review mode: **technical hardening + enterprise presentation/security completion only**
- Target: **Odoo 19 Community Edition**
- Target path: `/mnt/d/projects/odoo19v/clinic19a/clinic_patient`
- Backup files whose filename starts with digit `0`: **ignored**
- Architecture redesign: **forbidden**
- Simplification/removal of existing function: **forbidden**
- Sibling-addon modification: **forbidden**
- Manifest dependency-set change: **forbidden**

## Preserved structural baseline
- 16 custom persistent business models preserved.
- 2 canonical Odoo model extensions preserved: `res.partner`, `res.users`.
- Existing fields preserved.
- Existing business methods preserved, except documented Odoo 19 API migrations.
- Manifest dependency set preserved exactly:
  `base`, `mail`, `contacts`, `uom`, `product`, `clinic_base`.

## Odoo 19 technical hardening applied
1. Migrated 12 legacy `_sql_constraints` assignments containing 15 SQL constraints to 15 `models.Constraint` declarations.
2. Migrated legacy `_name_search` implementations to Odoo 19-compatible `name_search(..., domain=None, ...)` for:
   - `clinic.patient`
   - `clinic.patient.condition`
   - `clinic.patient.vital`
3. Added Odoo 19-native `_compute_display_name()` where legacy label behavior otherwise depended only on `name_get()`:
   - `clinic.patient.identifier.type`
   - `clinic.condition.code`
4. Updated active Python action view modes from legacy `tree` terminology to `list`.
5. Added a small presentation-only `clinic.patient.action_open_contact()` helper for the existing `partner_id`.

## Existing-code completion
These artifacts are not new business domains; active source already referenced/consumed them:
- `data/patient_sequence.xml` supplies sequence code `clinic_patient.seq_patient_code` used by `clinic.patient.create()`.
- `data/patient_stage_data.xml` supplies stage flags already consumed by patient default/register/deceased automation.
- `report/patient_card_report.xml` supplies `clinic_patient.action_report_patient_card` already called by `action_print_patient_card()`.

## Enterprise UI completion
All 16 custom persistent models now have:
- Search view
- List view
- Form view

Main patient form includes:
- action buttons,
- Many2one statusbar (`stage_id`),
- smart/body buttons,
- structured identity/contact/status groups,
- Identifiers / Allergies / Conditions / Vitals notebook pages,
- One2many object buttons,
- chatter.

Additional professional forms expose existing safe actions:
- Set Primary Identifier
- Resolve Allergy
- Resolve Condition
- Open Attachments
- Open Patient
- Print Patient Card
- Register Patient

Canonical Odoo forms are extended rather than replaced:
- `res.partner`
- `res.users`

## Security hardening
The old active baseline had no loaded ACL for the real patient-domain models.
The hardened addon now includes:
- 16 internal-user ACL rows for the 16 custom persistent models.
- 7 ORM company record rules for company-scoped clinical records.
- No public ACL.
- No portal ACL.
- No UI-invisibility-as-security shortcut.
- No `sudo()` security bypass added.

A dedicated ClinicOne clinical-role architecture was **not invented**, because that would be an architecture decision outside this hardening scope.

## Human-friendly source structure
Views are split by domain:
- `views/patient_views.xml`
- `views/patient_identifier_views.xml`
- `views/patient_allergy_views.xml`
- `views/patient_condition_views.xml`
- `views/patient_vital_views.xml`
- `views/res_partner_views.xml`
- `views/res_users_views.xml`
- `views/clinic_patient_menus.xml`

The old scaffold `views/views.xml` is preserved in source but is no longer loaded as production UI.

## Enterprise Development Guardrail
Included in the addon:
- `AGENTS.md`
- `docs/CLINIC_PATIENT_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md`
- `docs/CLINIC_PATIENT_BASELINE_CONTRACT.json`
- `docs/CLINIC_PATIENT_STRUCTURAL_INVENTORY.md`
- `docs/CLINIC_PATIENT_UI_UX_MATRIX.md`
- `docs/CLINIC_PATIENT_ENTERPRISE_COMPLETENESS_MATRIX.md`
- `tools/clinic_patient_guardrail.py`

Codex role:
`LIMITED_IMPLEMENTATION_WORKER`

Codex is not an architect, simplifier, autonomous refactorer, dependency optimizer, or endless retry engine.

Maximum focused repair attempts per blocker/root-cause class:
`3`

After attempt 3:
`STOP` + blocker report + `MOVE_FORWARD_READY: NO`.

## Static hard-gate result
- HARD GATE 0: PASS
- HARD GATE 1: PASS
- HARD GATE 2: PASS
- HARD GATE 3: PASS
- HARD GATE 4: PASS
- HARD GATE 5: PASS
- HARD GATE 6: PASS
- HARD GATE 7: PASS
- HARD GATE 8: PASS
- HARD GATE 9: PASS
- HARD GATE 10: PASS
- HARD GATE 12: PASS
- HARD GATE 13: PASS
- HARD GATE 14: PASS
- HARD GATE 15: PASS

Static counts:
- `models.Constraint`: 15
- active legacy `_sql_constraints`: 0
- ACL rows: 16
- company record rules: 7
- custom models with Search/List/Form: 16 / 16

`CLINIC_PATIENT_STATIC_MOVE_FORWARD_READY: YES`

## Remaining runtime gate
ChatGPT cannot execute the user's target Odoo 19 PC runtime here.

Before freeze:
1. Run `python3 tools/clinic_patient_guardrail.py`.
2. Install/upgrade `clinic_patient` on the target PC.
3. Repeat upgrade.
4. Confirm registry load.
5. Smoke patient creation and automatic patient code.
6. Smoke Register Patient and stage behavior.
7. Smoke Print Patient Card.
8. Smoke Identifier / Allergy / Condition / Vital create/edit/actions.
9. Smoke multi-company isolation.
10. Confirm no critical traceback attributable to `clinic_patient`.

Until those pass:

`CLINIC_PATIENT_MOVE_FORWARD_READY: PENDING`
