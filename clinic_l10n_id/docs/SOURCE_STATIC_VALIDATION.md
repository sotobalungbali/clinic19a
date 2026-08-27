# Source / Static Validation

Required static gates:
- Python compile;
- XML parse;
- manifest data-file existence;
- six persistent owned models;
- Search/List/Form for all six;
- no `<tree>`;
- no legacy `attrs=` / `states=`;
- no executable `_sql_constraints`;
- Odoo 19 `models.Constraint` / `models.Index`;
- Odoo 19 privilege hierarchy;
- backend workflow transition guards;
- no custom tax engine;
- no custom Coretax XML engine;
- no custom upstream inherited-view XML IDs;
- current ClinicOne cross-addon field/model contract audit.

## Runtime acceptance

After installation:
1. Verify `l10n_id` and `l10n_id_efaktur_coretax` are installed.
2. Confirm company Country and Fiscal Country = Indonesia.
3. Confirm NPWP / PKP company identity.
4. Create Tax Profile and run **Load Native Indonesian Taxes**.
5. Review/refine sales and purchase PPN tax scope.
6. Validate and Activate the Tax Profile.
7. Create a Sales Journal Numbering Policy.
8. On a clean journal, Validate and Apply; on a journal with posted entries,
   verify ClinicOne refuses unsafe sequence mutation.
9. Generate a PPN Report for a test period.
10. Reconcile PPN lines to native posted tax lines.
11. Verify refunds reduce the period tax totals.
12. Drill from PPN line to native invoice and Coretax document.
13. Run Indonesia Compliance.
14. Review buyer NPWP/NIK, transaction-code, product-code, UoM-code, Coretax,
   and numbering results.
15. Mark Reviewed and Lock evidence.
16. Print PPN PDF and Compliance PDF.
17. Confirm scheduled prior-month PPN generation only runs for an Active profile.

Until these runtime tests pass on the user's PC, status remains **RUNTIME PENDING**.

