# FULL STRUCTURAL INVENTORY — HARD GATE 4

## Owned persistent models

1. `clinic.api.scope`
2. `clinic.api.client`
3. `clinic.api.provider`
4. `clinic.api.request.log`
5. `clinic.api.idempotency`
6. `clinic.api.event.type`
7. `clinic.api.event`
8. `clinic.api.webhook.subscription`
9. `clinic.api.webhook.delivery`

## Owned technical/transient models

- abstract `clinic.api.service`
- transient `clinic.api.provider.credential.wizard`
- transient `clinic.api.webhook.token.wizard`

## Additive upstream extensions

- `clinic.marketing.message`
- `clinic.telemedicine.session`
- `clinic.billing.gateway.tx`

## Controllers

- Bearer-only ClinicOne resource API
- authenticated provider inbound webhook

## Enterprise layers

- groups, ACLs, company record rules
- seeded scopes and event types
- sequences and bounded crons
- Search/List/Form views for every persistent model
- smart buttons, workflow buttons, statusbars, One2many row buttons
- static Enterprise Development Guardrail and source-contract tests
