# ClinicOne — clinic_care_plan Enterprise Development Guardrail

## Project identity
- PROJECT: ClinicOne
- ADDON: `clinic_care_plan`
- PLATFORM: Odoo 19 Community Edition
- AUTHORITATIVE BASELINE: user-supplied ClinicOne source dump dated 2026-08-14
- BACKUP RULE: ignore every file whose basename begins with `0`
- PRESERVATION RULE: functional baseline is FINISHED; preserve existing models, fields, methods, workflows and manifest dependencies

## Codex role — HARD GATE
Codex is a **LIMITED IMPLEMENTATION WORKER**.

Codex is **NOT**:
- an architect
- a simplifier
- a product owner
- a model-ownership decision maker
- a dependency optimizer
- an autonomous refactorer
- an endless retry engine

### Machine-readable bounded-worker contract
The following tokens are intentionally explicit so automated guardrails can
verify the same owner policy without interpreting prose:

- `NOT ARCHITECT`
- `NOT SIMPLIFIER`
- `NOT PRODUCT OWNER`
- `NOT MODEL-OWNERSHIP DECISION MAKER`
- `NOT DEPENDENCY OPTIMIZER`
- `NOT AUTONOMOUS REFACTORER`
- `NOT ENDLESS RETRY ENGINE`

Codex may implement a bounded, explicitly identified compatibility/runtime repair only after the owner contract and acceptance criteria are already defined.

## Mandatory preservation
Codex must not remove, rename, merge, move, deactivate, or silently replace an existing business model, field, method, state, workflow, dependency, security rule, or integration contract merely to make tests pass.

The following baseline imports must remain active:
- `care_plan`
- `procedure_session_inherit`
- `emar_prescription_inherit`
- `care_protocol`
- `care_plan_line`
- `care_protocol_step`
- `practitioner_inherit`

The following additive integration modules are owner-approved:
- `patient_inherit`
- `doctor_inherit`
- `encounter_inherit`

`models/models.py` is dormant scaffold source and must remain unimported unless the owner explicitly changes architecture.

## Odoo 19 hard requirements
- No executable legacy `_sql_constraints`; use `models.Constraint`.
- No `fields.DateUtils` dependency.
- No deprecated `group_operator`; use `aggregator`.
- No Python `tree` action terminology; use `list`.
- Every implicit/explicit Many2many relation identifier must fit PostgreSQL's identifier limit.
- Cross-addon presentation XML-IDs must not become installation blockers.
- ORM ACL/record rules are authoritative; UI visibility is not security.

## Retry limit — HARD GATE 14
`MAX_FOCUSED_REPAIR_ATTEMPTS_PER_BLOCKER = 3`

After the third focused attempt for the same blocker/root-cause class:
1. STOP editing.
2. Set `MOVE_FORWARD_READY: NO`.
3. Report the failing gate/command/traceback.
4. Report attempts 1–3 and why each failed.
5. Request an owner/architecture decision instead of starting attempt 4.

## Completion rule
Static/runtime/test PASS alone is not enterprise completion. Move-forward requires preservation, structural inventory, Odoo 19 compatibility, UI coverage, ORM security, local XML-ID/sequence/report contracts, and target-PC runtime installation.
