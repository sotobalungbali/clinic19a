# Source / Static Validation and Runtime Acceptance

## Required source/static gates

- parse every Python file;
- parse every XML file;
- verify every manifest data file exists;
- ignore numeric-prefix backup files;
- verify latest baseline contains `clinic_feedback 19.0.1.0.0`;
- verify `clinic_reports` did not already exist in the baseline;
- validate live-import source contracts rather than dead source files;
- validate 19 report keys and engine dispatch methods;
- validate every report-engine source field/path;
- validate Branch support/disable matrix;
- validate no source model is re-owned;
- validate Search/List/Form coverage for all five persistent report models;
- validate Odoo 19 Search architecture;
- validate no `<tree>`, legacy `attrs=`, `states=`;
- validate `models.Constraint` / `models.Index`;
- validate Odoo 19 privilege hierarchy and company rules;
- validate CSV/PDF/schedule services;
- validate source/static is kept separate from runtime.

## Runtime acceptance

1. Activate `clinic_reports`.
2. Open Report Catalog: verify 19 Active definitions.
3. Generate Revenue/Billing for a known date range.
4. Verify KPI totals against the underlying Billing records.
5. Open at least one Detail source record.
6. Download CSV.
7. Print PDF.
8. Finalize the run and verify scope/Metric/Detail immutability.
9. Generate AR Aging and verify overdue/aging values.
10. Generate AP and Cash Flow reports.
11. Generate Accounting and Indonesia Tax reports.
12. Generate Insurance report.
13. Generate Booking, Queue and Room reports.
14. Generate Inventory, Membership and Wallet reports.
15. Generate Encounter, Procedure and Triage reports.
16. Generate Adverse Event report.
17. Generate Post-Care report.
18. Generate Feedback report and verify true NPS = %Promoters - %Detractors.
19. Test a supported Branch report.
20. Attempt Branch on an unsupported definition and verify backend rejection/disabled UI.
21. Disable `policy_branch_scope_reports` and verify Branch cannot be forced by RPC.
22. Create a Schedule owned by a Reports Analyst.
23. Run Schedule Now.
24. Verify schedule links to generated Run.
25. Test scheduled auto-finalization in a test database.
26. Verify company record isolation.
27. Verify Report User cannot generate/finalize.
28. Verify Analyst can generate but cannot finalize.
29. Verify Manager can finalize and manage definitions/schedules.
30. Verify no source transaction changes state during reporting.

Until runtime acceptance succeeds:
**ODOO RUNTIME = PENDING**.
