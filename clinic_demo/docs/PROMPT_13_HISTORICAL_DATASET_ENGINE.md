
# MASTER PROMPT 13 — Historical Dataset Engine

**Addon:** `clinic_demo`  
**Build:** `19.0.1.0.15`  
**Status:** Source/static package implementation. Runtime owner-run pending.

## Objective

Create a deterministic historical-time backbone relative to the persisted Demo
Anchor Date without falsifying Odoo technical audit fields and without pre-empting
the business workflows owned by later Master Prompts.

Prompt 13 therefore has two responsibilities:

1. provide one reusable historical timeline/business-date service that later
   Booking, Referral, Encounter, Treatment Session, Imaging, eMAR, Care Plan,
   Post-care, Billing, Feedback, Incident and Quality generators must consume;
2. prove the engine immediately with source-native longitudinal patient history
   that can be created before those downstream transactional workflows exist.

## Historical periods

The service covers five source-independent temporal bands:

- Baseline History — T-365..T-181
- Growth Period — T-180..T-91
- Recent Quarter — T-90..T-31
- Recent Activity — T-30..T-8
- Latest History — T-7..T-1

`HistoricalTimelineService` uses twelve rolling 30-day segments and nested profile
positions. It never calls the wall-clock date for business-history placement.

Profile vital-history budgets:

- Compact: 24
- Standard: 48
- Full Enterprise: 72

## Business-date contract

Later domain generators must populate source-owned business date fields instead
of editing `create_date` or `write_date`.

The Prompt-13 contract covers, among others:

- `booking.booking.start_datetime`
- `clinic.referral.date_referral`
- `clinic.encounter.date_planned_start/date_start/date_end`
- `clinic.treatment.session.start_datetime/actual_*`
- `clinical.imaging.request.request_datetime`
- `clinical.imaging.request.desired_datetime`
- `clinical.imaging.performed_datetime/reviewed_datetime`
- `clinic.emar.order.date_prescribed/date_start/date_completed`
- `clinic.care.plan.start_date/end_date`
- `clinic.postcare.plan.start_datetime/expected_end_date`
- `clinic.billing.invoice.invoice_date/invoice_date_due`
- `clinic.billing.payment.date`
- `clinic.feedback.request.request_date`
- `clinic.incident.occurred_at/detected_at/reported_at`
- `clinic.quality.check.planned_date/started_at`

The generator performs a runtime field preflight against this contract before
creating Prompt-13 evidence.

## Runtime evidence created in Prompt 13

One bounded generator is registered:

`history.patient_longitudinal`

Dependency:

`resources.rooms_devices`

It creates only:

- `clinic.patient.vital`
- `clinic.patient.condition.episode`
- `clinic.patient.allergy.reaction`

These are source-native patient-history children and have explicit historical
business date fields.

Full Enterprise target:

- 72 longitudinal vital observations
- 6 chronic-condition episodes
- 1 recovered synthetic allergy-reaction history
- total 79 Prompt-13 business-history rows

All data is fictional/synthetic and is explicitly described as presentation data,
not diagnosis or clinical advice.

## Why Booking/Encounter/Billing history is not created here

The Master Prompt sequence places their owner workflows after Prompt 13.
Creating them here would duplicate or pre-empt:

- Prompt 14 Booking/Referral
- Prompt 15 Queue/Triage
- Prompt 16 Encounter/Treatment Session
- Prompt 17 Advanced Clinical
- Prompt 18 Commercial/Financial
- Prompt 19 Exception/Quality

Prompt 13 establishes their deterministic historical-time contract now. Those
domain prompts later create the actual historical transactions through official
business methods using the same service.

## Reset

Prompt-13 history children are `DELETE_SAFE` and receive higher child-first reset
sequence values than patient masters. Patient master identity remains archived by
the Prompt-10 policy.

## Progressive adoption

A Demo Run with completed Prompt 12 may adopt build 19.0.1.0.15 through
**Refresh Compatibility** only when no Prompt-13 checkpoint/reference exists yet.

Expected progression:

`resources.rooms_devices = DONE`
→ `history.patient_longitudinal = DONE`

Expected registered generator count after successful Prompt-13 runtime execution:

**10 bounded generators**

## Non-scope

Prompt 13 does not create:

- Booking
- Referral
- Queue/Triage
- Encounter
- Treatment Session
- Imaging request/order/result
- eMAR order/administration
- Care Plan
- Post-care Plan
- Billing Invoice/Payment
- Feedback
- Incident
- Quality Check
- KPI/dashboard snapshots

These remain owned by subsequent Master Prompts.


