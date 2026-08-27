# Cross-Addon Contract Audit

The authoritative snapshot was audited before build. Key contracts preserved:

1. `clinic_base` owns `clinic.mixin.audit`, including `_clinic_audit_logger_model`,
   `_clinic_audit_emit`, `clinic_audit_skip`, and create/write audit hooks.
2. `clinic_encounter` also defines the historical `clinic.audit.log` contract and grants
   broad user ACLs.  This addon therefore enforces legacy immutability in backend methods and
   does not rely on additive ACLs to revoke older access.
3. Existing modules such as encounter/EMAR/billing still emit legacy audit records via `sudo()`;
   they remain compatible.
4. `clinic_branch` owns `clinic.branch` and user `allowed_branch_ids`; authoritative events use
   company + branch record rules.
5. `clinic_integration_api` is upstream business/integration functionality but is deliberately
   not a manifest dependency. Its models are included in the fixed registry coverage catalog
   when installed.
6. `clinic_analytics` #39 is downstream and is not referenced as a dependency.

The audit ledger never duplicates patient, booking, encounter, billing, inventory, branch,
quality, telemedicine, or integration business ownership.

7. Upgrade compatibility: legacy active policies had no workflow `state`; the 19.0.2.0.0
   post-migration promotes existing active/triggered rows to the new Active state. Legacy
   `company_ids` remains supported and `company_id` stays nullable for global policies.
