# ClinicOne Executive Demo Script

This script uses only records registered by the Full Enterprise Demo Run. Start
from **ClinicOne > Demo Dataset > Control Center**, open the Ready run, and use
Golden Journeys to resolve every `DEMO-*` key to its current record. This avoids
database IDs, mutable sequence values, and assumptions about list ordering.

| Chapter | Menu path / exact evidence | Presenter action | Business story and value | Stakeholders / talking points |
|---|---|---|---|---|
| 1. Foundation | Demo Dataset > Control Center; `DEMO-COMPANY-001`, `DEMO-BRANCH-001..003` | Open run, Compatibility and Golden Journeys | One governed dataset anchors company, branches, locale, currency and calendars. | Owner, IT: controlled scope, Safe Mode, traceability. |
| 2. Organization & Resources | Golden Journeys; `DEMO-DOC-001`, `DEMO-ROOM-B001-IMG-01`, `DEMO-DEVICE-MON-01` | Open doctor, room/device and schedules | Workforce and physical capacity are connected before operations start. | Manager, doctor, nurse: availability and accountable ownership. |
| 3. Patient 360 | Patients; `DEMO-PAT-RET-001`, `DEMO-PAT-CHRON-001` | Open master, identifiers, conditions and longitudinal evidence | A reusable identity supports safe continuity without duplicate patients. | Doctor, nurse, front office: one patient context. |
| 4. Service & Catalog | Treatments/Packages/Consent; `DEMO-TREAT-CONSULT-GEN`, `DEMO-PKG-*`, `DEMO-CONSENT-TPL-*` | Open treatment, pricing, protocol and consent version | Clinical service definition drives scheduling, care and commercial rules. | Manager, finance, compliance: governed catalog. |
| 5. Booking & Front Office | Referrals/Bookings; `DEMO-REF-001`, `DEMO-BOOK-TODAY-REF-001` | Follow referral conversion into booking and appointment | Acquisition becomes a scheduled service without re-keying identity. | Front office, management: conversion and capacity visibility. |
| 6. Queue & Triage | Queue/Triage; `DEMO-QUEUE-WAIT-001`, `DEMO-TRIAGE-NORMAL-001`, `DEMO-APPT-TRIAGE-ABN-001` | Compare waiting, called/service and abnormal triage cases | Arrival status and vitals prioritize care while preserving timestamps. | Nurse, doctor, clinic manager: safety and waiting-time control. |
| 7. Clinical Encounter | Encounters/Treatment Sessions; `DEMO-ENC-001`, `DEMO-SESSION-001` | Open SOAP, diagnosis, procedures and completed session | Consultation evidence flows into delivered treatment and follow-up. | Doctor, therapist, compliance: complete clinical provenance. |
| 8. Advanced Clinical | Imaging/eMAR/Care/Telemedicine; `DEMO-IMG-001`, `DEMO-EMAR-ORDER-001`, `DEMO-CARE-PLAN-001`, `DEMO-TELE-SESSION-001` | Open each linked workflow and its owner state | Specialized care remains connected to patient and encounter context. | Clinical leaders, IT: integrated workflows with Safe Mode. |
| 9. Commercial & Financial | Billing/AR/AP; `DEMO-BILL-001`, `DEMO-AR-001`, `DEMO-AP-001` | Trace bill to posted move, receivable and supplier payable | Service delivery becomes auditable finance evidence. | Finance, owner: revenue, receivable, payable and posting integrity. |
| 10. Exception & Incident | Feedback/Quality/Incident; `DEMO-FB-001`, `DEMO-QUAL-001`, `DEMO-INC-001`, `DEMO-API-001` | Open escalation, nonconformity, investigation and safe integration failure | Exceptions are visible management work, not hidden success-only data. | Quality, compliance, IT: response, ownership, no outbound side effect. |
| 11. History | Patient 360 and historical bookings; `DEMO-HIST-VITAL-*`, `DEMO-HIST-COND-EP-*`, `DEMO-BOOK-HIST-*` | Move through dated clinical and operational history | Longitudinal trends explain current decisions. | Doctor, board: continuity and trend evidence. |
| 12. Reports | Reports > Runs; `DEMO-REPORT-*` | Open Ready runs, metrics, details and CSV | Nineteen owner report engines summarize source transactions. | Managers, board: source-backed operational evidence. |
| 13. KPI & Dashboard | Dashboard/Analytics; `DEMO-DASH-SNAPSHOT-*`, `DEMO-ANL-SNAPSHOT-*`, `DEMO-ANL-FORECAST-BOOKING` | Compare dashboards, three snapshot periods and forecast | KPI and forecast are calculated from the same operational source. | Owner, top management: performance and forward visibility. |
| 14. Management Decision | Dashboard > source report > operational record | Drill from KPI exception to source evidence and responsible workflow | Management can act on queue pressure, service recovery, capacity and cash. | Board, manager: insight remains explainable and actionable. |

## Close

Return to the Demo Run and show: 35 Done checkpoints, Compatible fingerprint,
Safe Mode enabled, Validation PASS, and **READY FOR DEMO**.
