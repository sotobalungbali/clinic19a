# Clinic Inventory — Enterprise Development Guardrail

This document is a HARD GATE for every future change to `clinic_inventory`.

## Gate 0 — Project Identity Preflight
Before editing, explicitly resolve:
PROJECT, ADDON, AUTHORITATIVE BASELINE, PRESERVATION RULE, ALLOWED CHANGE, FORBIDDEN CHANGE, CURRENT VERIFIED STATUS.

## Gate 1 — Codex Bukan Architect
Codex is only a bounded implementation worker. Architecture, ownership, dependency topology, and scope decisions require an explicit owner decision.

## Gate 2 — Existing Function Preservation
The supplied active source is a finished functional baseline. No model, field, method, business state, or workflow may disappear to achieve compatibility or test PASS.

## Gate 3 — Enterprise Completeness
Static/runtime test PASS is necessary but insufficient. Operational UI, search, list, form, security, traceability, maintainability, and business usability are reviewed separately.

## Gate 4 — Full Structural Inventory
The baseline model/field/method inventory is retained in `CLINIC_INVENTORY_STRUCTURAL_INVENTORY.md` and machine-readable contract JSON.

## Gate 5 — Human-Friendly Coding Structure
Keep concerns separated by model/domain. Avoid generated monoliths. UI is split by business surface.

## Gate 6 — Professional Form Design
Business documents expose meaningful headers, state/statusbar where an existing state exists, organized groups/notebooks, relevant smart/action buttons, and chatter where the model already supports it.

## Gate 7 — UI/UX Matrix per Model
Every persistent business model has an explicit UX disposition. Technical/internal models are explicitly classified rather than given fake menus.

## Gate 8 — Search View Wajib
Every user-facing persistent ClinicOne inventory model has a Search view.

## Gate 9 — List View Enterprise Quality
Every user-facing persistent ClinicOne inventory model has an operational List view with useful columns/status context.

## Gate 10 — Security Tidak Boleh Dikalahkan UI
ORM ACL/record rules are authoritative. `invisible`, menu groups, or readonly UI are never used as a security substitute.

## Gate 12 — Code Style Human Friendly
Readable names, bounded methods, visible business sections, and minimal cleverness.

## Gate 13 — Comments Yang Berguna
Comments explain business intent, compatibility rationale, or non-obvious safeguards; they do not narrate obvious syntax.

## Gate 14 — Codex Retry Limit
Maximum 3 focused attempts per blocker/root cause. Attempt 3 failure is a mandatory STOP with blocker report and `MOVE_FORWARD_READY: NO`.

## Gate 15 — Enterprise Completeness Matrix
The completeness matrix is maintained separately from automated PASS/FAIL evidence.

## Shared Odoo Model Boundary — Mandatory Regression Gate
`clinic_inventory` extends shared native models such as `product.template`. Clinic-specific defaults and constraints must never silently reclassify ordinary products created by unrelated Odoo addons. `product.template.usage_type` is therefore opt-in, and `ODOO_NATIVE_PRODUCT_BOUNDARY_GATE` must remain PASS.

## Runtime Freeze Rule
Only after target-PC install/upgrade/repeat-upgrade and focused inventory smoke PASS may the addon be marked:
`CLINIC_INVENTORY_MOVE_FORWARD_READY: YES`
and `SOURCE_FROZEN: YES`.




