# Source / Static Validation

Required before delivery:
- Python compile;
- XML parse;
- manifest data-file existence;
- numeric-prefix backup exclusion;
- six owned persistent models;
- Search/List/Form for all six owned models;
- no `<tree>`;
- no `attrs=` / `states=`;
- no executable `_sql_constraints`;
- `models.Constraint` / `models.Index`;
- `res.groups.privilege` security hierarchy;
- backend workflow guards;
- no future-addon dependencies;
- no SMS/WhatsApp/API fake delivery;
- stored/searchable computed fields for every search-domain reference;
- `clinic.postcare.task.assignee_id` contract;
- current ClinicOne cross-addon model/field audit.

## Runtime acceptance

1. Activate addon.
2. Create Post-Care Protocol with patient instructions.
3. Add an Email reminder step and a required Check-in step.
4. Activate Protocol.
5. Complete a test Encounter.
6. Create Post-Care Plan from the Encounter.
7. Generate/activate Tasks.
8. Verify Staff smart counter shows assigned open task.
9. Verify an Email task can send to a patient with an email address.
10. Verify phone/internal/manual channels do NOT claim they were automatically sent.
11. Record a normal Check-in and complete required-response Task.
12. Record an attention/red-flag Check-in and verify Escalation is created.
13. Acknowledge -> Start -> Resolve Escalation.
14. Verify Plan returns from Escalated to Active when no open escalation remains.
15. Verify overdue cron changes stale task and creates one escalation only.
16. Verify auto-create setting OFF creates nothing automatically.
17. Turn setting ON in a test database and verify recent completed Encounter creates one Plan only.
18. Verify multi-company isolation.
19. Print Patient Instructions PDF.
20. Print Follow-up Summary PDF.

Until runtime tests pass on the target PC:
**ODOO RUNTIME = PENDING**.
