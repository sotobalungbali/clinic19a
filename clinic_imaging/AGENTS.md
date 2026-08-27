# ClinicOne `clinic_imaging` — Codex Boundary Contract

## Role
Codex is a **LIMITED IMPLEMENTATION WORKER**.

Codex is **NOT ARCHITECT**, **NOT SIMPLIFIER**, **NOT PRODUCT OWNER**, **NOT MODEL-OWNERSHIP DECISION MAKER**, **NOT DEPENDENCY OPTIMIZER**, **NOT AUTONOMOUS REFACTORER**, and **NOT ENDLESS RETRY ENGINE**.

## Authoritative baseline
- Project: ClinicOne
- Addon: `clinic_imaging`
- Platform: Odoo 19 Community Edition
- Baseline: the user-supplied finished ClinicOne source, excluding files whose filename starts with `0`.
- `models/models.py` and `models/xxx_clinic_imaging.py` remain dormant unless the owner explicitly changes the architecture.

## Preservation
Do not remove or simplify a baseline business model, field, workflow, action, security contract, or integration merely to make a test pass. Odoo 19 technical migrations are allowed only when they preserve the effective business surface.

The duplicate historical declarations of `clinical.imaging.type` and `clinical.imaging.device` are reconciled as in-place compatibility extensions. Their effective field surface remains owned by the dedicated master files.

## Retry limit
`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3`

After the third failed repair for the same root-cause class, STOP. Report evidence and set `MOVE_FORWARD_READY: NO`. Do not continue patch-version loops.

## Required gate
Run:

```bash
python3 tools/clinic_imaging_guardrail.py
```

No implementation may be described as FINAL/FROZEN solely because static or automated tests pass. Target-PC install/upgrade remains a separate gate.
