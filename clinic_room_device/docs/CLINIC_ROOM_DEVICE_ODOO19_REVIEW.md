# ClinicOne — clinic_room_device Odoo 19 Review

## Baseline
- Functional status: FINISHED.
- Allowed changes: technical/Odoo 19 hardening and enterprise completeness.
- Files beginning with digit `0`: ignored as user backups.
- Manifest dependency list: preserved exactly.
- Dormant `models/inherit`: preserved and intentionally not activated.

## Odoo 19 hardening applied
1. Migrated all 18 legacy SQL constraints in non-backup source to `models.Constraint`.
   - 16 belong to the active custom models.
   - 2 are in dormant inherit source and remain dormant.
2. Migrated 5 legacy `name_search(... args=None ...)` signatures to `domain=None`.
3. Replaced legacy Python action view mode `tree` with `list` throughout non-backup source.
4. Removed dead Product Type value `product` from active Room Type / Device Category policy.
5. Removed `supplier_rank` domain hard-coupling because Accounting is not a manifest dependency.
6. Hardened optional Maintenance Request mapping to Odoo 19 field names:
   `maintenance_team_id` and Date `request_date`, only when the optional bridge fields exist.
7. Added the sequence records already required by existing source code.
8. Added professional Search/List/Form views for all 8 persistent custom models.
9. Added lifecycle statusbars/buttons using existing methods/states only.
10. Added ACLs and company record rules for all 8 persistent custom models.
11. Added machine-checkable model/field/method/view/relation/XML-ID guards.

## Explicit non-changes
- No model removed or merged.
- No existing field removed.
- No existing method removed.
- No workflow state removed.
- No dependency added or removed.
- No Core247 integration added.
- `models/inherit` was not activated.
- No backup `0*` file was used as the implementation baseline.

## Source gate
Run:
`python3 tools/clinic_room_device_guardrail.py`

Final runtime readiness remains PENDING until target-PC Odoo 19 install/upgrade passes.
