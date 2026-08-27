# UI / UX MATRIX — HARD GATES 6–9

| Model | Search | List | Form | Kanban | Graph/Pivot | Statusbar | Enterprise actions |
|---|---:|---:|---:|---:|---:|---:|---|
| `clinic.referral` | Yes | Yes | Yes | Yes | Yes | Yes | Confirm, Convert, Cancel, Expire, Reward actions, Patient, Booking, Session, Membership, Audit, Origin, Conversion |
| `clinic.referral.program` | Yes | Yes | Yes | n/a | via Referral analysis | Yes | Start, Pause, Reset, Close, Archive, Referrals, Bookings, Memberships |
| `clinic.referral.source` | Yes | Yes | Yes | n/a | via Referral analysis | n/a | Referrals, Patients, Bookings, Memberships |

Cross-addon UX:

- Booking form/search: Referral attribution and Create/Open Referral.
- Patient 360: inbound and outgoing Referral smart buttons.
- Branch form: Referral smart button.
- Program/Source One2many histories: row-level **Open** button.
