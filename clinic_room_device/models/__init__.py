
# -*- coding: utf-8 -*-
"""
ClinicOne - clinic_room_device
Model package initializer

Memuat seluruh model inti serta subpackage `inherit` agar Odoo mengenali
semua class/model pada saat modul di-install.
"""

# ---- Core / Master Models ----
from . import room              # models/room.py
from . import room_type         # models/room_type.py
from . import device            # models/device.py
from . import device_category   # models/device_category.py

# ---- Transactional / Operational Models ----
from . import assignment        # models/assignment.py
from . import availability      # models/availability.py
from . import movement          # models/movement.py

from . import room_session      # new model w/ ChatGPT
# ---- Inherited Models (extend bawaan Odoo/Addon lain) ----
# Penting: import setelah core agar dependensi tersedia.
# from . import inherit           # models/inherit/__init__.py (memuat seluruh inherit)
