# Source / Static Validation and Runtime Acceptance

Mandatory source/static gates:
- latest bundle identity;
- recursive live-import graph;
- exact upstream field/comodel/state contracts;
- Python AST and class-load symbol audit;
- XML/QWeb parse;
- manifest payload existence;
- no numeric-prefix backup files;
- 8 owner model inventory;
- existing Incident/CAPA ownership preservation;
- Inventory quality-state ownership preservation;
- exact Incident type compatibility;
- exact Inventory lot quality-state values;
- company/branch record-rule contracts;
- Search/List/Form 8/8;
- nested One2many model switching;
- View field/object-button validation;
- Search-domain searchability;
- Odoo 19 privilege hierarchy;
- no Portal/Public ACL;
- no `<tree>`, `attrs=`, `states=`;
- no executable `_sql_constraints`;
- Constraint/Index identifier safety;
- no fragile custom upstream inherited views;
- no future Integration API/Audit/Analytics hard dependency.

Runtime acceptance:
1. Activate addon 35.
2. Open Quality Settings.
3. Create SOP and Draft Version.
4. Submit Version for Review.
5. Approve Version and verify current-version snapshot.
6. Acknowledge Approved Version as linked Clinic Staff.
7. Void an acknowledgement as Quality Manager and preserve evidence.
8. Create Draft Quality Template and controls.
9. Activate Template.
10. Create Quality Check.
11. Start Check and verify controls are copied as snapshots.
12. Enter Pass/Fail/N/A/Observation results.
13. Verify required evidence blocks submission when missing.
14. Submit Check for Review.
15. Return for correction.
16. Resubmit.
17. Verify weighted score and result.
18. For critical failure, create Incident and confirm addon-34 ownership.
19. Confirm Quality user without Incident Reporter cannot bypass Incident ACL.
20. Close Quality Check.
21. Confirm closed evidence is immutable.
22. Create Room-scope Check.
23. Create Staff-scope Check.
24. Create Doctor-scope Check.
25. Create Treatment-scope Check.
26. Create Inventory-Lot-scope Check.
27. Confirm `stock.lot.clinic_quality_state` is not changed automatically.
28. Create and activate recurring Quality Schedule.
29. Run Now and verify Draft Check creation.
30. Run cron and verify recurrence advancement.
31. Confirm one failing Schedule does not abort all due Schedules.
32. Verify company/branch isolation.
33. Verify Search/List/Form/Kanban/Pivot/Graph.
34. Verify Current SOP PDF.
35. Verify Quality Check PDF.

Until these succeed: **ODOO RUNTIME = PENDING**.
