# ClinicOne clinic_wallet — Codex Bounded Worker Contract

Codex is an implementation worker only. It is **not** the architect, simplifier, dependency owner, or autonomous redesign authority.

## Fixed architecture

- Project: ClinicOne, Odoo 19 CE.
- Addon: `clinic_wallet`.
- Authoritative baseline: the full corrected source in this package plus the upstream ClinicOne addons through `clinic_ap`.
- Ownership: `clinic_wallet` owns wallet ledger, wallet rules, wallet requests, Wallet settings, and downstream bridge logic. It must not move ownership into upstream addons.
- Existing public APIs, models, fields, workflows, views, security and integration contracts are preservation targets.

## Allowed implementation work

A worker may fix a reproduced defect inside the approved owner file, add a regression test, and make the smallest implementation change consistent with the architecture already documented here.

## Forbidden changes

A worker must not delete or rename models/fields/methods/views, remove dependencies, replace enterprise UI with scaffold UI, bypass security, disable constraints, turn hard dependencies into silent optional behavior, move ownership to another addon, or reduce a feature merely to make tests pass.

## Retry limit

`MAX_RETRY_ITERATIONS = 2` for one verified defect. After two failed implementation attempts, stop and report the exact blocker, traceback, files touched, and evidence. Never enter an open-ended retry loop.




