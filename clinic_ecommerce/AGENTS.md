# ClinicOne `clinic_ecommerce` — Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- cart/checkout/payment architect;
- source workflow owner;
- transaction-model owner;
- an endless retry engine.

Architectural ownership:
- Odoo `website_sale` owns products/cart/checkout/sale-order behavior;
- Odoo `payment`/`sale` owns payment post-processing and sale confirmation;
- `clinic_booking` owns Booking lifecycle/overlap validation;
- `clinic_package` owns Package Allocation lifecycle/entitlements;
- `clinic_membership` owns Membership Contract lifecycle/benefits;
- `clinic_ecommerce` owns curated online catalog metadata and fulfillment orchestration only.

Forbidden:
- replacing Odoo checkout/payment flow;
- creating duplicate Clinic Billing invoices for Website Sales;
- calling `membership.contract.action_confirm()` automatically from eCommerce;
- bypassing membership paid-invoice policy;
- auto-reversing completed Package/Membership/Booking benefits when a sale is cancelled;
- silently ignoring branch policy;
- granting public ACL to backend eCommerce governance models;
- hard dependency on future `clinic_portal`, `clinic_marketing`, `clinic_integration_api`, `clinic_audit`, or `clinic_analytics`;
- executable legacy `_sql_constraints`;
- legacy `<tree>`, `attrs=`, or `states=`;
- list-valued `_inherit` without explicit `_name`.

Retry limit:
- maximum 2 bounded implementation attempts per verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause/architecture review.
