




# Runtime Repair 19.0.1.0.11 — Functional ACL Context

## Runtime symptom

`master.catalog` paused with:

`You are not allowed to create 'eMAR Medication Clinical Profile' (clinic.emar.medication.profile) records.`

The owner ACL allows creation only to `clinic_emar.group_emar_manager`.

## Root cause

The Demo Control Center correctly requires a System Administrator, but Odoo's
`base.group_system` does not bypass arbitrary owner-addon ACLs. Prompt 11 had been
creating all master records in the technical operator's environment. That worked for
models open to `base.group_user`, but failed on functional-manager-only masters.

A full Prompt-11/12 ACL audit identified the same class of restriction for:

- eMAR medication profiles;
- package policy/pricing/package/lines/events;
- membership plans/benefits/events;
- insurance plans/rules;
- wallet rules.

Prompt-12 room/device/booking-resource masters are available to internal users and do
not require a special functional manager context.

## Repair

The existing `DEMO-USER-MGR` Clinic Manager is used as the functional master-data actor.
Only source-existing manager groups required for the bounded master are added to that
demo-owned user. Restricted records are created, updated, resolved and validated with
`with_user(DEMO-USER-MGR)` while normal ACL and record rules remain active.

`DemoReferenceService` accepts optional `record_user` for actor-aware idempotency.
There is no `sudo()` in Prompt-11/12 generators and no owner ACL/record-rule change.

## Existing failed run adoption

A 19.0.1.0.10 run failed at `master.catalog` may adopt 19.0.1.0.11 when:

- `master.catalog` is the failed checkpoint;
- Prompt 10 checkpoints are already present;
- no Prompt-11 demo references were committed by the failed generator savepoint;
- no later Prompt-11/12 checkpoint shape exists.

Use the same Demo Run, do not Reset, run **Refresh Compatibility**, confirm
**Compatible**, then run **Generate Full Enterprise Dataset** again as System
Administrator.









