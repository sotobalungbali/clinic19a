
# Project Identity Preflight

- Project: ClinicOne
- Addon: `clinic_treatment_session`
- Target: Odoo 19 Community Edition
- Source-actual addon order: 41 / 41
- Baseline version: `19.0.2.0.2`
- Repair version: `19.0.2.0.3`
- Delivery: Direct Full Replacement Addon
- Runtime trigger: `operations.booking`
- Failure: `BookingRoom.is_available() got an unexpected keyword argument 'ignore_booking_id'`

The repair belongs to the Treatment Session extension of `booking.room`; it is
not implemented as a `clinic_demo` workaround.
