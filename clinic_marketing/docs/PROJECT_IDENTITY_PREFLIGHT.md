# PROJECT IDENTITY PREFLIGHT - HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_marketing`
- OFFICIAL SEQUENCE: addon 32 of 39
- AUTHORITATIVE BLUEPRINT:
  - **Manages campaigns, promotions, and communication with patients via email/WhatsApp.**
- AUTHORITATIVE BASELINE:
  - latest user bundle: `clinic19a(20260821-003600).md`
  - `clinic_portal`: 19.0.1.0.0 installed/frozen
  - `clinic_ecommerce`: 19.0.1.0.0
  - `clinic_dashboard`: 19.0.1.0.0
  - `clinic_reports`: 19.0.1.0.0
  - `clinic_inventory`: 19.0.1.0.2
- AUTHORITATIVE FAILED ADDON BASELINE: `clinic_marketing` 19.0.1.0.0
- REPAIR TARGET: `clinic_marketing` 19.0.1.0.1
- CURRENT RUNTIME STATUS: PENDING.

## Ownership boundary

`clinic_marketing` owns:
- patient marketing communication preferences;
- structured reusable patient segments;
- campaign orchestration;
- promotion presentation / CTA wrappers;
- immutable campaign recipient snapshots;
- WhatsApp communication intent/evidence;
- synchronization of campaign delivery evidence.

It does NOT own:
- patient identity;
- Branch master data;
- treatment/package/membership/billing pricing;
- voucher redemption;
- eCommerce checkout/fulfillment;
- Booking;
- Clinic Billing;
- feedback/NPS facts;
- Odoo Email Marketing's sending/tracking engine;
- a third-party WhatsApp gateway;
- future regulatory audit or predictive analytics.

## Email ownership

Odoo `mass_mailing` remains the Email Marketing engine. ClinicOne creates and
links native `mailing.mailing`, applies the governed Patient audience through
an Odoo mailing domain, queues it through the native workflow, and synchronizes
the native `mailing.trace` evidence.

## WhatsApp ownership

The base addon stores governed patient message intent, destination snapshot,
manual `wa.me` handoff, and delivery evidence. `_dispatch_via_gateway()` is a
provider-neutral extension hook. Future `clinic_integration_api` may override
that transport without becoming a current dependency.

