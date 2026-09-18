

# ClinicOne Membership — Runtime Repair 2026-08-18 #04

## Baseline
- Source: user-supplied ClinicOne snapshot after V4.
- Previous version: `19.0.3.0.3`.
- Corrected version: `19.0.3.0.4`.

## Runtime defect
Odoo stopped while validating `views/contract_views.xml`:

`action_open_usages is not a valid action on membership.contract.benefit`

The failing button is inside the inline list of
`membership.contract.benefit` records rendered by the
`benefit_snapshot_ids` One2many field on `membership.contract`.

## Root cause
`type="object"` executes on the row/view model. The inline row model is
`membership.contract.benefit`, but the button incorrectly referenced
`membership.contract.action_open_usages`.

The child model already owns the correct enterprise action:
`membership.contract.benefit.action_view_usages`.

## Repair
The inline Entitlements button now calls:

`action_view_usages`

The parent contract smart button still correctly calls:

`action_open_usages`

No business model, field, workflow, ACL, record rule, entitlement logic,
accounting integration, package/eMAR traceability, or enterprise UI capability
was removed.

## Prevention
The source/static guardrail now resolves nested One2many/Many2many fields to
their actual comodel and validates every `type="object"` button against that
model's Python methods.

A regression test verifies the contract form Entitlements inline action belongs
to `membership.contract.benefit`.

## Status
Source/static validation: PASS.
Windows/Odoo runtime installation: PENDING.

