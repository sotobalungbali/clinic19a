# clinic_demo 19.0.1.0.54 — deterministic reconciliation readers

Baseline: clinic19a(20260916-061124).md, SHA-256 dec6e50eb21ef44c85ad213cdef56b47f51382d3b79dbba07f1ef66541e5c9b0.

## Root cause and corrected contract

Version 53's provenance inspector used the Control Center caller for every business model. Owner generators instead use functional demo actors on restricted models. The first visible mismatch was master.catalog / clinic.emar.medication.profile, where the caller has no eMAR role even though the manager actor creates and validates the records.

The shared journey_read_context policy now selects a declared reader BEFORE record access, ACL checks, duplicate searches and company/branch checks. Reconciliation and Reporting Sufficiency use this same policy. Normal Odoo ACL and record rules still apply. No sudo, permission retries, role grants, sequence calls, or business mutations were added. Reader choice is included in reference evidence for diagnosis.

| Scope | Reader |
|---|---|
| Catalog eMAR medication profile | Verified DEMO-USER-MGR |
| Restricted commercial master models | Verified DEMO-USER-MGR |
| Imaging, eMAR prescriptions/orders, care, telemedicine | Verified DEMO-USER-DOC-001 |
| eMAR administration | Verified DEMO-USER-NUR-001 |
| eMAR schedules and post-care, including encounter post-care | Verified DEMO-USER-MGR |
| Referral, future follow-up, Billing/AR/AP, exception/integration, reports/dashboard/analytics and supplemental report sources | Verified DEMO-USER-MGR |
| Treatment sessions and their line | Doctor linked by the exact declared booking, checked against run-owned doctor-user provenance |
| Other existing foundation/organization/master paths | Existing Control Center operator, preserving original generator access |

Missing, ambiguous, inactive, reused non-owned or out-of-company actor provenance remains BLOCKED. This release does not silently grant an actor a missing role. Existing owner semantic validators still run in the read-only rollback savepoint. Genuine data defects remain visible.

Version/source adoption explicitly accepts predecessor 19.0.1.0.53 and retains historical checkpoint aliases. The existing 40-journey registry, deterministic identities, data, checkpoint history and reset policy are preserved.

## Install and resume

1. Stop Odoo. Fully replace clinic_demo with this package; keep companion addon versions unchanged.
2. Start Odoo, Update Apps List, upgrade clinic_demo to 19.0.1.0.54.
3. Open the same Demo Run. Refresh Compatibility, then Reconcile Existing Dataset.
4. Inspect Journey Progress. The reported eMAR rows are read through the declared manager; PASS still requires the actual record and owner validator to succeed.
5. Execute Next / Resume from the first incomplete journey, or Generate Full through the same engine. Do not Reset for this correction.

## Validation and limits

211 source/behavior tests passed. The addon guardrail and related owner guardrails passed at source/static level; raw results are in evidence_54. Entire composite Python/XML parse succeeded. Native Odoo upgrade and reconciliation are not executed in this environment and require runtime confirmation. No guaranteed PASS count is asserted. L1–L8 reporting population expansion remains incomplete as documented in release 53.

GOVERNING_MODEL_BY_MODEL.md retains the exact newest user-supplied prompt as the persistent execution/migration authority; the original dataset Master Prompt continues to govern content.







