# HARD GATE 4 - Full Structural Inventory

## Owned persistent model

### `clinic.portal.profile`

Responsibilities:
- one profile per Company + Patient Contact;
- Patient Card linkage;
- native Portal User visibility;
- Draft / Active / Suspended / Archived workflow;
- Booking / Invoice / Treatment History feature policy;
- companion Wallet / Consent / Orders / Shop shortcuts;
- last Clinic Portal access timestamp/page;
- backend Booking / Invoice / Treatment counters;
- native Portal Access Management launcher.

## Additive inherited models

- `res.company`
- `res.config.settings`
- `res.partner`
- `clinic.patient`

## Controllers

Odoo 19 `CustomerPortal` extension:
- `/my/clinic`
- `/my/clinic/bookings`
- `/my/clinic/bookings/<id>`
- `/my/clinic/invoices`
- `/my/clinic/invoices/<id>`
- `/my/clinic/treatments`
- `/my/clinic/treatments/<id>`

## Website/portal UI

- standard Odoo portal-home cards;
- ClinicOne breadcrumbs;
- patient overview;
- booking list/detail;
- clinic invoice list/detail;
- completed treatment list/detail;
- native invoice/payment handoff;
- Wallet / Consent / Orders / Shop shortcuts;
- responsive local SCSS;
- local SVG pictograms.

## Backend governance UI

- Search/List/Form on Portal Profile;
- statusbar;
- native portal-access wizard button;
- Patient / Contact / Portal User smart navigation;
- Booking / Invoice / Treatment smart buttons;
- settings app section.
