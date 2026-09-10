

# ClinicOne — clinic_booking Enterprise Completeness Matrix

| Domain | Static result | Evidence / contract |
|---|---|---|
| Project identity | PASS | ClinicOne / clinic_booking / target path locked |
| Existing function preservation | PASS | Baseline model/field/method subset preserved |
| Odoo 19 SQL constraints | PASS | 19 active legacy constraints migrated; dormant aggregate also migrated |
| Odoo 19 stock API | PASS | `stock.move.line.quantity` / `stock.picking.move_ids` compatibility |
| Odoo 19 action view modes | PASS | Python actions use `list`, not legacy `tree` |
| Odoo 19 display-name behavior | PASS | Custom labels bridged to `_compute_display_name()` |
| Search views | PASS | 24/24 persistent custom models |
| List views | PASS | 24/24 persistent custom models |
| Form views | PASS | 24/24 persistent custom models |
| Main booking workflow UX | PASS | Header actions + statusbar |
| Smart navigation | PASS | Invoice/appointment + existing booking/slot smart actions |
| One2many usability | PASS | Booking lines embedded with row action |
| ACL coverage | PASS | 24/24 persistent custom models, internal users only |
| Multi-company record rules | PASS | 24/24 company-scoped custom models |
| Sequence contract | PASS | Booking and feedback sequences supplied |
| Feedback mail fallback contract | PASS | Default XML template exists for existing `_get_mail_template()` fallback |
| XML-ID/action reference contract | PASS | Local XML refs/actions/direct `env.ref()` targets resolve |
| Model/view cross-contract | PASS | Nested relational fields + object buttons validated against effective custom model fields/methods |
| Relational field contract | PASS | Booking comodels + One2many inverse fields validated |
| Human-friendly source structure | PASS | Domain-split XML + docs + tools |
| Codex bounded-worker guardrail | PASS | Max 3 attempts per blocker class |
| Fresh install on target Odoo 19 | PENDING | Must be executed on PC |
| Repeat upgrade on target Odoo 19 | PENDING | Must be executed on PC |
| Functional smoke on target Odoo 19 | PENDING | Booking lifecycle + invoice/appointment + scheduling |
| Final freeze | PENDING | Only after runtime gates pass |

Static/test PASS is not equivalent to enterprise completion. Runtime and functional evidence are mandatory before freeze.
