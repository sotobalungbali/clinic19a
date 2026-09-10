
# -*- coding: utf-8 -*-
"""
ClinicOne - Clinical Queue & Room Management (Odoo 18 CE)
File: models/__init__.py

Import order matters. Keep this sequence to avoid circular imports:

1) Foundations (referenced by core models):
   - clinic_queue_stage
   - clinic_queue_token

2) Core entities:
   - clinic_room
   - clinic_queue

3) Flow / auxiliary entities (depend on core):
   - clinic_room_assignment
   - clinic_queue_event

4) Cross-module inherits (extend models from other ClinicOne apps):
   - res_partner_inherit
   - appointment_inherit
   - treatment_inherit
   - hr_doctor_inherit
"""

# 1) Foundations
from . import clinic_queue_stage
from . import clinic_queue_token

# clinic_room_device

# 2) Core entities
# from . import clinic_room # DIHAPUS, sudah ada di clinic_room_device
from . import clinic_queue

# 3) Flow / auxiliary
from . import clinic_room_assignment
from . import clinic_queue_event
from . import clinic_queue_channel
from . import clinic_queue_visit
from . import clinic_queue_ticket

# 4) Cross-module inherits
# from . import res_partner_inherit
# from . import appointment_inherit
# from . import treatment_inherit
from . import hr_doctor_inherit
