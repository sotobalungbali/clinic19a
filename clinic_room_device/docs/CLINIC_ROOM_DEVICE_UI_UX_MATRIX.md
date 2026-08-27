# ClinicOne — clinic_room_device UI/UX Matrix

| Model | Search | List | Form | Statusbar / lifecycle | Smart / Action Buttons | Notes |
|---|---:|---:|---:|---|---|---|
| `clinic.room` | Yes | Yes | Yes | `status` statusbar | Assignments, Availability | Room master and capacity policy |
| `clinic.room.type` | Yes | Yes | Yes | N/A | Rooms | Configuration master |
| `clinic.device` | Yes | Yes | Yes | `status` statusbar | Assignments, Movements, Stock Moves; lifecycle buttons | Device master |
| `clinic.device.category` | Yes | Yes | Yes | N/A | Devices, Due Maintenance, Due Calibration | Configuration master |
| `clinic.room.device.assignment` | Yes | Yes | Yes | `state` statusbar | Activate, End, Cancel, Open Device, Open Room | Operational placement |
| `clinic.room.availability` | Yes | Yes | Yes | `state` statusbar | Activate, Draft, Archive, Generate Slots | Calendar view also provided |
| `clinic.device.movement` | Yes | Yes | Yes | N/A | Device, From Room, To Room, Stock Moves | Audit/traceability |
| `clinic.room.session` | Yes | Yes | Yes | `state` statusbar | Schedule, Start, Finish, No Show, Cancel, Room, Devices | Calendar view also provided |

### UI security rule
Buttons and menu visibility are usability controls only. ACLs and record rules
remain authoritative.
