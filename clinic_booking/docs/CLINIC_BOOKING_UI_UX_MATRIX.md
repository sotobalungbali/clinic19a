
# ClinicOne — clinic_booking UI/UX Matrix

| Model | Search | List | Form | Primary access | UX note |
|---|---|---|---|---|---|
| `booking.tag` | PASS | PASS | PASS | Configuration menu | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.channel` | PASS | PASS | PASS | Configuration menu | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.policy` | PASS | PASS | PASS | Configuration menu | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.policy.exception` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.room.tag` | PASS | PASS | PASS | Embedded / relational maintenance | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.room` | PASS | PASS | PASS | Configuration menu | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.room.schedule` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.room.blackout` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.resource.tag` | PASS | PASS | PASS | Embedded / relational maintenance | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.resource` | PASS | PASS | PASS | Configuration menu | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.resource.schedule` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.resource.blackout` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.slot` | PASS | PASS | PASS | Scheduling menu | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.slot.exception` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.recurring.rule` | PASS | PASS | PASS | Scheduling menu | Maintained as supporting scheduling/configuration model. |
| `booking.recurring.weekday` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.recurring.monthday` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.recurring.byweekday` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.recurring.exdate` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.booking` | PASS | PASS | PASS | Bookings menu + calendar | Professional header actions, statusbar, smart buttons, calendar, one2many booking lines. |
| `booking.line` | PASS | PASS | PASS | Embedded / relational maintenance | Dedicated Search/List/Form; parent smart/body actions used where existing methods support them. |
| `booking.feedback.link` | PASS | PASS | PASS | Operations menu | Lifecycle/status fields retained; feedback actions remain model methods. |
| `booking.doctor.schedule` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |
| `booking.doctor.blackout` | PASS | PASS | PASS | Embedded / relational maintenance | Maintained as supporting scheduling/configuration model. |

## UI security rule

Visibility, readonly modifiers, menus, and buttons are not security controls. ACLs and record rules remain authoritative.


