# MASTER PROMPT 23 - Validation, Reset, Regeneration, Tests and Fresh Database

## Runtime scope

Prompt 23 completes the 35-generator registry with six ordered, read-only
acceptance checkpoints. They inspect the real records produced by Prompts 08-22;
they do not create replacement business transactions or hardcoded KPI evidence.

1. `validation.structural` - reference existence, uniqueness, company and branch.
2. `validation.temporal` - historical/future coverage and logical date windows.
3. `validation.workflow` - critical Billing, AR, AP and Incident lifecycle states.
4. `validation.journey_exception` - golden-journey and exception evidence families.
5. `validation.analytics_evidence` - report, dashboard, KPI snapshot and forecast provenance.
6. `validation.integrity_reset_regeneration` - missing-reference and reset-policy coverage.

## Safety contract

- Generate Full never performs Reset.
- Reset remains protected by the existing typed confirmation wizard.
- Reset inspects explicit ownership and policy per reference, then processes the
  highest child-first `reset_sequence` first.
- Unknown model/state policies remain blocked.
- Posted, legal and immutable evidence is retained or corrected through owner
  rules; it is never deleted generically.
- Regenerate Missing dispatches only to the generator recorded as owner of the
  missing demo reference.
- No `sudo()`, direct SQL, manual commit, UUID, system-date identity or mutable
  production sequence is introduced by Prompt 23.

## Native acceptance order

1. Upgrade `clinic_demo` and Refresh Compatibility.
2. Continue/Generate Full on the same 29-generator Demo Run.
3. Confirm all 35 checkpoints are Done.
4. Run Validate and require `READY FOR DEMO`.
5. Perform Reset and Regenerate Missing only on a disposable fresh-database
   acceptance run, never on the user's established presentation run.



