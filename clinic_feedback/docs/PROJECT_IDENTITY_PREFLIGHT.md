# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- PROJECT: ClinicOne
- PLATFORM: Odoo 19 Community Edition
- ADDON: `clinic_feedback`
- OFFICIAL SEQUENCE: addon 27 of 39
- AUTHORITATIVE BLUEPRINT:
  - **Collects patient feedback and satisfaction surveys with escalation workflow.**
- AUTHORITATIVE SOURCE BASELINE:
  - latest user bundle dated 2026-08-20;
  - `clinic_post_care_followup` 19.0.1.0.0 installed/frozen.
- CURRENT RUNTIME STATUS: PENDING.

## Critical preservation decision

The current installed `clinic_booking` already owns:

`booking.feedback.link`

including:
- secure token;
- Booking/Patient/Doctor/Treatment context;
- email invitation/reminder;
- states Draft/Queued/Sent/Opened/Submitted/Expired/Revoked;
- 1-5 rating;
- patient comment;
- recommendation response.

Addon 27 MUST NOT redefine or move that model.

Instead:
- `booking.feedback.link` remains the Booking invitation/content contract;
- addon 27 extends it with Survey and canonical Feedback links;
- submitted Booking responses are synchronized to `clinic.feedback`.

## Historical Queue contract

The live `clinic.queue.action_done()` already contains an optional hook which
creates `clinic.feedback.request` only when that model exists and when
`feedback_request_id` exists on Queue.

Addon 27 intentionally supplies:
- `clinic.feedback.request`;
- live `clinic.queue.feedback_request_id`.

Thus the old safe/optional Queue hook becomes functional without changing Queue
ownership.

## Forward boundary

Future addons are not dependencies:
- `clinic_reports`;
- `clinic_dashboard`;
- `clinic_portal`;
- `clinic_marketing`;
- `clinic_telemedicine_secure_messaging`;
- `clinic_incident_event`;
- `clinic_quality`;
- `clinic_integration_api`;
- `clinic_analytics`.
