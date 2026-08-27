# ClinicOne — `clinic_booking` (Odoo 19 CE)

**Booking Management** for ClinicOne: front-desk reservations, scheduling handshake with Doctor Appointments, room/equipment allocation, and downstream automation (billing, inventory, feedback, portal).
This module defines the core **`booking.booking`** entity (reservations) and keeps a clean separation from **`clinic.appointment`** (clinical schedule) which lives in **`clinic_doctor`**.

> **Design note:** “Booking” (front-office reservation) ≠ “Appointment” (doctor schedule). `clinic_booking` creates/links appointments at confirm time while avoiding circular dependencies.

---

## Table of Contents

* [Key Features](#key-features)
* [Architecture](#architecture)
* [Directory Layout](#directory-layout)
* [Core Models](#core-models)
* [Integration Map](#integration-map)
* [Dependencies](#dependencies)
* [Installation](#installation)
* [Configuration](#configuration)
* [Typical Flows](#typical-flows)
* [Security](#security)
* [Data Files](#data-files)
* [Reporting & Dashboard](#reporting--dashboard)
* [i18n](#i18n)
* [Testing](#testing)
* [Extensibility Hooks](#extensibility-hooks)
* [Roadmap](#roadmap)
* [License](#license)

---

## Key Features

* Front-desk **reservations** with clear status flow: *draft → confirmed → in_progress → done → cancelled*.
* **Overlap prevention** for doctor/room; slot-based scheduling support.
* **Room & resource** allocation (devices, machines, tools).
* **Policy & channel** rules (cancellation window, deposits, online/phone/walk-in, etc.).
* **One-click invoice** creation (optional), price derivation from treatment/product.
* **Portal & feedback** tokens/URLs; email templates for reminders and post-care feedback.
* **Tight integration** with Patient, Doctor, Treatment, Inventory, Billing, Membership, Portal, etc.
* Clean **separation** from `clinic_doctor`’s `clinic.appointment` to avoid circular dependencies.

---

## Architecture

* Odoo 19 CE, Python models + XML views, QWeb reports, backend & portal assets.
* Primary model: **`booking.booking`**; detail lines: **`booking.line`**.
* Uses `mail.thread` + `mail.activity.mixin` for chatter & reminders.
* Generates **portal/feedback tokens** for patient self-service.
* Provides **compute/inverse** fields for durations, amounts, and URLs.

---

## Directory Layout

```
clinic_booking/
├─ __init__.py
├─ __manifest__.py
├─ models/                    # Booking, lines, room, resource, policy, channel, inherits
├─ wizards/                   # Reschedule, cancel, assign doctor, bulk confirm, check-in/out
├─ controllers/               # Portal/website/API/webhook endpoints
├─ security/                  # Groups, record rules, access
├─ data/                      # Sequences, crons, server actions, mail templates, base data
├─ views/                     # Menus, actions, form/tree/kanban/calendar/search, portal templates
├─ report/                    # QWeb reports + actions (+ optional XLSX)
├─ static/                    # JS/CSS assets and description images
├─ demo/                      # Demo data
└─ tests/                     # Unit/integration tests
```

---

## Core Models

* **`booking.booking`** — master reservation (patient, doctor, treatment, start/end, room, state).
* **`booking.line`** — detailed items/services/consumables per booking.
* **`booking.room`** — clinical rooms; capacity & compatibility flags.
* **`booking.resource`** — devices/machines/tools required by a booking.
* **`booking.slot`** — predefined time slots (optional).
* **`booking.policy`** — cancellation/deposit policies.
* **`booking.channel`** — booking origins (Walk-in, Phone, Web, etc.).
* Inherit models: `res.partner`, `clinic.doctor`, `clinic.treatment`, `account.move`, `stock.picking`.

> Appointments (`clinic.appointment`) are defined in **`clinic_doctor`**, not here.
> `booking.booking` may link to it via `appointment_id` (when enabled).

---

## Integration Map

* **Patient (`clinic_patient`)**: `booking.booking.patient_id → res.partner`. History shown on patient profile.
* **Doctor (`clinic_doctor`)**: overlap checks, optional **`clinic.appointment`** creation on confirm.
* **Treatment (`clinic_treatment`)**: default product/price, allowed doctors, default lines/resources.
* **Inventory (`clinic_inventory` + Odoo Stock)**: optional `stock.picking` for tracked consumables.
* **Billing/AR/AP/Accounting** (`clinic_billing`, `clinic_ar`, `clinic_accounting`): invoice creation/link.
* **Membership (`clinic_membership`)**: auto-apply benefits/discounts (if configured).
* **Portal/Marketing/Feedback** (`clinic_portal`, `clinic_marketing`, `clinic_feedback`): tokens, emails, surveys.
* **Pricing/Package** (`clinic_pricing`, `clinic_package`): derive prices from price lists or service bundles.
* **Room & Devices** (`clinic_room_device`): room allocation and device compatibility.

---

## Dependencies

Declared in `__manifest__.py` (excerpt):

* **Odoo core**: `base`, `mail`, `contacts`, `hr`, `account`, `product`, `sale`, `stock`, `portal`, `website`
* **ClinicOne base**: `clinic_base`
* **Cross-module** (aligned with `clinic_patient`’s list but avoiding circular deps):
  `clinic_doctor`, `clinic_treatment`, `clinic_billing`, `clinic_ar`, `clinic_ap`, `clinic_finance`,
  `clinic_accounting`, `clinic_inventory`, `clinic_ecommerce`, `clinic_membership`, `clinic_feedback`,
  `clinic_reports`, `clinic_dashboard`, `clinic_wallet`, `clinic_package`, `clinic_pricing`,
  `clinic_room_device`, `clinic_hr`, `clinic_portal`, `clinic_marketing`, `clinic_l10n_id`, `clinic_audit`.

> We **do not** depend on `clinic_patient` to avoid cycles — `clinic_patient` already depends on `clinic_booking`.

---

## Installation

1. Ensure all required dependencies above are installed and up-to-date.
2. Place this module in your Odoo addons path:

   ```bash
   /odoo/addons/clinic_booking
   ```
3. Update addons list and install:

   ```bash
   odoo-bin -d <db> -u clinic_booking
   ```
4. (Optional) Install related modules (doctor, treatment, inventory, billing) for full features.

---

## Configuration

1. **Sequences**: `booking.booking` sequence (`data/booking_sequence.xml`).
2. **Policies**: define cancellation/deposit policies in **Booking Policies**.
3. **Channels**: set booking channels (Walk-in, Phone, Web).
4. **Rooms & Resources**: configure rooms and clinical devices/tools.
5. **Slots** (optional): define standard working slots per day.
6. **Mail Templates**: review/edit reminder & feedback templates in **Settings > Technical > Email**.
7. **Server Actions/Crons**: enable reminder jobs as needed (T-1 day, T-2 hours, etc.).
8. **Portal**: verify `web.base.url` and portal routes for patient access/feedback submission.

---

## Typical Flows

**A. Create & Confirm Booking**

1. Create booking with patient, (optionally) treatment, doctor, room, start/end.
2. Click **Confirm** → validates overlaps and required fields.
3. (If enabled) Create/link `clinic.appointment` in `clinic_doctor`.
4. Reminder activities are scheduled for doctor/frontdesk.

**B. Start & Complete**

* **Start** at arrival time → status `in_progress`.
* **Done** after service → triggers post-care **feedback** email (optional).

**C. Cancel & Reschedule**

* **Cancel** validates policy (window/deposit).
* **Reschedule** via wizard/calendar drag-drop with overlap checks and appointment sync.

**D. Billing & Inventory (optional)**

* **Create Invoice** from booking; lines from treatment or booking lines.
* **Stock Picking** generated when consumables/devices are tracked via inventory rules.

---

## Security

Suggested groups (defined in `security/booking_security.xml`):

* `clinic_booking.group_user` — Frontdesk/Reception: create/update own bookings.
* `clinic_booking.group_manager` — Manager: full access across company.
* `clinic_booking.group_doctor` — Doctor: read assigned bookings; limited edits (check-in/out).

Record rules in `booking_record_rules.xml` restrict non-managers to relevant records (by company/assignment).

Access rights are set in `security/ir.model.access.csv` for:

* `booking.booking`, `booking.line`, `booking.room`, `booking.resource`, `booking.policy`, `booking.channel`, etc.

---

## Data Files

* **Sequences**: `data/booking_sequence.xml`
* **Activities/Crons/Server Actions**: `data/booking_activity_types.xml`, `data/booking_cron.xml`, `data/booking_server_actions.xml`
* **Mail Templates**: `data/booking_mail_template.xml`
* **Base Data**: `data/booking_data.xml`
* **Demo**: `demo/booking_demo.xml`, `demo/booking_room_demo.xml`, `demo/booking_resource_demo.xml`, `demo/booking_policy_demo.xml`

---

## Reporting & Dashboard

* QWeb: `report/booking_report_templates.xml` + actions in `report/booking_report_actions.xml`
* (Optional) XLSX helper: `report/booking_xlsx_report.py`
* KPIs are intended to surface in `clinic_reports` / `clinic_dashboard`.

---

## i18n

* Default language: **English** (UI strings).
* Translations: `i18n/en.po`, `i18n/id.po` — keep keys stable and avoid hard-coded strings.

---

## Testing

* Run tests:

  ```bash
  odoo-bin -d <db> -i clinic_booking --test-enable --stop-after-init
  ```
* Included:

  * `test_booking_flow.py` — create/confirm/start/done/cancel lifecycle
  * `test_double_booking.py` — overlap prevention (doctor/room)
  * `test_integration_billing.py` — invoice creation/linking

---

## Extensibility Hooks

Key methods you can override/extend:

* Lifecycle: `action_confirm`, `action_start`, `action_done`, `action_cancel`
* Validation: `_check_overlaps`, `_check_doctor_can_do_treatment`, `_ensure_required_for_confirm`
* Financials: `_compute_amounts`, `_prepare_invoice_vals`
* UX/Automation: `_schedule_reminder_activities`, `_request_feedback_if_configured`
* Portal: `_compute_portal_urls`
* Onchange: `_onchange_treatment_id`, `_onchange_patient_id`

Use `@api.model_create_multi`, `@api.depends`, `@api.constrains`, and `_inherit` in downstream modules for safe customizations.

---

## Roadmap

* Appointment handshake templates (create/sync/cancel policies) behind a configuration flag.
* No-show tracking & penalties; deposits/refunds.
* Capacity planning for rooms/devices; conflict resolution suggestions.
* Advanced pricing with `clinic_pricing` (rules & bundles).
* Deeper queueing integration with room assignment workflows.

---

## License

LGPL-3.0-or-later. See `LICENSE`.

> © 2025 ClinicOne Team — Designed for Odoo 19 Community Edition.
