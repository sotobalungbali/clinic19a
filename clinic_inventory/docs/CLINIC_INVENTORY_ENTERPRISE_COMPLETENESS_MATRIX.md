# Clinic Inventory — Enterprise Completeness Matrix

| Area | Requirement | Status | Evidence |
|---|---|---|---|
| Identity | Correct ClinicOne / clinic_inventory target | PASS | Guardrail Gate 0 |
| Preservation | Existing models/fields/methods preserved | PASS | Baseline contract + validator |
| Odoo 19 | Legacy `_sql_constraints` removed | PASS | `models.Constraint` migration |
| Odoo 19 | `stock.move.line.qty_done` removed from active code | PASS | Uses `quantity` |
| Odoo 19 | Product goods semantics corrected | PASS | `type='consu'` + `is_storable` mapping |
| Data contract | Existing sequence calls have sequence records | PASS | `data/clinic_inventory_sequence.xml` |
| Workflow | Treatment usage states/actions surfaced | PASS | Professional form + statusbar |
| Workflow | Inventory adjustment states/actions surfaced | PASS | Professional form + statusbar |
| Traceability | Patient product history visible and navigable | PASS | Search/List/Form + smart buttons |
| Governance | Doctor product rules visible and secured | PASS | Search/List/Form + manager ACL |
| Integration audit | Event log read UI | PASS | Manager-only Search/List/Form |
| Search quality | All user-facing persistent models have search views | PASS | UI/UX matrix |
| List quality | All user-facing persistent models have enterprise lists | PASS | UI/UX matrix |
| Form quality | All user-facing persistent models have professional forms | PASS | UI/UX matrix |
| Security | ORM ACL and company rules authoritative | PASS | security XML/CSV |
| Security | No public/portal access introduced | PASS | ACL inventory |
| Maintainability | Human-friendly file split and comments | PASS | views/docs/tools structure |
| Codex | Limited implementation worker | PASS | `AGENTS.md` |
| Codex | Max 3 focused repair attempts | PASS | Guardrail + validator |
| Runtime | PC fresh/install/upgrade/smoke | PENDING | Must run on target PC |

