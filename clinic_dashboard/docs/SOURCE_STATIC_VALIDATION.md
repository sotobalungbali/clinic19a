# Source / Static Validation and Runtime Acceptance

## Source/static hard gates

- parse all Python;
- parse all XML;
- parse Owl template XML;
- syntax-check JavaScript as ECMAScript module;
- verify every manifest data/asset path;
- verify build marker/version;
- ignore numeric-prefix backup files;
- verify latest baseline contains `clinic_reports 19.0.1.0.0`;
- verify `clinic_dashboard` is absent from the baseline;
- inspect only live-import Clinic Reports source;
- verify every seeded Report Key;
- verify every seeded Metric Code exists in the corresponding live Report engine;
- verify all Dashboard source model/field/method contracts;
- verify Search/List/Form for every owned persistent model;
- verify Odoo 19 Search syntax;
- verify no legacy `<tree>`, `attrs=`, `states=`;
- verify Odoo 19 privilege hierarchy;
- verify generated Snapshot/Line ACL is read-only;
- verify no future addon dependency;
- verify `clinic_reports` remains KPI owner.

## Runtime acceptance

1. Activate `clinic_dashboard`.
2. Confirm six company Dashboard Boards are seeded.
3. Open Interactive Dashboard.
4. Switch between all six Boards.
5. Test Date From/Date To scope.
6. Test company-wide scope.
7. Test a supported Branch scope.
8. Test a Widget whose Report does not support Branch and verify
   `Unsupported Branch Scope`, not silent company-wide fallback.
9. As Dashboard User, verify Refresh is unavailable.
10. As Dashboard Analyst, refresh Executive Dashboard.
11. Verify missing Report Runs are delegated to `clinic_reports`.
12. Verify existing exact-scope Report Runs are reused.
13. Verify Dashboard Snapshot and Lines are created.
14. Compare several card values against source `clinic.report.metric`.
15. Open card source Report.
16. Open card source Metric.
17. Verify trend appears only when previous comparable Report Run exists.
18. Verify Warning/Critical thresholds.
19. Verify target progress.
20. Open Snapshot Board backend Kanban.
21. Open KPI Analysis Pivot/Graph.
22. Verify Snapshot/Line direct create/write/delete is blocked.
23. Enable Automatic Refresh with a Dashboard Analyst owner.
24. Run due-refresh cron in a test database.
25. Verify one failed board does not abort every due board.
26. Run old-snapshot archive cron.
27. Verify snapshots are archived, never deleted.
28. Verify company isolation.
29. Verify `policy_branch_scope_reports` backend enforcement.
30. Verify no upstream transaction is changed by Dashboard refresh.

Until these runtime checks succeed:

**ODOO RUNTIME = PENDING**.


