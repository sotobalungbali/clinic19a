# HARD GATE 10 — Security Model

Roles:
- Incident User
- Incident Reporter
- Incident Investigator
- Incident Manager

Hierarchy:
User -> Reporter -> Investigator -> Manager.

Backend enforcement:
- company + branch record rules;
- shared/company Category rule;
- Branch policy constraint;
- Branch user-access constraint;
- direct state writes blocked;
- Reporter cannot close/cancel;
- Investigator controls Triage/Investigation/CAPA execution;
- Manager verifies CAPA effectiveness and closes/cancels cases;
- closed/cancelled Incident cases are business-read-only;
- completed/cancelled Investigations are read-only;
- verified/cancelled CAPA is read-only;
- Timeline is immutable and controlled-system-created.

There are no Portal/Public backend ACL rows.

Telemedicine:
- secure bodies/internal notes remain in addon 33;
- linking a Secure Thread never copies its protected content.

Regulatory:
- this addon records reportability/reporting evidence;
- it does not claim external transmission.
