# CLINICONE API CONTRACT

Base path: `/api/clinic/v1`

## Authentication

Use an Odoo API token as an explicit Bearer token. The linked Odoo user must have a single active `clinic.api.client` policy for the active company.

## Read endpoints

- `GET /health`
- `GET /resources/<resource>?q=&limit=&offset=`
- `GET /resources/<resource>/<id>`

`limit` is capped at 100. Callers cannot submit arbitrary Odoo domains or field lists.

## Mutation endpoints

- `POST /resources/patients`
- `PATCH /resources/patients/<id>`
- `POST /resources/bookings`
- `PATCH /resources/bookings/<id>`
- `POST /resources/bookings/<id>/actions/{confirm|start|done|cancel|no_show}`

All mutation endpoints require an `Idempotency-Key` header. Mutation fields/actions are whitelisted in source code.

## Resource families

Clinical: Patients, Doctors, Triage Sessions, Encounters, EMAR Orders, Telemedicine Sessions.

Operations: Treatments, Bookings, Queue Visits, Rooms, Packages, Branches.

Finance: Billing Invoices, AR Invoices, AP Documents, Wallets, Memberships, Insurance Authorizations.

Engagement: Post-care Plans, Feedback.

Governance: Report Runs, Incidents, Quality SOPs, Quality Checks.

## Provider callback

`POST /api/clinic/v1/webhooks/<provider_webhook_key>`

Header: `X-Clinic-Webhook-Token: <one-time configured token>`.
