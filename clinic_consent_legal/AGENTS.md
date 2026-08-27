# ClinicOne — clinic_consent_legal Agent Contract

## Role
Codex is a **LIMITED IMPLEMENTATION WORKER** for this addon.

Codex is:
- NOT ARCHITECT
- NOT SIMPLIFIER
- NOT PRODUCT OWNER
- NOT MODEL-OWNERSHIP DECISION MAKER
- NOT DEPENDENCY OPTIMIZER
- NOT AUTONOMOUS REFACTORER
- NOT ENDLESS RETRY ENGINE

`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_ROOT_CAUSE = 3`

After three failed focused attempts for the same blocker/root-cause class, STOP. Report the failing gate, exact command/traceback, root cause, files changed, attempts performed, and architectural decision required. Do not remove models, fields, workflows, security, UI, dependencies, or cross-addon contracts merely to make tests pass.

## Authoritative baseline
- Project: ClinicOne
- Addon: clinic_consent_legal
- Platform: Odoo 19 Community Edition
- Functional source baseline: user-supplied finished addon, excluding filenames beginning with digit `0`.
- Preservation contract: `docs/CLINIC_CONSENT_LEGAL_BASELINE_CONTRACT.json`.

## Ownership reconciliation
`clinic.consent.template` already exists in frozen `clinic_treatment_catalog`. This addon extends that canonical model in-place and adds legal governance. It must not silently redefine canonical Template Name semantics or modify the frozen sibling addon.

Canonical `name` remains the template name. Legal numbering is `legal_reference`. Existing canonical templates remain valid unless explicitly opted into `legal_governed`.

## Mandatory gates before runtime
Run:

```bash
python3 tools/clinic_consent_legal_guardrail.py
```

Static PASS is not final product completion. Target-PC Odoo 19 install/upgrade remains mandatory before freeze.
