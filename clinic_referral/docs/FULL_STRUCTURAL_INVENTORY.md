# FULL STRUCTURAL INVENTORY — HARD GATE 4

## Owned models

| Model | Role | Preserved contract |
|---|---|---|
| `clinic.referral` | Transaction / workflow | patient, doctor, referrer, source, program, dates, reward, origin, lifecycle |
| `clinic.referral.program` | Master / governance | validity period, eligibility, reward policy, applicability |
| `clinic.referral.source` | Master / attribution | source classification, referrer entity, campaign metadata, defaults, statistics |

## In-place integrations

| Model | Additive integration |
|---|---|
| `booking.booking` | `referral_id`, related source/program, create/open Referral |
| `clinic.patient` | inbound/outbound referral counters and navigation |
| `clinic.branch` | branch referral counters and navigation |
| `crm.lead` | Clinic Referral lineage and counters |
| `res.company` | Referral governance defaults |
| `res.config.settings` | Odoo 19 settings extension |

## Optional downstream integrations

These models are runtime-detected and intentionally absent from the manifest:

- `membership.contract`
- `clinic.treatment.session`
- `clinic.treatment.session.line`

## Baseline defects corrected

1. Security and ACL files existed conceptually but were not loaded by the draft manifest.
2. Referral / Program / Source sequence codes were used by Python but no sequence data was loaded.
3. The old Booking counter looked for `clinic.booking`; actual owner model is `booking.booking`.
4. `clinic.referral.source` still used executable legacy `_sql_constraints`.
5. Date-relative `is_expired` / `is_current` / `is_future` / `is_past` were stored and could become stale.
6. Several action methods conflicted with their own state-transition map.

## Upgrade-safety migration

`migrations/19.0.2.0.0/pre-migrate-source-codes.py` repairs placeholder or
duplicate historical Referral Source codes before the Odoo 19 UNIQUE constraint
is applied. It changes only conflicting legacy identifiers and preserves all
business relations.

