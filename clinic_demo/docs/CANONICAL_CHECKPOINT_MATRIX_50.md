# Canonical checkpoint matrix — v50

New generation uses the first scenario declared by each generator. Historical alias policy is separate and limited to the Resource checkpoint documented in RELEASE_50.md.

| Generator | Phase | Declared scenarios | Dependencies |
|---|---|---|---|
| clinical.care_postcare | 17_advanced | SCN-CARE-01 | clinical.emar |
| clinical.emar | 17_advanced | SCN-EMAR-01 | clinical.imaging |
| clinical.imaging | 17_advanced | SCN-IMAGING-01 | operations.treatment_session |
| clinical.telemedicine | 17_advanced | SCN-TELE-01 | clinical.care_postcare |
| commercial.ap | 18_commercial | SCN-AP-01 | commercial.ar |
| commercial.ar | 18_commercial | SCN-AR-01 | commercial.billing |
| commercial.billing | 18_commercial | SCN-BILLING-01 | clinical.telemedicine |
| digital.ecommerce_marketing_portal | 19_exception | SCN-API-01 | exception.incident_quality |
| exception.feedback | 19_exception | SCN-FEEDBACK-01 | commercial.ap |
| exception.incident_quality | 19_exception | SCN-INCIDENT-01, SCN-QUALITY-01 | exception.feedback |
| foundation.native | 08_foundation | SCN-FOUNDATION-01 | — |
| foundation.organization | 08_foundation | SCN-FOUNDATION-01 | foundation.native |
| history.patient_longitudinal | 13_history | SCN-PATIENT-RET-01 | resources.rooms_devices |
| management.analytics | 22_management | SCN-ANALYTICS-01 | management.dashboard |
| management.dashboard | 22_management | SCN-DASH-01 | management.reports |
| management.reports | 21_reports | SCN-REPORT-01 | operations.future_pipeline |
| master.catalog | 11_master | SCN-ENCOUNTER-01, SCN-SESSION-01, SCN-IMAGING-01, SCN-EMAR-01, SCN-CARE-01 | patient.personas |
| master.commercial | 11_master | SCN-PACKAGE-01, SCN-MEMBERSHIP-01, SCN-WALLET-01, SCN-INSURANCE-01 | master.consent |
| master.consent | 11_master | SCN-CONSENT-01 | master.catalog |
| operations.booking | 14_frontoffice | SCN-BOOKING-HIST-01, SCN-BOOKING-TODAY-01, SCN-PIPELINE-01, SCN-REFERRAL-01 | operations.referral |
| operations.encounter | 16_clinical | SCN-ENCOUNTER-01, SCN-ENCOUNTER-RET-01 | operations.queue_triage |
| operations.future_pipeline | 20_pipeline | SCN-PIPELINE-01 | digital.ecommerce_marketing_portal, operations.booking, clinical.telemedicine |
| operations.queue_triage | 15_arrival | SCN-QUEUE-01, SCN-TRIAGE-ABN-01 | operations.booking |
| operations.referral | 14_frontoffice | SCN-REFERRAL-01, SCN-REFERRAL-02 | history.patient_longitudinal |
| operations.treatment_session | 16_clinical | SCN-SESSION-01, SCN-SESSION-02 | operations.encounter |
| patient.personas | 10_patient | SCN-PATIENT-NEW-01, SCN-PATIENT-RET-01 | workforce.staff |
| resources.rooms_devices | 12_resources | SCN-BOOKING-TODAY-01 | master.commercial |
| validation.analytics_evidence | 23_validation | SCN-DASH-01 | validation.journey_exception |
| validation.integrity_reset_regeneration | 23_validation | SCN-PATIENT-RET-01 | validation.analytics_evidence |
| validation.journey_exception | 23_validation | SCN-INCIDENT-01 | validation.workflow |
| validation.structural | 23_validation | SCN-ANALYTICS-01 | management.analytics |
| validation.temporal | 23_validation | SCN-PIPELINE-01 | validation.structural |
| validation.workflow | 23_validation | SCN-ENCOUNTER-01 | validation.temporal |
| workforce.preflight | 09_workforce | SCN-WORKFORCE-01 | foundation.organization |
| workforce.staff | 09_workforce | SCN-WORKFORCE-01 | workforce.preflight |











