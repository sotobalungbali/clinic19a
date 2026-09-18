# Clinic Demo KPI Coverage Matrix

The three Analytics periods are fixed relative to the Demo Run anchor:
Historical T-365..T-181, Prior T-180..T-1, and Current/Future T..T+90.
Every value is evaluated by `clinic.analytics.engine`; no KPI output is written
directly by `clinic_demo`.

| KPI family | Source models | Formula ownership | Demo source records | Expected direction | Status |
|---|---|---|---|---|---|
| Revenue | clinic.billing.invoice | clinic_analytics fixed adapter | Prompt 18 invoices | non-zero current/combined revenue | Required |
| Booking | booking.booking | clinic_analytics fixed adapters | Prompt 14/20 historical/current/future bookings | volume plus completion/no-show variation | Required |
| Patient retention | booking.booking | clinic_analytics fixed adapters | returning-patient history | historical versus current comparison | Required |
| Membership | membership.contract | clinic_analytics fixed adapters | Prompt 11 membership journey | active/renewal signal | Required |
| Wallet | clinic.wallet | clinic_analytics fixed adapter | Prompt 11 wallet | source-backed balance | Required |
| Experience | clinic.feedback | clinic_analytics fixed adapters | Prompt 19 complaint/escalation | NPS/rating exception signal | Required |
| Quality | clinic.quality.check | clinic_analytics fixed adapter | Prompt 19 failed control | non-zero quality source | Required |
| Incident | clinic.incident | clinic_analytics fixed adapters | Prompt 19 investigation | normal plus exception signal | Required |
| Marketing | clinic.marketing.* | clinic_analytics fixed adapters | only source-supported campaign evidence | zero allowed when no legitimate delivery exists | Coverage-only |
| Booking forecast | booking.booking | clinic.analytics.forecasting | 12 monthly actual + 3 future points | transparent linear trend | Required |

All snapshot lines must retain `source_model`, `source_count`, and serialized
source-domain evidence. A zero remains zero when the source is legitimately
empty; it is never replaced with a hardcoded showcase number.


















