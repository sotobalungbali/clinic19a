# MASTER PROMPT 08 — FOUNDATION & ORGANIZATION DATASET

Version: `19.0.1.0.3`

Authoritative source SHA-256: `4f1c986c7e1bec0848bec6659315ba239288f8f0cc37959bcf0dd47f1ef7b214`

## Scope implemented

Prompt 08 activates the first real ClinicOne business-data generators:

1. `foundation.native`
2. `foundation.organization`

The registered scenario is:

`SCN-FOUNDATION-01 — Multi-branch ClinicOne Foundation`

## Native Odoo foundation

The generator reuses the selected Demo Run company and source-required native
records. It does not create a speculative second company or fake accounting
foundation.

Reused / validated when available:

- selected `res.company`;
- company base `res.currency`;
- Indonesia `res.country` (`code=ID`);
- company `resource.calendar`;
- owner-selected branch `stock.warehouse`;
- warehouse `stock.location` mapping where normal user access permits.

Source-owned side effects created by the owning ClinicOne models are tracked:

- `clinic.branch.create()` may create its generic `ir.sequence`;
- `clinic.branch.location.create()` may create a `resource.resource` for bookable
  locations.

No generic `sudo()` is added by `clinic_demo`.

Accounting journals, taxes, chart/account/payment-term specifics are intentionally
not invented in Prompt 08. Their source-required financial readiness is completed
in Prompt 18.

## Organization profiles

Compact:

- 1 branch
- 3 branch locations

Standard:

- 2 branches
- 6 branch locations

Full Enterprise:

- 3 branches
- 12 branch locations

Full Enterprise branches:

- `DEMO-BRANCH-001` — ClinicOne Demo Central
- `DEMO-BRANCH-002` — ClinicOne Demo South
- `DEMO-BRANCH-003` — ClinicOne Demo East

Locations use the source-valid `clinic.branch.location` types only:
`site`, `kiosk`, `room`, and `storage`.

## Security

`foundation.organization` declares:

`clinic_branch.group_branch_manager`

as its required owner role.

`Demo Dataset Operator` now implies Clinic Branch Manager so the operator authorized
to execute generation buttons can create source-valid branch/location records without
bypassing ClinicOne ACLs or record rules.

Pure System Administrator access to the UI does not bypass the owning branch security;
if the required branch role is absent, the checkpoint fails cleanly and logs the
required role.

## Idempotency

Each created/reused foundation record is bound to the stable Demo Reference registry.

Examples:

- `DEMO-COMPANY-001`
- `DEMO-CURRENCY-BASE`
- `DEMO-COUNTRY-ID`
- `DEMO-CALENDAR-COMPANY`
- `DEMO-WAREHOUSE-PRIMARY`
- `DEMO-BRANCH-001`
- `DEMO-BRANCH-001-SEQUENCE`
- `DEMO-LOC-B001-SITE`
- `DEMO-RESOURCE-B001-TREAT-A`

Rerun behavior:

- done checkpoint → skip;
- reset → checkpoint returns to Pending;
- missing reference → owning registered generator executes repair path;
- demo-owned branch/location → reused and safely updated/reactivated;
- reused native record → never deleted.

## Reset foundation

- `clinic.branch` → DEACTIVATE
- `clinic.branch.location` → DEACTIVATE
- `resource.resource` created for demo location → DEACTIVATE
- branch-owned `ir.sequence` → FRESH_DB_RESET_ONLY
- reused company/currency/country/calendar/warehouse → retained

If a demo branch was set as `res.company.default_branch_id`, reset clears that link
before deactivating the branch.

## Bounded execution

The Control Center now executes registered generators for real.

Per generator:

1. compatibility preflight;
2. group/owner-role check;
3. persistent checkpoint;
4. one database savepoint;
5. source-valid generation;
6. generator postcondition validation;
7. persistent counters/log;
8. stop on first unknown runtime root cause.

Prompt 08 has only two registered generators. Therefore Generate Full currently
completes Foundation + Organization only and reports that the registry is partial.
It does not claim the full enterprise dataset is ready.

## Validation

Prompt 08 validates:

- selected company exists;
- base currency exists;
- Indonesia country master exists;
- expected branch count per profile;
- expected branch-location count per profile;
- company consistency;
- branch consistency;
- non-negative/usable location capacity;
- warehouse readiness warning where relevant;
- duplicate prevention through Demo Reference registry.

Action `Validate` also re-runs the completed registered generator postconditions.

## Core addon changes

None.

No existing ClinicOne business addon is changed by Prompt 08.
