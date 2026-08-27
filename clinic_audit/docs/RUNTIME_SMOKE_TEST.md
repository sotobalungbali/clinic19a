# Runtime Smoke Test (after installation)

1. Install/upgrade `clinic_audit` on the target Odoo 19 CE database.
2. Create a low-risk ClinicOne record and confirm one `clinic.audit.event` is generated.
3. Update one non-sensitive field and confirm a sealed event with event-line diff.
4. Confirm a privacy-sensitive field is redacted/digested.
5. Create a branch-restricted audit user and verify cross-branch evidence is not visible.
6. Run Integrity Verification as Audit Manager and confirm PASS.
7. Generate Evidence Export JSON.
8. Run one bounded Legacy Evidence Import batch if historical logs exist.
9. Confirm ordinary users cannot edit/delete authoritative or legacy evidence.

Runtime status is not PASS until these checks are observed on the user's Odoo instance.
