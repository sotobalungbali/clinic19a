# FULL STRUCTURAL INVENTORY — HARD GATE 4

## Owned persistent models

| Model | Role |
|---|---|
| `clinic.treatment.session` | Treatment delivery transaction/workflow |
| `clinic.treatment.session.line` | Procedure/material/medication/billing/stock detail |
| `clinic.treatment.session.stage` | Kanban/workflow stage configuration |

## Historical extensions preserved

- `booking.booking`
- `res.partner`
- `hr.employee`
- `booking.room`
- `res.config.settings`

## Additive canonical bridges

- `clinic.patient`
- `clinic.doctor`
- `clinic.encounter`
- `clinic.branch`
- `clinic.referral`

## Ownership boundaries

Upstream owners remain upstream:
Booking, Referral, Package, Encounter, Inventory, Billing, Audit.

Downstream consumers remain downstream:
Membership, AR, Wallet, Finance, Accounting, Reports, Dashboard, Analytics and
other source-actual consumers.
