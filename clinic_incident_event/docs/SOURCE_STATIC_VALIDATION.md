# Source / Static Validation and Runtime Acceptance

Mandatory source/static validation:
- latest bundle identity;
- recursive live-import graph;
- Python AST parse;
- XML/QWeb parse;
- class-load import/symbol audit;
- manifest file/resource existence;
- numeric-prefix backup exclusion;
- upstream model/field/type/state contracts;
- Adverse Event/AE CAPA ownership preservation;
- Staff historical Incident contract;
- eMAR nested import contract;
- Queue doctor exact typing (`hr.employee`);
- Feedback related Patient exact typing (`res.partner`);
- Telemedicine secure-content non-copy;
- Branch policy and branch-record-rule contracts;
- owner Search/List/Form 5/5;
- nested One2many model switching;
- View field/object-button validation;
- Search-domain searchability;
- no `<tree>`, `attrs=`, `states=`;
- no executable `_sql_constraints`;
- `models.Constraint` / `models.Index`;
- Odoo 19 privilege hierarchy;
- no Portal/Public ACL;
- no future Quality/API/Audit/Analytics dependency;
- HARD GATE 11.

Runtime acceptance:
1. Activate addon 34.
2. Open Incident Settings.
3. Verify seeded Categories.
4. Create Draft Incident.
5. Report -> Triage -> Investigation -> Action Plan -> Verification -> Close.
6. Confirm direct state write is blocked.
7. Confirm Branch is required when policy enabled.
8. Confirm Branch must be empty when policy disabled.
9. Confirm unauthorized Branch is rejected/hidden.
10. Confirm serious Incident requires reportability review.
11. Complete structured Investigation.
12. Verify root-cause propagation.
13. Create CAPA, Start, Done, enter effectiveness note, Verify.
14. Confirm open CAPA blocks Verification.
15. Confirm unverified CAPA blocks Closure.
16. Confirm reportable Incident cannot close without regulator evidence.
17. Confirm Timeline immutability.
18. Confirm terminal Incident read-only behavior.
19. Create Incident from existing Adverse Event.
20. Confirm duplicate Adverse Event Incident is prevented.
21. Confirm upstream Adverse Event state unchanged.
22. Confirm Booking state unchanged.
23. Confirm Queue state unchanged.
24. Confirm eMAR state unchanged.
25. Confirm Feedback Escalation state unchanged.
26. Confirm Telemedicine Session/Thread state unchanged.
27. Confirm Secure Message bodies/internal notes are not copied.
28. Verify Patient Contact smart button.
29. Verify Staff incident counter.
30. Recompute Staff KPI incident count/rate.
31. Verify Incident User is read-only.
32. Verify Reporter permissions.
33. Verify Investigator permissions.
34. Verify Manager permissions.
35. Verify QWeb PDF.
36. Verify Search/List/Form/Kanban/Pivot/Graph.
37. Run multi-company and multi-branch regression.

Until these succeed: **ODOO RUNTIME = PENDING**.
