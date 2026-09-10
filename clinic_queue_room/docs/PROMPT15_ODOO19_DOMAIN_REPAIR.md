# Prompt 15 — Odoo 19 Queue Stage Domain Repair

Concrete runtime failure:

`operations.queue_triage: 'tuple' object has no attribute 'lower'`

Root cause:

`clinic.queue._find_stage_by_mapped_state()` passed the nested tuple
`("|", condition_a, condition_b)` as one item inside a search domain. Odoo 19
treats a three-item tuple/list as one simple condition, so its second element
must be an operator string. Here the second element was itself a tuple.

Repair:

Use the prefix OR token form:

- `"|"`
- `("mapped_state", "=", mapped_state)`
- `("code", "=", mapped_state)`

No queue workflow state, security rule, ACL, model ownership, or business
semantics are changed.
