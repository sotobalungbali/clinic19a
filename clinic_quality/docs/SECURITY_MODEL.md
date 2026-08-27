# HARD GATE 10 — Security Model

Hierarchy:
- Quality User
- Quality Inspector
- Quality Approver
- Quality Manager

`Quality User -> Inspector -> Approver -> Manager`.

## Backend authority

- User: read governed quality records; may acknowledge own Approved SOP.
- Inspector: draft SOP Versions, execute Checks and record evidence.
- Approver: approve SOP Versions, review/return/close Checks, request Incident
  escalation.
- Manager: configure SOP headers/Templates/Schedules, retire/restore governance,
  void acknowledgement evidence and perform controlled administration.

Direct state writes are blocked.

Approved SOP Versions, closed Checks and evidence records are protected by
backend immutability rules.

## Branch / company security

8 record rules enforce:
- allowed companies;
- branch applicability/branch access.

No Portal/Public backend ACL exists.

## Incident escalation

Quality does not inherit Incident Reporter automatically. A user invoking
Quality failure escalation must also possess Incident Reporter access, so
Quality UI cannot defeat addon-34 security.
