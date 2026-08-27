# HARD GATE 4 — Full Structural Inventory

## Persistent owner models — 8

1. `clinic.quality.sop`
2. `clinic.quality.sop.version`
3. `clinic.quality.sop.acknowledgement`
4. `clinic.quality.check.template`
5. `clinic.quality.check.template.line`
6. `clinic.quality.check`
7. `clinic.quality.check.line`
8. `clinic.quality.schedule`

## Abstract mixins — 2

- `clinic.quality.security.mixin`
- `clinic.quality.scope.mixin`

## Additive integrations

- `res.company`
- `res.users`
- `res.config.settings`
- `clinic.incident`
- `clinic.branch`
- `clinic.room`
- `clinic.staff`
- `clinic.doctor`
- `clinic.treatment`
- `stock.lot`

## Automation

Daily cron:
`Clinic Quality: Generate Due Checks`.

The cron creates Draft Checks only. It does not auto-start, auto-score,
auto-close or mutate source workflows.

## Reports

- Current SOP PDF
- Quality Check Evidence PDF

## Human-friendly Quality Check implementation split

- `quality_check.py` — owner fields, scoring, CRUD and contract validation
- `quality_check_workflow.py` — Start/Submit/Return/Escalate/Close/Cancel
- `quality_check_navigation.py` — smart-button/source/report navigation
