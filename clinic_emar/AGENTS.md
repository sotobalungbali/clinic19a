# clinic_emar — Codex Bounded Implementation Contract

Codex is a **bounded implementation worker** for this addon. It is not the architect, not a simplifier, and not an autonomous retry loop.

Before modifying source, Codex must read:

1. `docs/ENTERPRISE_DEVELOPMENT_GUARDRAIL.md`
2. `docs/BASELINE_PRESERVATION_MATRIX.md`
3. `docs/INTEGRATION_CONTRACTS.md`
4. `docs/ENTERPRISE_COMPLETENESS_MATRIX.md`
5. `docs/STRUCTURAL_INVENTORY.md`
6. `docs/SOURCE_STATIC_VALIDATION.md`

## Allowed

- Implement a defect or bounded change whose architecture/owner/dependency decision is already defined.
- Add a regression test for the exact defect.
- Run `python tools/clinic_emar_guardrail.py` after changes.
- Improve comments/readability without changing ownership or behavior.

## Forbidden

- Delete models, fields, workflows, views, ACLs, rules, tests, integrations, or enterprise UX merely to obtain PASS.
- Change model ownership, dependency direction, canonical patient/doctor identity, or security policy without an explicit architecture decision.
- Re-introduce forward dependencies (`clinic_audit`, `clinic_branch`, `clinic_imaging`, `clinic_care_plan`, `clinic_package`, billing/finance/reporting addons).
- Re-introduce legacy `_sql_constraints`, `<tree>`, `tree,form`, XML `attrs`/`states`, or Odoo 18 UoM compatibility fields.
- Re-introduce Python multiple inheritance shaped like `class X(PlainHelper, models.Model)`; Odoo 19 registry model extensions must use Odoo-native inheritance or module-level helpers.
- Treat UI visibility as authorization; lifecycle/safety gates belong in ORM methods.
- Merge clinical dose and physical inventory quantity into one field.

## Retry hard stop

Maximum **2 bounded implementation attempts** for one defect and maximum **1 repetition of the same root cause**. If the same root cause remains, STOP and return evidence for architecture/root-cause review. Do not retry indefinitely.

## Acceptance

Static PASS is only a source gate. Do not claim completion until target Odoo 19 CE fresh install/upgrade and the clinical smoke workflow have passed.

