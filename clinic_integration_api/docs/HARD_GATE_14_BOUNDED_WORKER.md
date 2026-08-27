# HARD GATE 14 — CODEX RETRY LIMIT

Architecture, ownership, security boundaries, resource contracts, and dependency direction are fixed by the ClinicOne baseline and this guardrail. An implementation worker may repair a concrete validation defect a maximum of three bounded attempts for a build cycle. It must not redesign ownership, delete functions merely to make tests pass, turn the API into generic RPC, or retry indefinitely.

## Build-cycle repair ledger

Repair attempts used: **3 / 3 (final bounded attempt)**.

1. Contract gate exposed unprovable relation paths and a false-positive legacy-constraint scanner.
2. Resource/branch paths and AST-based legacy-constraint detection were corrected; guardrail passed.
3. Final regression hardening removed the self-referential test false positive, made bearer-user policy unambiguous, aligned mutations/logging with the active allowed company, bound emitted events to authoritative branch paths, and enforced delivery scope in Python. No further repair loop is permitted in this build cycle.
