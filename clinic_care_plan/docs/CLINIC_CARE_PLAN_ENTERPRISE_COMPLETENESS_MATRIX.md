# ClinicOne — clinic_care_plan Enterprise Completeness Matrix

| Gate | Requirement | Evidence / implementation |
|---|---|---|
| 0 | Project identity preflight | Root/addon/version/dependency contract checked by machine guardrail |
| 1 | Codex bukan architect | `AGENTS.md` locks Codex to bounded implementation only |
| 2 | Existing function preservation | Baseline model/field/method/dependency contract machine-compared |
| 3 | Enterprise completeness != test pass | UI/security/integration/report/sequence/schema gates are independent |
| 4 | Full structural inventory | `CLINIC_CARE_PLAN_STRUCTURAL_INVENTORY.md` |
| 5 | Human-friendly coding | Domain-separated model/view/security/data/report/hook files |
| 6 | Professional form design | Lifecycle headers, statusbars, smart buttons, notebooks, body actions |
| 7 | UI/UX matrix per model | 4/4 persistent models documented |
| 8 | Search view wajib | 4/4 persistent models |
| 9 | Enterprise list quality | 4/4 lists with relevant columns/decorations/optional fields |
| 10 | Security over UI | ACL + multi-company rules; no public/portal ACL |
| 12 | Human-friendly code style | Named sections, focused files, stable method names |
| 13 | Useful comments | Comments explain integration/security/compatibility rationale |
| 14 | Codex retry limit | Maximum 3 focused attempts per blocker/root-cause class |
| 15 | Enterprise completeness matrix | This file + machine guardrail |

## Runtime status
`CLINIC_CARE_PLAN_STATIC_MOVE_FORWARD_READY` may be YES after all static gates
pass. `CLINIC_CARE_PLAN_MOVE_FORWARD_READY` remains PENDING until the target
Odoo 19 PC install/upgrade succeeds.
