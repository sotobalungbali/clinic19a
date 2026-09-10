# Clinic Demo Dashboard Coverage Matrix

Dashboard snapshots use the exact Prompt-21 report window and consume only
normalized `clinic.report.metric` records. The Dashboard owner engine creates
all snapshot lines and preserves Report Run/Metric provenance.

| Dashboard | Coverage | Demo source | Expected result | Status |
|---|---|---|---|---|
| Executive | revenue, collection, AR, cash, booking, queue, encounter, NPS | Prompt 14–21 Report Runs | populated cross-functional cards | Required |
| Financial | revenue, collection, AR, AP, cash, tax, insurance | Prompt 11/18/21 | populated cards; legitimate source-zero allowed | Required |
| Operations | booking, queue, room, inventory, membership, wallet | Prompt 11–16/20/21 | populated operational cards | Required |
| Clinical | encounter, procedure, triage, adverse, post-care, feedback | Prompt 15–21 | normal and exception visibility | Required |
| Room | assignment, occupancy, service, queue context | Prompt 15/21 | populated room-utilization cards | Required |
| Experience | feedback, complaint, escalation, post-care | Prompt 17/19/20/21 | populated patient-experience cards | Required |

Validation rejects `no_data`, `unsupported_scope`, and `error` cards and rejects
any populated card without both Report Run and Report Metric provenance.



