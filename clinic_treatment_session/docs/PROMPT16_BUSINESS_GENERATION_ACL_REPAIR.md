# Prompt 16 — Treatment Session Business Generation ACL Repair

Runtime failure:
`operations.treatment_session` was denied read access to `ir.actions.act_window`
under the linked clinician.

Root cause:
the Booking generation action combined Treatment Session business creation with
UI Action Window construction.

Repair:
- add owner business API `generate_treatment_sessions()`;
- preserve `action_generate_treatment_sessions()` as the UI wrapper;
- keep clinician security boundaries unchanged.
