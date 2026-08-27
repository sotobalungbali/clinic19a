# Source / Static Validation

Required before delivery:
- Python compilation;
- XML parsing;
- manifest data-file existence;
- numeric-prefix backup exclusion;
- six owned persistent model inventory;
- Search/List/Form for all six owned models;
- standalone enterprise Claim and Claim Line Search/List/Form;
- no legacy `<tree>`;
- no legacy `attrs=` / `states=`;
- no executable `_sql_constraints`;
- Odoo 19 `models.Constraint` / `models.Index`;
- Odoo 19 `res.groups.privilege`;
- backend transition/approval guards;
- no duplicate `_name = clinic.insurance.claim`;
- no duplicate `_name = clinic.insurance.claim.line`;
- no parallel insurer settlement ledger;
- computed fields used in search domains must be stored/searchable;
- cross-addon contract audit against the latest user bundle.
- live-import audit for upstream source files before treating fields as runtime contracts;
- addon-owned Partner/Appointment/Treatment Policy/Authorization bridge fields;

## Runtime acceptance

1. Install/activate addon.
2. Mark a Contact as Insurer / Payer.
3. Create and Activate an Insurance Plan.
4. Add a generic Benefit Rule and a treatment-specific rule.
5. Create a Patient Policy; Verify then Activate it.
6. Run Internal Eligibility and confirm Eligible evidence.
7. Create an Authorization from Booking.
8. Verify Booking lines are prepared into Authorization lines.
9. Submit -> Pending -> Approve/Partial.
10. Verify validity dates and payer/patient estimates.
11. Link/create Clinic Billing Invoice.
12. Create Billing-owned Insurance Claim from Authorization.
13. Verify Claim Policy/Authorization/line mapping.
14. Submit Claim; verify backend blocks invalid Policy/Authorization when configured.
15. Mark Under Review -> Approve -> Settle using existing Billing payment flow.
16. Verify historical Billing claim state synchronization still works.
17. Test Billing Manager legacy claim authority.
18. Test Insurance User/Coordinator/Adjudicator/Manager permissions.
19. Test multi-company visibility.
20. Print Authorization and Claim Evidence PDFs.
21. Run expiry crons in a safe test database.

Until these pass on the user's Odoo PC:
**ODOO RUNTIME = PENDING**.

