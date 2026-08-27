# -*- coding: utf-8 -*-
"""
ClinicOne - Treatment Session
Extensions package initializer.

Berisi semua ekstensi model eksternal yang di-hook oleh addon ini:
- booking.booking       → ext_booking
- booking.room          → ext_room_device
- res.partner (patient) → ext_patient
- hr.employee (doctor)  → ext_doctor
"""

from . import ext_booking
from . import ext_room_device
from . import ext_patient
from . import ext_doctor
