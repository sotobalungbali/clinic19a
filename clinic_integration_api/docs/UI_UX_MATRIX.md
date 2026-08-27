# UI/UX MATRIX — HARD GATES 6–9

| Model | Search | List | Form | Statusbar | Header/Body Actions | Smart Button | One2many row action |
|---|---|---|---|---|---|---|---|
| clinic.api.client | Yes | Yes | Yes | Yes | Activate/Suspend/Reset | Requests, Idempotency | Recent request evidence |
| clinic.api.provider | Yes | Yes | Yes | Yes | Activate/Suspend/Reset, credential/token, validate endpoint | Subscriptions, Deliveries | Subscription delivery button |
| clinic.api.event | Yes | Yes | Yes | Yes | Queue/Retry/Cancel | Deliveries | Open Event / Retry Delivery |
| clinic.api.webhook.subscription | Yes | Yes | Yes | Yes | Activate/Suspend/Reset | Deliveries | Open Event / Retry Delivery |
| clinic.api.webhook.delivery | Yes | Yes | Yes | Yes | Retry/Open Event | — | List row Open/Retry |
| clinic.api.scope | Yes | Yes | Yes | — | configuration | — | — |
| clinic.api.event.type | Yes | Yes | Yes | — | configuration | — | — |
| clinic.api.request.log | Yes | Yes | Yes | — | immutable evidence | — | — |
| clinic.api.idempotency | Yes | Yes | Yes | — | governed evidence | — | — |
