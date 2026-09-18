# MASTER PROMPT 18 — Commercial, Billing & Financial Journey

Build: `clinic_demo 19.0.1.0.38` + `clinic_billing 19.0.3.0.5` +
`clinic_ap 19.0.3.0.3` +
`clinic_ar 19.0.3.0.3`

Prompt 17 is frozen after the same Demo Run completed all 19 registered
generators. Prompt 18 adds exactly three ordered checkpoints:

1. `commercial.billing`: Done Treatment Session to Clinic Billing to posted
   customer invoice, using owner workflow methods.
2. `commercial.ar`: billing-owned receivable linked to the same posted ledger;
   no duplicate accounting invoice is fabricated.
3. `commercial.ap`: supplier liability approved and posted through the AP owner
   workflow and standard vendor bill.

Every checkpoint performs the same whole-path preflight before its first
financial write. It verifies models, fields, comodels, methods, actor ACL,
referenced sources, billable lines, products, and company journals.

The synthetic enterprise manager is explicitly assigned every generated demo
branch before any branch-protected Treatment Session is read. Prompt 18 then
completes the exact service line whose commercial projection was intentionally
deferred by Prompt 16. The owner Billing bridge maps those real Billing lines to
the standard accounting invoice; zero-value placeholder ledgers are prohibited.
The same bounded actor receives Odoo's source-standard `Contact/Creation` role
before ACL preflight because AP creates one dedicated synthetic vendor. Existing
Contacts are not modified by this path.

Billing and AP receive stable `DEMO-*` numbers before lifecycle transitions. AR
uses the bounded `clinic_demo_ar_name` owner context; production callers retain
the standard AR sequence. Accounting move numbers remain owned by Odoo posting.

Posted financial documents use `fresh_db_reset_only`. Reset never deletes them,
puts them back in draft, or manufactures journal reversals. Real corrections use
the owner addon's reversal/cancellation workflow.

Progressive adoption accepts exactly the completed Prompt-17 set, or a failed
Prompt-18 checkpoint with an exact completed prefix and no committed references
in the failed/unexecuted suffix. The same Run resumes without Reset.





















