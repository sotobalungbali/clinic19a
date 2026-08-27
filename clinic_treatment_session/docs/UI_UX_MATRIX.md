# UI / UX MATRIX — HARD GATES 6–9

| Model | Search | List | Form | Kanban | Calendar | Graph/Pivot | Statusbar | Enterprise Actions |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `clinic.treatment.session` | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Confirm, Start, Complete, No-show, Cancel, Reset, Consumption, Billing |
| `clinic.treatment.session.line` | Yes | Yes | Yes | n/a | n/a | n/a | Yes | Ready, Consume, Reset, Open Stock |
| `clinic.treatment.session.stage` | Yes | Yes | Yes | via Session kanban | n/a | n/a | n/a | Open Sessions |

Runtime-safe smart-button bridges target Booking, Patient, Doctor, Encounter and
Branch. Their UI decoration is optional; core Treatment Session installation is
never made dependent on stale foreign view XML IDs.
