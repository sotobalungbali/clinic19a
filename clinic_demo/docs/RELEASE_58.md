# clinic_demo 19.0.1.0.58 — explicit Telemedicine branch contract

Baseline: clinic19a(20260917-024603).md and odoo(20260917-022158).log. User runtime reached 18/40 PASS, then Telemedicine session/thread were blocked because the consultation patient's South branch is outside Dr. Alya's allowed branch set.

## Cause and correction

Telemedicine owner create() fills a false branch_id from patient.partner_id.branch_id when branch-scoping policy is enabled. The original demo passed false and did not declare the resulting cross-branch clinician entitlement. Switching to the proper clinician reader exposed this missing scope contract.

The new shared preparation verifies unique demo-owned doctor/user/patient/branch provenance, matching company and doctor-user relationship, and checks existing session/thread patient/company/branch. It adds only the verified consultation patient's branch to DEMO-USER-DOC-001.allowed_branch_ids using the standard res.users.write owner API. Working branch and staff/doctor home branch remain unchanged. No group or record rule is changed, no sudo is used, and no access is granted to unowned or foreign-company branches. The addition is logged once; repeat preparation makes no change.

Reconcile now explicitly includes this bounded actor-entitlement preparation before Telemedicine inspection; this is a permission metadata mutation, not merely a read-only operation. It has its own savepoint so a failed preparation cannot leave partial entitlement changes. Owner validators remain inside their rollback-only evidence savepoints. Advanced generation prepares the same scope before owner preflight. Newly generated Telemedicine sessions receive the verified patient branch explicitly rather than relying on owner fallback. Existing clinical data is not moved or reset.

## Upgrade and resume

Stop Odoo, replace the full clinic_demo folder, restart and upgrade to 19.0.1.0.58. Other addons stay unchanged. Open the same Demo Run, Refresh Compatibility, then Reconcile Existing Dataset. Open Journey Progress; if clinical.telemedicine passes, Execute Next / Resume continues from the next incomplete journey without selecting a row. No Reset and no manual clinical-state edits. The acting Control Center user must satisfy the existing Branch owner API permission for changing another demo user's branch scope; this addon does not bypass that security.

## Verification

222 source/behavior tests and clinic_demo guardrail PASS. Regression cases check one-branch addition, repeat no-op, working-branch preservation, and denial for missing ownership, duplicate branch provenance or foreign company. Composite Python/XML parse PASS; raw evidence is in evidence_58. Native Odoo database execution NOT RUN here. No fixed PASS count is promised. Existing known missing Telemedicine icon assets in composite and L1–L8 population expansion remain outside this permission correction. Permanent governing prompt remains bundled.



