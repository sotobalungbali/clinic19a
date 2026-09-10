# MASTER PROMPT 17 — Advanced Clinical Workflows

Build: `clinic_demo 19.0.1.0.33` + `clinic_emar 19.0.3.0.3`

Authoritative source: `clinic19a(20260908-001624).md`  
SHA-256: `8e0d2be47034b5841642ba056df294825f71a6040f7f27b77cd6da32ef417ab2`

Implemented as four isolated, provenance-bound generators:

- `clinical.imaging`: requested → scheduled → in progress → completed → reviewed;
- `clinical.emar`: prescription, medication lines, active order, and completed administration;
- `clinical.care_postcare`: active recurring Care Plan plus active Post-Care Plan;
- `clinical.telemedicine`: signed Consent, ready Session, Secure Thread, and secure message.

Before every Prompt-17 checkpoint's first clinical-record write, source-declared
entitlements are reconciled only on synthetic functional actors, then the same
whole-path runtime preflight verifies every model, field, comodel, business
method, exact per-actor operation, and upstream provenance prerequisite used by
all four generators. This makes a resumed run independent of which earlier
Prompt-17 checkpoint executed in the current process or database lifecycle.
Actor-bound records disable broad relational prefetch and explicitly read only
the cross-model fields required by owner workflows. The preflight also probes
those exact field reads. This preserves Odoo's private `hr.employee` fields
instead of granting clinical actors unintended access merely to make demo data.
Immutable Secure Messages are checked for read/create only; the nurse reads the
eMAR Order and writes only Administration evidence. All transaction
identifiers and the medication scan barcode are explicit deterministic values;
they do not consume mutable production numbering for demo identity.

The eMAR Order uses its actual downstream compatibility contract:
`patient_id=res.partner`, `doctor_id=hr.employee`, with canonical
`clinic_patient_id` and `clinic_doctor_id`. Confirmation runs as the synthetic
eMAR Manager so both owner configurations (auto-schedule enabled or disabled)
remain ACL-valid. The Secure Thread is created with its final deterministic name
before Session scheduling, so the owner sequence is never consumed and renamed.

The generator contains no `sudo()`, direct SQL, technical audit-date manipulation,
direct state write, or fabricated third-party provider. eMAR administration uses
deterministic patient/product scan evidence. The owner-created Secure Thread is
renamed deterministically and bound to provenance. Billing remains deferred to
MASTER PROMPT 18. Runtime acceptance requires upgrade, Refresh Compatibility,
then Generate Full Enterprise Dataset on the same Demo Run without Reset.

A failed Prompt-17 checkpoint may adopt this build only when Prompt 16 and the
exact earlier Prompt-17 prefix are complete, the failed savepoint committed no
references for itself or any later stage, and the checkpoint set exactly matches
that prefix plus the failed stage. This stage-aware bounded repair preserves the
same Demo Run and never reopens completed checkpoints.

The Prompt-17 source gate additionally parses all executable Python in its six
owner addons and permits only known Odoo `fields.Date` / `fields.Datetime`
helpers. `clinic_emar 19.0.3.0.3` replaces the invalid
`fields.Date.timedelta` prescription-expiry computation with Python
`datetime.timedelta`; the normal 30-day validity remains intact.









