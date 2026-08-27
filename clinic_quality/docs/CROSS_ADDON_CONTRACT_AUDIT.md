# Cross-Addon Contract Audit

## `clinic_incident_event`

Quality depends on addon 34 and consumes:
- `clinic.incident`
- `incident_type`
- `state`
- `_category_for_type()`
- `_log_timeline()`
- Incident Reporter security boundary.

Quality extends Incident only with source provenance:
- `quality_check_id`
- `quality_check_line_id`
- related `quality_sop_id`.

One failed Quality Control may create at most one Incident.

Quality does **not**:
- redefine Incident;
- redefine Investigation;
- redefine CAPA;
- auto-close Incident;
- bypass Incident Reporter access.

## `clinic_inventory`

Quality consumes:
- `stock.lot`
- `clinic_quality_state`
- `clinic_quarantine_reason`.

Those fields remain Inventory-owned. Quality does not automatically write
`released`, `on_hold` or `rejected`.

## Branch

Quality computes its own user branch-access helper from the existing
`allowed_branch_ids` contract. Company/branch record rules protect SOP
applicability, Templates, Checks, Control evidence and Schedules.

Addon 35 also consumes addon-34 company policy
`policy_branch_scope_incident_event`. When that policy is enabled, Quality
Checks and Schedules require a Branch so that any future critical
nonconformity remains legally escalatable into a valid Incident case. Incident
creation itself passes Branch only when that addon-34 policy is enabled.

## Room / Staff / Doctor / Treatment

Quality adds reverse-navigation counters/actions only.

It never changes:
- Room operational status;
- Staff lifecycle/KPI ownership;
- Doctor lifecycle;
- Treatment/Catalog lifecycle.

## Future owners

No hard dependency on:
- `clinic_integration_api`
- `clinic_audit`
- `clinic_analytics`

Although a historical `clinic_audit` copy exists in the current repository,
official sequence keeps generic Audit downstream. Quality uses its own
domain-specific evidence only.
