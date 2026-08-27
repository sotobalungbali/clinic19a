# ClinicOne — clinic_consent_legal Odoo 19 Review

## Scope
Technical hardening of a functionally finished ClinicOne addon for Odoo 19 CE. User backup files beginning with digit `0` are excluded. No sibling frozen addon is edited.

## Major decisions
1. All legacy SQL constraints are migrated to `models.Constraint`.
2. `clinic.consent.template` is reconciled with the already-frozen canonical model in `clinic_treatment_catalog` instead of being destructively re-owned.
3. Canonical `name` remains Template Name. Legal numbering is stored in `legal_reference`.
4. `legal_governed` isolates legal-only governance from existing canonical treatment-catalog templates, avoiding migration breakage for installed records.
5. Canonical `_description`/`_order` are preserved globally; legal ordering is view-level. Legal copy clears canonical unique `code` to avoid duplicate-code failures.
6. Legal-only requiredness is enforced at legal workflow boundaries rather than by schema requirements that could invalidate historical canonical records.
7. Patient/appointment/treatment/invoice integration uses effective model contracts and defensive optional presentation hooks rather than fragile sibling form XML-IDs.
8. Portal routes are read-only; signing remains a server-side model workflow.
9. Dormant aggregate/schedule files remain dormant.

## Odoo 19 compatibility changes
- `_sql_constraints` → `models.Constraint`.
- Active list actions/views use `list`, not legacy `tree` terminology.
- Backend aggregation uses `_read_group()` where required.
- Display naming uses `_compute_display_name()` while keeping compatibility wrappers where useful.
- Non-stored computed `is_expired` has a search method.
- Same-name model extension with multiple mixins uses explicit `_name = "clinic.consent.template"` plus list `_inherit` to preserve the canonical model identity.

## Static acceptance
The machine guardrail must pass all 15 owner hard gates plus structural/cross-contract checks. Runtime install/upgrade remains a separate mandatory gate.
