# ClinicOne Patient Portal

Version: **19.0.1.0.0**

Official ClinicOne addon: **31 of 39**

Official blueprint responsibility:

> Provides web portal for patients to view bookings, invoices, and treatment history.

The addon extends Odoo 19 Customer Portal. It does not create a second
authentication system, second invoice portal, second booking engine, or second
clinical record.

Core patient routes:

- `/my/clinic`
- `/my/clinic/bookings`
- `/my/clinic/invoices`
- `/my/clinic/treatments`

Companion existing services are linked rather than duplicated:

- `/my/clinic-wallet`
- `/my/consents`
- `/my/orders`
- `/my/invoices`
- `/clinic/shop`

Runtime status remains **PENDING** until activation and browser/security smoke
tests succeed on the target Odoo 19 CE database.
