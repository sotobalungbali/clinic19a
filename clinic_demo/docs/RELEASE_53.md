# clinic_demo 19.0.1.0.53 — bounded journey migration

Authoritative source: clinic19a(20260916-041553).md. Its extracted files and SHA-256 are identical to the 20260915-231124 attachment. Companion clinic_inventory stays 19.0.1.0.4; this package changes only clinic_demo.

## Preserved authority

GOVERNING_MODEL_BY_MODEL.md is the exact supplied modelbymodel(1).md, saved with this full source release as the permanent HOW contract. The 24 Master Prompts retain WHAT: dataset scope, scenarios, personas, dates, business relationships and owner workflows. Do not request another prompt upload unless the user supplies a revision. Future corrections use the latest composite as the technical baseline.

## Changed behavior

- 40 execution journeys: all 35 existing generator contracts plus five source aggregates split from reports (insurance, membership, inventory, wallet, procedure).
- Reconcile Existing Dataset reconstructs progress from run-bound provenance, actual records, scope and existing semantic validators. Historical Done checkpoints alone cannot establish PASS.
- Execute Current, Execute Next / Resume, legacy Continue, Full, current phase and Complete Source Journeys dispatch through one journey engine.
- Each journey has its own savepoint. A caught journey failure rolls back that aggregate and records the diagnosis; earlier completed journeys survive when the RPC commits. A process crash or transaction-level failure can still roll back the whole RPC; no manual commit was introduced.
- Reconciliation rolls back any business mutation attempted by legacy validators. Only progress/evidence and validated checkpoint adoption persist.
- Missing, ambiguous or cross-company provenance cannot be silently adopted by a display-name guess. Blocked records require explicit resolution; no broad automatic deletion.
- Consumer reports/dashboard/analytics are marked stale after source mutation. Re-execution of actual validated PASS skips business creation and reports Created=0.
- Reset Preview lists existing ownership policies and downstream impact before the existing confirmation wizard. Rebuild Retained Dataset uses the same generation engine and retains records that owner policy cannot delete.

## Evidence and limits

204 source/behavior tests passed, using contract analysis and record doubles. Seven owner guardrails passed at source/static level. Entire extracted composite parsed: 926 Python and 517 XML, zero parse failures. See evidence_53 for raw output. Native Odoo upgrade, database transactions, ACL enforcement and acceptance A–F have NOT been run here.

This is an execution-architecture migration, not a completed enterprise-volume expansion. Existing generators retain their baseline populations. Reporting Sufficiency exposes conservative minimum-density deficits for L1–L8 and blocks overall readiness when they fail; it does not generate filler or declare every reporting requirement complete. The fixed minimum-density gate is only a necessary diagnostic floor, not a substitute for the prompt's preferred volumes, all eight report families or valid statistics. Expected minimum reflects known provenance, not complete profile-specific expected counts. Reconciliation validates only identities with verified provenance plus each existing owner's semantic checks; it is not a universal discovery/recovery tool for arbitrary unbound historical records.

## Upgrade and execution

1. Stop Odoo and replace the entire clinic_demo folder with this package. Keep clinic_inventory 19.0.1.0.4 installed.
2. Start Odoo, Update Apps List, upgrade clinic_demo to 19.0.1.0.53.
3. Open the same Demo Run; Refresh Compatibility, then Reconcile Existing Dataset. Migration does not require Reset.
4. Open Journey Progress. Existing validated records should appear as ADOPT/PASS; dependent journeys wait when upstream evidence is incomplete.
5. Use Execute Next / Resume for one aggregate, or select a journey and Execute Current. Generate Full uses the same engine for all eligible journeys.
6. Validate after generation. Review Reporting Sufficiency separately. Insufficient enterprise population is a real remaining task, not a reason to reset.
7. For a deliberate reset test only: Reset Preview, inspect retained/reverse/delete decisions, then use the existing typed confirmation. Rebuild Retained Dataset resumes the same deterministic identities.

No claim of full ClinicOne dataset runtime completion is made by this release.








