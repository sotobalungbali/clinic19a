# clinic_demo 19.0.1.0.62 — Acceptance evidence visibility

Baseline: clinic19a(20260920-225715).md, clinic_demo 19.0.1.0.61.

The Validate override already writes reporting status/evidence and two acceptance
rows before returning its notification. The previous notification did not request
a form reload. The supplied log shows action_validate returning HTTP 200 without
a subsequent Demo Run read in that excerpt. A stale form is consistent with Pending,
Draft and the old 38-result count. These artifacts do not establish database rollback.

Changes:
- Both successful and unsuccessful Validate notifications reopen the exact Demo Run
  through a standard window action, refreshing status and One2many evidence.
- Acceptance Results button opens only journey.actual_progress/reporting.sufficiency
  for this run. Existing Validation button continues to show all checks.
- Reporting Sufficiency now labels status, last evaluation time and population
  evidence; a Pending help message explains that Validate must evaluate the run.
- Evaluation timestamp is saved with the population result. Existing earlier evidence
  will acquire a timestamp on the next Validate.
- Explicit v61 fingerprint lineage allows metadata adoption using existing controls.

No population threshold is weakened and no business dataset is regenerated. This
release does not implement enterprise population expansion or certify completeness.
Owner validation failure remains failure even if population checks pass.
No new sequence, administrator bypass, manual commit or reset is introduced.

Install: replace the full clinic_demo directory, restart Odoo, Update Apps List,
upgrade clinic_demo to 19.0.1.0.62. On the same Demo Run: Refresh Compatibility,
then Validate. The form should reopen with current results. Open Acceptance Results
or Reporting Sufficiency and supply the saved population evidence if insufficient.
Do not reset the dataset. No companion addon changes are required.

Validation: 240 Python source/record-double tests pass; main enterprise guardrail
passes. Native Odoo/real PostgreSQL/browser execution is not available in this workspace;
these tests do not establish runtime acceptance or database persistence.














