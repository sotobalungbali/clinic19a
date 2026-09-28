# ClinicOne bounded Billing monetary-line contract — 19.0.1.0.70

## Runtime finding

Odoo 19 represents a normal `account.move.line` invoice row with
`display_type = 'product'`.  The former bounded Billing contract filtered on
`not line.display_type`, so it discarded the valid product row and reported
that the move did not contain exactly one monetary line.

## Closed owner contract

- `clinic_billing 19.0.3.0.9` owns
  `_clinic_billing_product_invoice_lines()`.
- Product identity, not a false `display_type`, selects real invoice rows.
- Tax, payment-term, rounding, section, and note rows are excluded.
- The bounded owner API matches the one source line to one accounting product
  line, restores the explicit Income account and Billing-line provenance while
  the move is draft, and proves both values before posting.
- Population validation and the Insurance fallback consume the same owner
  classification; no duplicate line classifier remains.
- The contract applies to all twelve `population.billing.mNN` journeys.

## Continuation

Upgrade `clinic_billing` before `clinic_demo`, reuse the same Demo Run, refresh
compatibility, reconcile, then execute next/resume.  Do not reset the dataset:
the failed period-01 attempt was rolled back by its journey savepoint.






