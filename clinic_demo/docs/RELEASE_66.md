# ClinicOne Population Reconciliation Contract — 19.0.1.0.66

Baseline: `clinic19a(20260923-020742).md`; governing architecture:
`modelbymodel(10).md`.

## Runtime closure

The v65 reconciliation path invoked semantic validation before checking whether
a population journey had any provenance.  A never-executed `population.setup`
therefore tried to resolve `DEMO-POP-SETUP-WH-1` and was incorrectly recorded
as FAILED.

Version 66 establishes one deterministic reconciliation contract for all 97
population journeys:

- no provenance: MISSING / READY; owner validation is not invoked;
- partial provenance: exact missing-key count plus full owner validation,
  remaining PARTIAL/FAILED until repaired;
- complete provenance: exact identity inventory, scope checks and owner
  semantic validation are all required before PASS;
- unexpected prefixed provenance is BLOCKED;
- prior FAILED state is cleared to READY only when the savepoint left no
  population provenance; detailed historical errors remain in Logs.

The setup journey declares exactly 16 references: three warehouses, nine
locations and four wallets.  The other 96 domain/month journeys calculate their
complete primary and child provenance keys before mutation, including
encounters, policies, stock/accounting moves and owner event logs.

## Upgrade and resume

Upgrade only `clinic_demo` to 19.0.1.0.66.  Keep `clinic_billing` 19.0.3.0.7
installed.  Open the same Demo Run and run Refresh Compatibility, Reconcile
Existing Dataset, then Execute Next / Resume.  Do not reset the dataset and do
not create another run.

Expected immediate reconciliation result: the first 31 journeys remain PASS
and `Population / Shared resources` becomes READY with expected=16, existing=0,
missing=16.  Runtime execution remains subject to the target database's owner
workflows and ACLs.










