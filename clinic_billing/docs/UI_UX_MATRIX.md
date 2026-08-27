# UI/UX Matrix — `clinic_billing`

| Model | View matrix | Enterprise UX |
|---|---|---|
| `clinic.billing.invoice` | Search/List/Form | Statusbar; 8+ smart buttons; Booking/Care Plan/eMAR body imports; accounting/payment actions; billing-lines O2M actions |
| `clinic.billing.line` | Search/List/Form | Clinical-source open action; commission recompute; typed source fields |
| `clinic.billing.payment` | Search/List/Form | Statusbar; confirm/post/cancel; account-payment smart navigation |
| `clinic.billing.payment.line` | Search/List/Form | Split method/journal/gateway/fee/account-payment traceability |
| `clinic.billing.discount.rule` | Search/List/Form | Rule scope, priority, membership/code conditions |
| `clinic.billing.discount.redemption` | Search/List/Form | Invoice/patient/rule/code/amount traceability |
| `clinic.billing.voucher.program` | Search/List/Form | Voucher-generation action and policy fields |
| `clinic.billing.voucher` | Search/List/Form | Voucher lifecycle/balance/owner/reservation |
| `clinic.billing.voucher.redemption` | Search/List/Form | Voucher/invoice/line/patient redemption traceability |
| `clinic.insurance.claim` | Search/List/Form | Statusbar; prepare/submit/approve/reject/settle/cancel |
| `clinic.insurance.claim.line` | Search/List/Form | Coverage/deductible/patient-vs-insurer responsibility |
| `clinic.billing.commission.rule` | Search/List/Form | Provider/product/category/base/percent/fixed rules |
| `clinic.billing.commission.line` | Search/List/Form | Invoice/provider/base/commission/settlement traceability |
| `clinic.billing.commission.settlement` | Search/List/Form | Statusbar; collect/confirm/journal entry/payment/cancel |
| `clinic.billing.gateway.tx` | Search/List/Form | Statusbar; initiate/authorize/capture/settle/refund/fail/cancel/chargeback |
| `clinic.billing.gateway.event` | Search/List/Form | Gateway payload/event timeline |
| `clinic.billing.membership.usage` | Search/List/Form | Statusbar; reserve/debit/release/cancel |
| `clinic.treatment.billing.link` | Search/List/Form | Open-origin action and generic source identity |
| `clinic.billing.integration.event` | Search/List/Form | Statusbar; processed/retry/ignore outbox actions |

All 19 persistent owner/domain models have dedicated Search, List and Form views. Runtime-safe upstream smart-button decoration is additive and does not replace the owner views.
