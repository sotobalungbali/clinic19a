# ClinicOne `clinic_portal` - Enterprise Development Guardrail

Codex is a **bounded implementation worker** only.

Codex is NOT:
- architect;
- simplifier;
- portal authentication owner;
- Booking owner;
- Billing/Accounting owner;
- Encounter/Procedure owner;
- secure-messaging owner;
- Audit owner;
- an endless retry engine.

Architecture authority:
- Odoo `portal` owns Customer Portal authentication and access invitation.
- `clinic_patient` owns patient identity and user/partner linkage.
- `clinic_booking` owns Booking workflow.
- `clinic_billing` owns Clinic Billing.
- Odoo Accounting Portal owns invoice download/payment interaction.
- `clinic_encounter` owns treatment/encounter/procedure data.
- `clinic_wallet` and `clinic_consent_legal` keep their existing portal pages.
- `clinic_ecommerce` owns Clinic storefront metadata and fulfillment.
- future `clinic_telemedicine_secure_messaging` owns doctor-patient messaging.
- future `clinic_audit` owns system-wide regulatory audit.

Forbidden:
- granting portal access outside native `portal.wizard`;
- exposing arbitrary patient IDs supplied by a browser;
- using commercial-partner family scope to expose sibling patient records;
- showing SOAP notes, diagnosis, assessments, vitals, internal comments, or
  unpublished documents in the generic portal;
- writing upstream Booking/Billing/Encounter state from portal view routes;
- future-addon dependencies;
- executable legacy `_sql_constraints`;
- `<tree>`, legacy `attrs=`, or legacy `states=`;
- database identifiers that exceed PostgreSQL/Odoo naming safety limits;
- field/method collisions or unsafe ORM technical names.

Retry limit:
- maximum 2 bounded implementation attempts per verified defect;
- maximum 1 repeat for the same root cause;
- then STOP and return to root-cause/architecture review.
