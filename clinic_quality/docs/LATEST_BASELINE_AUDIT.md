# Latest Baseline Audit — 2026-08-21

Authoritative file: `clinic19a(20260821-080252).md`.

## Baseline identity

- file sections: **1,608**
- ClinicOne manifests: **38**
- addon 34 `clinic_incident_event`: **19.0.1.0.0**
- addon 35 `clinic_quality`: **ABSENT**

Numeric-prefix basename files are backup material and are not used as live
contracts.

Only recursively imported Python model source is authoritative.

## Critical upstream contracts

### Incident
Addon 34 owns:
- `clinic.incident`
- Incident Investigation
- Incident CAPA
- immutable Incident timeline.

Quality therefore escalates failed controls into `clinic.incident` and does not
create a parallel Quality CAPA model.

### Inventory
`clinic_inventory` owns:
- `stock.lot.clinic_quality_state`
- values `released`, `on_hold`, `rejected`
- `clinic_quarantine_reason`.

Quality links compliance evidence to Inventory Lots but does not alter these
disposition fields automatically.

### Branch
Current architecture provides:
- `res.company.default_branch_id`
- `res.users.allowed_branch_ids`
- `res.users.working_branch_id`
- `clinic.branch.company_id`.

### Quality source targets
Current live source confirms:
- `clinic.room.company_id`
- `clinic.staff.company_id`
- `clinic.staff.branch_id`
- `clinic.doctor.company_id`
- `clinic.treatment.company_id`
- `stock.lot` from native Stock / Clinic Inventory.
