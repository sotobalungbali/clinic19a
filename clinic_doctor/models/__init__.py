
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/__init__.py
# Register business models for the clinic_doctor addon (Odoo 18 CE).
# Import order follows the development sequence used in this thread:
# 1) Core identities (doctor, specialty)
# 2) Room extension (inherits clinic.room from clinic_queue_room)
# 3) Scheduling layer (schedule rules, availability slots, leaves)
# 4) Operational flows (appointments, queue)
# 5) Cross-module integrations & hooks (partner, patient, treatment, billing, inventory)

from . import doctor
from . import specialty
# from . import room

from . import schedule_rule
from . import availability
from . import leave

from . import appointment
# from . import queue

from . import res_partner_inherit
# from . import patient_link
# from . import treatment_hook
# from . import billing_hook
# from . import inventory_hook

# __all__ = [
#     "doctor",
#     "specialty",
#     "room_inherit",
#     "schedule_rule",
#     "availability_slot",
#     "leave",
#     "appointment",
#     "queue",
#     "res_partner_inherit",
#     "patient_link",
#     "treatment_hook",
#     "billing_hook",
#     "inventory_hook",
# ]
