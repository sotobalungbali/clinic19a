# Cross-Addon Contract Audit

Authoritative source: ClinicOne user bundle uploaded 2026-08-20.

## `clinic_booking`

Live owner:
- `booking.feedback.link`.

Verified existing fields used by addon 27:
- `booking_id`;
- `company_id`;
- `patient_id`;
- `doctor_id`;
- `treatment_id`;
- `token`;
- `access_url`;
- `state`;
- `rating_value`;
- `comment`;
- `would_recommend`.

Verified existing methods:
- `action_mark_opened()`;
- `action_submit_feedback()`;
- `sudo_find_by_token()`.

Addon 27 extends this model only; no `_name = "booking.feedback.link"` exists.

`booking.booking` remains the Booking owner and receives only:
- canonical request navigation;
- canonical response counters;
- explicit request action.

## `clinic_queue_room`

Live `clinic.queue` has:
- `patient_id -> res.partner`;
- `treatment_id -> clinic.treatment`;
- `company_id`;
- `state`;
- `end_time`;
- `action_done()`.

Its existing completion method `clinic.queue.action_done()` already checks for
`clinic.feedback.request` and `feedback_request_id`.
Addon 27 closes that optional contract by adding the missing Queue field and
canonical Request model.

No Queue workflow replacement is introduced.

## `clinic_encounter`

Live fields used:
- `patient_id -> clinic.patient`;
- `partner_id -> res.partner`;
- `doctor_id -> clinic.doctor`;
- `treatment_id -> clinic.treatment`;
- `company_id`;
- `state`;
- `date_end`.

Addon 27 provides explicit Feedback Request navigation and optional cron
automation. `action_done()` remains owned by Encounter.

## `clinic_post_care_followup`

Verified upstream version: 19.0.1.0.0.

Live fields used:
- `patient_id`;
- `partner_id`;
- `doctor_id`;
- `responsible_staff_id`;
- `treatment_id`;
- `company_id`;
- `branch_id`;
- `state`;
- `completed_at`.

Addon 27 adds Feedback Request navigation and opt-in automation only.

## Patient / Doctor / Staff

`clinic.patient`, `clinic.doctor`, and `clinic.staff` remain owned by their
respective modules.

Addon 27 adds:
- satisfaction counters;
- average rating;
- open service-recovery counts where appropriate;
- drill-down actions.

`res.partner.feedback_count` / `feedback_avg_rating`, which already belong to
Booking integration, are preserved and broadened to include:
- canonical `clinic.feedback`;
- legacy submitted Booking links not yet canonicalized.

## Future Incident/Quality/Reports

Feedback Escalation is a service-recovery workflow internal to addon 27.
It does NOT create:
- `clinic.incident.*`;
- quality cases;
- reporting/dashboard models.

Those remain future addon responsibilities.

## Result

- duplicated upstream model ownership: 0
- required live upstream contracts unresolved: 0
- future-addon hard dependencies: 0
- fake SMS/WhatsApp/API delivery: 0
