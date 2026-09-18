# Release 61 — Stable report metric refresh

Package: clinic_demo 19.0.1.0.61, clinic_reports 19.0.1.0.1.
Baseline: clinic19a(20260917-093440).md.

The report engine previously deleted every metric before regenerating output.
Dashboard snapshot lines protect their source metric links with ondelete=restrict,
so refreshing FIN-REV failed before calculation. The owner report engine now
updates metrics by the existing unique (run_id, normalized code) identity, creates
new codes and deletes only codes no longer emitted. Duplicate normalized codes
are rejected. All 19 report engines use the same _add_metric boundary.

Existing snapshot IDs, metric links and copied snapshot values are preserved.
Drill-down to a metric on a non-finalized report shows the refreshed current value;
the snapshot's own stored value remains historical. Finalized/archived report
regeneration is still prohibited. No FK weakening, downstream snapshot deletion,
or manual SQL is introduced. Obsolete metrics still referenced by consumers
remain protected by FK restrictions: generation rolls back instead of silently
retaining stale metrics or destroying history. Detail replacement and CSV refresh
remain within the existing generation savepoint. Clinical source rows are untouched.

Upgrade:
1. Stop Odoo and fully replace both addon directories from this package.
2. Start Odoo and update Apps List.
3. Upgrade clinic_reports to 19.0.1.0.1, then clinic_demo to 19.0.1.0.61.
4. Same Demo Run: Refresh Compatibility, Reconcile Existing Dataset.
5. Execute Next / Resume once to retry management.reports.
A prior FAILED status may remain after Reconcile until successful execution.
Do not reset the dataset or remove dashboard snapshots manually.
After Reports passes, resume Dashboard then Analytics through the same journey
engine; upstream success marks those consumers for refresh. Expected next progress
is 32/40 if all report and retained source checks pass, not a completion guarantee.

Validation:
235 source/behavior tests PASS; clinic_demo and clinic_reports guardrails PASS.
935 Python and 517 XML parse successfully. All 41 companion manifests match the
updated version vector. ZIP integrity checked. Native Odoo execution is pending.
Record-double tests exercise the actual _add_metric method for repeat refresh,
reference identity preservation, new codes, cross-run isolation and duplicate
codes. Source checks verify obsolete cleanup within savepoint and FK retention.
The governing Model-by-Model prompt remains bundled. Overall readiness is not
claimed; 31/40 is the last user-confirmed runtime progress.
