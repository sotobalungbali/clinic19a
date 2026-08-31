
# ClinicOne — clinic_room_device Enterprise Development Guardrail

## Purpose
This guardrail protects the already-finished functional baseline while allowing
bounded Odoo 19 compatibility and enterprise-quality hardening.

## HARD GATE 0 — PROJECT IDENTITY PREFLIGHT
Project, addon, authoritative baseline, allowed change, forbidden change, and
verified status must be explicit before editing.

## HARD GATE 1 — CODEX BUKAN ARCHITECT
Codex may implement an approved correction. It may not redesign ownership,
dependencies, workflows, or cross-addon architecture.

## HARD GATE 2 — EXISTING FUNCTION PRESERVATION
No existing non-backup model, field, method, or workflow may silently disappear.
Dormant `models/inherit` remains dormant.

## HARD GATE 3 — ENTERPRISE COMPLETENESS BUKAN SEKADAR TEST PASS
Source/static/runtime PASS does not by itself prove enterprise completeness.
UI, security, structural inventory, cross-contracts, and business usability are
separate gates.

## HARD GATE 4 — FULL STRUCTURAL INVENTORY
The addon keeps a model/field/method inventory derived from the original
non-backup source.

## HARD GATE 5 — HUMAN-FRIENDLY CODING STRUCTURE
Domain views are split by business concern. Python files remain model-oriented.

## HARD GATE 6 — PROFESSIONAL FORM DESIGN
Lifecycle models use headers/statusbars and existing object actions where they
already exist. Smart buttons expose useful existing navigation.

## HARD GATE 7 — UI/UX MATRIX PER MODEL
Every persistent custom model has an explicit UI/UX decision.

## HARD GATE 8 — SEARCH VIEW WAJIB
Every persistent custom model has a Search view.

## HARD GATE 9 — LIST VIEW ENTERPRISE QUALITY
Every persistent custom model has a useful List view.

## HARD GATE 10 — SECURITY TIDAK BOLEH DIKALAHKAN UI
ACLs and multi-company record rules are authoritative. Invisible/readonly/menu
visibility never substitutes for ORM security.

## HARD GATE 12 — CODE STYLE HUMAN FRIENDLY
Readable sections, descriptive methods, bounded helpers, and straightforward
XML are preferred over compact generator-like code.

## HARD GATE 13 — COMMENTS YANG BERGUNA
Comments explain Odoo 19 compatibility, optional integrations, and architectural
boundaries; they do not narrate obvious syntax.

## HARD GATE 14 — CODEX RETRY LIMIT
Maximum focused repair attempts per blocker/root-cause class: 3. Then STOP and
produce a blocker report.

## HARD GATE 15 — ENTERPRISE COMPLETENESS MATRIX
The addon maintains a matrix separating functional preservation, UI, security,
Odoo 19 compatibility, and runtime validation.

## Odoo 19 specific gates
- no legacy `_sql_constraints`;
- use `models.Constraint`;
- no legacy Python `tree` view modes;
- `name_search` uses `domain=None`;
- no field/method namespace collision;
- all compute/inverse/search method references resolve;
- One2many inverses resolve inside the custom model set;
- Search view domains do not target unsearchable non-stored computed fields;
- local XML IDs and sequence references resolve;
- no hard dependency on Accounting merely for `supplier_rank`;
- Product Type compatibility uses Odoo 19 values (`consu`, `service`, `combo`).
