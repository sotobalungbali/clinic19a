# Source / Static Validation

Required before delivery:
- Python AST parse;
- XML parse;
- manifest file existence;
- numeric-prefix backup exclusion;
- live-import audit of the user bundle;
- exact `clinic_post_care_followup 19.0.1.0.0` upstream baseline;
- `clinic_feedback` absent from baseline before build;
- six owned persistent models;
- no ownership duplication of `booking.feedback.link`;
- Search/List/Form for all six owned models;
- no `<tree>`;
- no legacy `attrs=` / `states=`;
- no executable `_sql_constraints`;
- `models.Constraint` / `models.Index`;
- Odoo 19 privilege hierarchy;
- backend workflow/security guards;
- no future-addon dependencies;
- no fake SMS/WhatsApp/API provider;
- search-domain field/searchability audit;
- combined baseline+addon view/method contract audit;
- public controller/template presence;
- runtime regression/contract tests.

## Runtime smoke acceptance

1. Activate addon 27.
2. Create a Satisfaction Survey and at least two questions.
3. Activate Survey and set it as Company Default.
4. Create a manual Feedback Request.
5. Send Email invitation to a test Patient.
6. Open public token form.
7. Submit rating 5 / NPS 9 and verify no escalation.
8. Submit a second request with rating 1 / complaint / NPS detractor.
9. Verify canonical Feedback is created and Service-Recovery Escalation appears.
10. Acknowledge -> Start -> Resolve Escalation.
11. Close Feedback after no open escalation remains.
12. Verify Patient, Doctor and Staff satisfaction rollups.
13. Submit an existing `booking.feedback.link` and verify canonical sync.
14. Verify old Booking feedback without a configured Survey still submits in Booking without crashing.
15. Complete a Queue item and verify its existing optional hook can create a Feedback Request.
16. Create Request from completed Encounter.
17. Create Request from completed Post-Care.
18. Verify opt-in automation OFF does nothing.
19. Enable automation in test DB and verify idempotent source requests.
20. Verify multi-company segregation.
21. Verify public expired/revoked tokens cannot submit.
22. Print Feedback Summary PDF.
23. Verify Pivot/Graph open.
24. Verify no Incident/Marketing/Portal/API addon is required.

Until these pass on the target PC:
**ODOO RUNTIME = PENDING**.
