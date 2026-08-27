# ClinicOne Integration API

Odoo 19 CE integration layer for ClinicOne development item **#37 / 39**.

The addon provides:

- explicit Bearer-only REST endpoints backed by Odoo service-user security;
- fixed ClinicOne resource adapters (no arbitrary model/domain/method RPC);
- API client scopes, company/branch narrowing, rate limits, and idempotency;
- provider registry with secret isolation and SSRF-conscious outbound transport;
- inbound webhook authentication;
- bounded outbound webhook events, subscriptions, delivery evidence, retry/dead-letter handling;
- provider bridges for Clinic Marketing WhatsApp, Telemedicine meeting provisioning, and Billing gateway webhook transaction matching.

Source/static PASS is not runtime completion. Runtime installation and smoke testing on the target Odoo database remain mandatory.
