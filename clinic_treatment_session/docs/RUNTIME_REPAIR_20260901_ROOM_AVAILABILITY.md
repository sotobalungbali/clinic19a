
# Runtime Repair — Booking Room Availability Contract

## Failure
`operations.booking` stopped with:
`BookingRoom.is_available() got an unexpected keyword argument 'ignore_booking_id'`

## Root cause
The 19.0.2.0.2 Treatment Session extension had a narrower override:
`is_available(start_datetime, end_datetime, ignore_session_ids=None)`.

`clinic_booking` legitimately calls the room authority with
`ignore_booking_id=` and `consider_capacity=`.

## Repair
19.0.2.0.3 exposes:
`is_available(start_dt, end_dt, ignore_booking_id=None,
consider_capacity=True, ignore_session_ids=None)`.

Execution order:
1. delegate to `super().is_available(...)`;
2. if owner availability is false, return false;
3. apply Treatment Session overlap domain;
4. optionally ignore Treatment Session IDs during rescheduling.

No generator-side bypass is used.
