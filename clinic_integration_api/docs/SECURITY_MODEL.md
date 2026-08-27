# SECURITY MODEL — HARD GATE 10

## Authentication

Business API endpoints use Odoo 19 `auth="bearer"` and additionally require an explicit `Authorization: Bearer ...` header so an authenticated browser session cannot silently become an API credential.

The bearer token remains an Odoo user token. This addon never stores a duplicate token.

## Authorization layering

1. Odoo service-user ACLs and record rules remain authoritative.
2. `clinic.api.client` narrows the caller by scope, company, branch, rate, and idempotency policy.
3. Resource/model/domain/method choices are fixed in Python code, not accepted from callers.
4. Business model operations run without `sudo()`.
5. `sudo()` is limited to technical metadata/log/event/token-secret lookup owned by this addon.

## Provider secrets

Outbound provider credentials are stored in `ir.config_parameter`, not in ordinary provider fields. Inbound webhook tokens are shown once; only SHA-256 digests are retained.

## Webhooks

Inbound webhooks require an opaque per-provider URL key plus `X-Clinic-Webhook-Token`. Business work runs as the configured provider service user.

Outbound provider URLs require HTTPS. Embedded URL credentials and local/private/reserved destinations are blocked by default. Redirects are refused, body/response sizes and timeout are bounded, and private-network access requires an explicit manager-only override.

## Sensitive evidence

Raw provider event payloads, idempotency replay bodies, diagnostic response excerpts, and detailed error evidence are Manager-only fields.
