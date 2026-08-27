# Source / Static Validation

Required runtime smoke test after installation:
1. create Finance Account mapped to a Cash journal;
2. create a Finance Category with counterpart account;
3. create/submit/approve/post an Internal Transaction and verify `account.move`;
4. create and post an Internal Transfer;
5. submit/approve Fund Request and create disbursement;
6. open Cash Session, count denominations, close and inspect variance;
7. refresh Treasury Position and inspect AR/AP/Wallet/Cashflow links;
8. print Treasury Position PDF.

Until those tests pass in the user's Odoo PC, runtime status remains PENDING.
