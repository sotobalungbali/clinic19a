# ClinicOne `clinic_marketing` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- patient identity owner;
- pricing or discount engine owner;
- voucher owner;
- Email Marketing delivery-engine owner;
- Booking owner;
- Billing owner;
- WhatsApp gateway architect;
- regulatory Audit owner;
- Analytics owner;
- an endless retry engine.

Architecture authority:
- `clinic_patient` owns Patient Card / exact patient identity.
- `clinic_branch` owns Branch and `policy_branch_scope_marketing`.
- `clinic_treatment_catalog` owns Treatment pricing rules.
- `clinic_package` owns Packages and Package Vouchers.
- `clinic_membership` owns Membership Plans / Contracts.
- `clinic_billing` owns Billing Voucher Programs and redemption.
- `clinic_feedback` owns patient feedback/NPS.
- `clinic_ecommerce` owns Clinic storefront and fulfillment.
- `clinic_portal` owns patient web portal.
- Odoo `mass_mailing` owns email dispatch, blacklist/exclusion handling and
  open/click/bounce/reply tracking.
- future `clinic_integration_api` may implement automated WhatsApp transport.
- future `clinic_audit` owns regulatory audit.
- future `clinic_analytics` owns predictive analytics.

Forbidden:
- reimplementing treatment/package/billing discount calculations;
- generating a duplicate Booking, Billing, membership or eCommerce workflow;
- sending marketing to a channel without the configured ClinicOne consent policy;
- bypassing branch policy in UI or RPC;
- treating `self.env["model"]` as a Python class;
- future-addon hard dependencies;
- executable legacy `_sql_constraints`;
- `<tree>`, legacy `attrs=`, or legacy `states=`;
- unsafe PostgreSQL/Odoo identifiers;
- field/method technical-name collisions.

Retry limit:
- maximum 2 bounded implementation attempts per verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause / architecture review.

