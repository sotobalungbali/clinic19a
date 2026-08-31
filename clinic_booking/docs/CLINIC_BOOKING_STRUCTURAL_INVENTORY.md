
# ClinicOne — clinic_booking Full Structural Inventory

Baseline: active non-backup source from the uploaded ClinicOne dump. Files whose names begin with digit `0` are excluded.

## Custom models and abstract mixins

| Model | Type | File | Fields | Methods |
|---|---|---|---:|---:|
| `booking.booking` | Persistent model | `models/booking_booking.py` | 31 | 25 |
| `booking.channel` | Persistent model | `models/booking_channel.py` | 23 | 17 |
| `booking.channel.mixin` | Abstract mixin | `models/booking_channel.py` | 1 | 1 |
| `booking.doctor.blackout` | Persistent model | `models/clinic_doctor_inherit.py` | 7 | 2 |
| `booking.doctor.schedule` | Persistent model | `models/clinic_doctor_inherit.py` | 7 | 1 |
| `booking.feedback.link` | Persistent model | `models/booking_feedback_link.py` | 27 | 21 |
| `booking.feedback.link.mixin` | Abstract mixin | `models/booking_feedback_link.py` | 1 | 1 |
| `booking.line` | Persistent model | `models/booking_line.py` | 22 | 11 |
| `booking.policy` | Persistent model | `models/booking_policy.py` | 39 | 17 |
| `booking.policy.exception` | Persistent model | `models/booking_policy.py` | 13 | 2 |
| `booking.policy.mixin` | Abstract mixin | `models/booking_policy.py` | 1 | 1 |
| `booking.recurring.byweekday` | Persistent model | `models/booking_recurring_rule.py` | 4 | 0 |
| `booking.recurring.exdate` | Persistent model | `models/booking_recurring_rule.py` | 5 | 0 |
| `booking.recurring.monthday` | Persistent model | `models/booking_recurring_rule.py` | 4 | 1 |
| `booking.recurring.rule` | Persistent model | `models/booking_recurring_rule.py` | 22 | 19 |
| `booking.recurring.rule.mixin` | Abstract mixin | `models/booking_recurring_rule.py` | 1 | 1 |
| `booking.recurring.weekday` | Persistent model | `models/booking_recurring_rule.py` | 4 | 0 |
| `booking.resource` | Persistent model | `models/booking_resource.py` | 26 | 16 |
| `booking.resource.blackout` | Persistent model | `models/booking_resource.py` | 7 | 2 |
| `booking.resource.mixin` | Abstract mixin | `models/booking_resource.py` | 1 | 1 |
| `booking.resource.schedule` | Persistent model | `models/booking_resource.py` | 7 | 1 |
| `booking.resource.tag` | Persistent model | `models/booking_resource.py` | 3 | 0 |
| `booking.room` | Persistent model | `models/booking_room.py` | 20 | 13 |
| `booking.room.blackout` | Persistent model | `models/booking_room.py` | 7 | 2 |
| `booking.room.schedule` | Persistent model | `models/booking_room.py` | 7 | 1 |
| `booking.room.tag` | Persistent model | `models/booking_room.py` | 3 | 0 |
| `booking.slot` | Persistent model | `models/booking_slot.py` | 26 | 19 |
| `booking.slot.exception` | Persistent model | `models/booking_slot.py` | 9 | 2 |
| `booking.slot.mixin` | Abstract mixin | `models/booking_slot.py` | 1 | 1 |
| `booking.tag` | Persistent model | `models/booking_tag.py` | 4 | 1 |

## Native/ClinicOne model extensions

| Extended model | Class | File | Added fields | Added methods |
|---|---|---|---:|---:|
| `res.partner` | `ResPartner` | `models/res_partner_inherit.py` | 18 | 15 |
| `clinic.doctor` | `ClinicDoctor` | `models/clinic_doctor_inherit.py` | 12 | 13 |
| `clinic.treatment` | `ClinicTreatment` | `models/treatment_inherit.py` | 11 | 10 |
| `account.move` | `AccountMove` | `models/account_move_inherit.py` | 7 | 9 |
| `account.move.line` | `AccountMoveLine` | `models/account_move_inherit.py` | 4 | 2 |
| `stock.move` | `StockMove` | `models/stock_move_inherit.py` | 7 | 5 |
| `stock.picking` | `StockPicking` | `models/stock_move_inherit.py` | 5 | 6 |

## Preservation rule

The baseline fields/methods above are preservation contracts. Technical hardening may add helpers, views, security, or Odoo 19 compatibility code, but it must not silently remove existing business structure.


