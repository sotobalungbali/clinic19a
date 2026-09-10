

# Runtime Repair 2026-08-20 — Booking Feedback Inverse Contract

## Symptom

Opening a new `booking.booking` form failed during onchange with:

`KeyError: 'feedback_link_ids'`

## Root cause

`booking.feedback.link.booking_id` correctly targets `booking.booking`, while the
inverse One2many `feedback_link_ids` lived on the abstract
`booking.feedback.link.mixin`. The primary `booking.booking` model did not
inherit that mixin. Odoo therefore had an inverse relation registered for the
Many2one but could not resolve `feedback_link_ids` on a new booking record.

## Repair

- load `booking_feedback_link` before `booking_booking`;
- make `booking.booking` inherit `booking.feedback.link.mixin`;
- preserve the existing mixin, feedback model, fields and
  `action_new_feedback_link()` behavior;
- add a hard gate proving the inverse field and helper method are effective on
  `booking.booking`.

No booking lifecycle, scheduling, billing, inventory, patient, doctor, room,
resource, policy, channel, security, or feedback behavior is removed.
