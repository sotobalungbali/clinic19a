# Source / Static Validation

The build must pass:
- Python compile;
- XML parse;
- manifest data-file existence;
- all 7 persistent models have Search/List/Form;
- ClinicOne Odoo 19 search contract;
- no `<tree>`;
- no `attrs=` or `states=`;
- no executable `_sql_constraints`;
- no list-valued `_inherit` without explicit `_name`;
- Odoo 19 `res.groups.privilege` hierarchy;
- company record rules;
- backend workflow guards;
- cross-addon field/model contract scan against the supplied source bundle.

## Runtime smoke acceptance after install

1. Configure a General Journal as Accounting Adjustment Journal.
2. Create an Accounting Ledger and open its Journal Entries.
3. Create a balanced Accounting Adjustment with at least two lines.
4. Submit -> Approve if threshold requires -> Post.
5. Verify one posted native `account.move` is created and source is
   `Accounting Adjustment`.
6. Open a Finance-generated move and verify `clinic_accounting_source`.
7. Generate Trial Balance.
8. Generate General Ledger and drill into a Journal Entry.
9. Generate Profit & Loss.
10. Generate Balance Sheet.
11. Generate Journal Audit and Clinic Source Summary.
12. Print Accounting Statement PDF.
13. Create Period Close and run Preflight.
14. Resolve blockers, Mark Ready, and close only in a safe test period.
15. Verify `res.company.fiscalyear_lock_date` advanced through native Odoo
    validation.
16. Print Period Close Evidence PDF.

Until these runtime tests pass on the user's PC, runtime status is **PENDING**.
