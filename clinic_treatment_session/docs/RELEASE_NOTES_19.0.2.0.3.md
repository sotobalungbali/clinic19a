
# Release Notes — 19.0.2.0.3

Patch release for the `operations.booking` runtime blocker.

Changed:
- `models/extensions/ext_room_device.py` public API compatibility;
- version/build metadata;
- source regression and guardrail evidence;
- patch ledger.

Preserved:
- owned models;
- historical public fields/methods;
- Booking/Patient/Doctor/Room extensions;
- workflow/security;
- stock/billing/referral/package/canonical bridges;
- views/configuration/migrations.

Runtime PASS must be established on the target Odoo database.
