# -*- coding: utf-8 -*-
"""
ClinicOne — clinic_booking
models/__init__.py

Load order (safe-by-design):
1) Foundation entities (static/master data used by bookings)
2) Primary booking model
3) Detail/auxiliary models that depend on the primary model
4) Cross-module inherits (extend models from other apps)

This ordering helps avoid early imports of classes that rely on fields
computed against not-yet-registered models, reducing registry noise and
keeping holistic integrations predictable.
"""

from . import booking_tag

# 1) FOUNDATION ENTITIES (independent or lightly-referenced masters)
from . import booking_channel          # Walk-in / Phone / Web / etc.
from . import booking_policy           # Cancellation window, deposits, terms
from . import booking_room             # Clinical rooms & capacity - OKAY
from . import booking_resource         # Devices, machines, tools
from . import booking_slot             # Optional predefined working slots
from . import booking_recurring_rule   # Optional recurring patterns (if any)

# 2) FEEDBACK FOUNDATION / MIXIN
# Loaded before booking.booking so the abstract mixin is available when
# the primary model inherits it; its Many2one still uses a string comodel.
from . import booking_feedback_link    # Feedback model + booking.feedback.link.mixin

# 3) PRIMARY BOOKING MODEL (ties patient/doctor/treatment/time/resources)
from . import booking_booking          # Core: booking.booking

# 4) DETAIL & AUXILIARY (depend on primary or enrich it)
from . import booking_line             # Items/services/consumables for a booking

# 5) CROSS-MODULE INHERITS (extend models from other modules)
from . import res_partner_inherit      # Patient profile hooks/history
from . import clinic_doctor_inherit    # Handshake to clinic.appointment (lives in clinic_doctor)
from . import treatment_inherit        # Defaults/pricing/allowed doctors from clinic_treatment
from . import account_move_inherit     # Invoice linkage (account.move)
from . import stock_move_inherit       # Stock/consumables linkage (stock.picking / moves)
