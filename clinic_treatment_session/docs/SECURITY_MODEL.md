# SECURITY MODEL — HARD GATE 10

Roles:

1. **Treatment Session User**
   - read/create/update session transactions;
   - no deletion;
   - company + allowed-branch record rules.

2. **Treatment Session Clinician**
   - inherits User;
   - can Start/Complete sessions;
   - can prepare and consume materials;
   - no deletion.

3. **Treatment Session Manager**
   - inherits Clinician;
   - company-wide operational visibility;
   - stage configuration;
   - reset workflow;
   - full owned-model ACL including deletion where model workflow permits.

Backend enforcement includes:
- ACLs;
- record rules;
- state-transition guards;
- manager/clinician Python guards;
- cross-company constraints;
- stock completion verification;
- no hiding a completed stock move through line reset.
