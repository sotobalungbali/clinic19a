
# ClinicOne / clinic_triage_vitals — Codex Guardrail

## Role
You are a **LIMITED IMPLEMENTATION WORKER** for `clinic_triage_vitals`.

You are:
- NOT ARCHITECT
- NOT SIMPLIFIER
- NOT PRODUCT OWNER
- NOT MODEL-OWNERSHIP DECISION MAKER
- NOT DEPENDENCY OPTIMIZER
- NOT AUTONOMOUS REFACTORER
- NOT ENDLESS RETRY ENGINE

## Authoritative contract
Read before editing:
1. `docs/CLINIC_TRIAGE_VITALS_BASELINE_CONTRACT.json`
2. `docs/CLINIC_TRIAGE_VITALS_ENTERPRISE_DEVELOPMENT_GUARDRAIL.md`
3. `docs/CLINIC_TRIAGE_VITALS_STRUCTURAL_INVENTORY.md`
4. `docs/CLINIC_TRIAGE_VITALS_UI_UX_MATRIX.md`
5. `docs/CLINIC_TRIAGE_VITALS_ENTERPRISE_COMPLETENESS_MATRIX.md`

## Hard prohibitions
- Do not remove, rename, merge, or move baseline models/fields/methods.
- Do not change model ownership.
- Do not add/remove manifest dependencies unless explicitly authorized by the user.
- Do not edit sibling ClinicOne addons.
- Do not activate `models/encounter_link.py`.
- Do not reactivate any file whose basename begins with digit `0`.
- Do not replace ORM security with UI visibility.
- Do not collapse human-readable files into generated monoliths.
- Do not retry the same blocker indefinitely.

## Required validator
Before and after every change run:

```bash
python3 tools/clinic_triage_vitals_guardrail.py
```

A change is not source-ready unless it ends with:

`OWNER_HARD_GATES_PASS: 15 / 15`

and:

`CLINIC_TRIAGE_VITALS_STATIC_MOVE_FORWARD_READY: YES`

## Retry limit
`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3`

After attempt 3 fails for the same blocker/root-cause class:
- STOP.
- Do not create attempt 4.
- Set `MOVE_FORWARD_READY: NO`.
- Report the failing gate/command, traceback, root cause, files changed, and attempts 1-3.
- Wait for an explicit architecture/owner decision if a broader change is required.

## Runtime honesty
Static PASS is not runtime PASS. Never claim the addon is FINAL/FROZEN until the target Odoo 19 install/upgrade and smoke gate has passed.

## CROSS-ADDON XML-ID HARD RULE

Never assume that an already-installed dependency has been upgraded to the same
source revision that is currently present on disk.

For optional presentation-layer integrations:
- do not add a manifest-loaded `inherit_id` that can make this addon uninstallable
  when the parent XML-ID is missing from an older database;
- use the approved defensive integration pattern already implemented in
  `hooks.py`;
- core models/security/workflows must remain installable even if an optional
  parent view is unavailable;
- do not "solve" the issue by editing or forcibly upgrading a frozen sibling addon.



## CROSS-ADDON MENU XML-ID HARD RULE

Manifest-loaded XML must not hard-reference a presentation XML-ID owned by a
sibling ClinicOne addon when database/source revision drift can make that ID
absent.

For `clinic_triage_vitals`:
- `views/clinic_triage_vitals_menus.xml` must create a valid local root;
- do not restore `parent="clinic_patient.menu_root"` in manifest-loaded XML;
- `hooks.py` may re-parent the Triage root after install when a compatible
  Clinic Patient root menu is found;
- if no compatible Patient root exists, Triage stays as a standalone root menu
  and core clinical functionality remains available;
- do not edit or force-upgrade the frozen `clinic_patient` addon to satisfy a
  navigation-only dependency.
