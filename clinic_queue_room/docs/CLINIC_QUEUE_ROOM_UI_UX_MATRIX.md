
# ClinicOne — clinic_queue_room UI/UX Matrix

| Model | Search | List | Form | Statusbar | Action Buttons | Smart Buttons / Navigation | Security |
|---|---:|---:|---:|---:|---|---|---|
| `clinic.queue` | Yes | Yes | Yes | `state` | Start, Hold, Resume, Done, Release Room, Cancel, No Show, Check SLA | Room Assignment | ACL + company rule |
| `clinic.queue.token` | Yes | Yes | Yes | `state` | Issue, Call, Skip, Serve, Create/Open Queue, Cancel, Expire | Queue | ACL + company rule |
| `clinic.room.assignment` | Yes | Yes | Yes | `state` | Start Service, End Service, Release, Cancel | Queue/room fields in body | ACL + company rule |
| `clinic.queue.visit` | Yes | Yes | Yes | `state` | Start, Finish, Cancel, No Show | Queue | ACL + company rule |
| `clinic.queue.ticket` | Yes | Yes | Yes | `state` | Mark Used, Reissue, Print, Cancel | Linked queue/token/visit | ACL + company rule |
| `clinic.queue.event` | Yes | Yes | Yes | N/A (audit event) | Navigation only | Queue, Room Assignment | ACL + company rule |
| `clinic.queue.stage` | Yes | Yes | Yes | N/A (configuration model) | N/A | Active queue metrics | ACL + company rule |
| `clinic.queue.channel` | Yes | Yes | Yes | N/A (configuration model) | View Queues | Waiting queue smart button | ACL + company rule |
| `hr.employee` queue extension | Existing HR search/list | Existing HR list | Inherited HR form | Availability field | On Duty, On Call, In Service, On Break, Off Duty | Active Queues, Room Assignments | Existing HR security |

## UI policy

- Search view is mandatory for every persistent custom user-facing model.
- `list`, not legacy `tree`, is used for Odoo 19 view terminology.
- Workflow buttons only call existing business methods.
- UI visibility is not treated as security; ORM ACL and multi-company rules remain authoritative.
- Technical/dormant non-imported extensions are not activated merely to increase UI coverage.
