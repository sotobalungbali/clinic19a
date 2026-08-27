

# ClinicOne Membership — Runtime Repair 2026-08-18 / 02

## Incident

Activation of `clinic_membership` 19.0.3.0.1 reached view loading but failed at:

`views/plan_views.xml`

with:

`Invalid view membership.plan.search definition`

This proves the previous Odoo 19 security privilege repair loaded successfully
and the next blocker was the search-view schema.

## Root cause

The Membership search views still carried two legacy contracts:

1. 23 `<filter>` nodes used for Group By had no technical `name`.
2. 9 `<group>` nodes used legacy `expand="0"` and `string="Group By"` attributes.

Odoo 19's official `common.rng` requires `<filter name="...">`. The Odoo 19
generic search `group` definition does not accept the legacy `expand` or
`string` attributes.

## Corrective action

All nine persistent-model search views were normalized:

- `membership.plan`
- `membership.plan.benefit`
- `membership.contract`
- `membership.contract.benefit`
- `membership.usage`
- `membership.voucher`
- `membership.point.tx`
- `membership.hold`
- `membership.integration.event`

Every Group By filter now has a deterministic technical name such as
`group_plan_id`, `group_state`, `group_company_id`, or `group_tier`.

Legacy search-group `expand` and `string` attributes were removed.

## Prevention

The source guardrail now fails when:

- a search `<filter>` has no `name`;
- filter names are duplicated within one search view;
- a search `<group>` contains legacy `expand` or `string` attributes.

Regression test `test_26_search_views_follow_odoo19_filter_contract` covers the
runtime-loaded views as well.

## Preservation

No Membership business model, field, workflow, ACL, record rule, clinical
traceability, accounting integration, Package integration, eMAR integration,
or downstream outbox contract was removed.

## Release

Version: `19.0.3.0.2`

Status:
- Root cause: IDENTIFIED
- Source repair: DONE
- Static guardrail: PASS required before packaging
- Windows Odoo runtime activation: PENDING

