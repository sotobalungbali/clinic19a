# ClinicOne Patient Feedback & Satisfaction

Version: **19.0.1.0.0**

Official ClinicOne addon: **27 of 39**

Blueprint:
> Collects patient feedback and satisfaction surveys with escalation workflow.

Key ownership decision:
`booking.feedback.link` remains owned by `clinic_booking`.  This addon extends
that invitation model and synchronizes submitted Booking feedback into the
canonical `clinic.feedback` model instead of redefining the Booking model.

Runtime status: **PENDING** until activation and smoke testing on the target
Odoo 19 CE environment succeeds.
