
# -*- coding: utf-8 -*-
"""
clinic_patient.models
Urutan import disusun agar dependensi model aman saat registry load:

1) patient.py                : model inti clinic.patient (link ke res.partner)
2) patient_identifier.py     : butuh clinic.patient untuk relasi/constraint
3) patient_allergy.py        : butuh clinic.patient (problem list ringkas)
4) patient_condition.py      : butuh clinic.patient (riwayat/kondisi ringkas)
5) patient_vital.py          : butuh clinic.patient (last-known vitals)
6) res_partner_inherit.py    : extend res.partner (smart button → patient)
7) res_users_inherit.py      : extend res.users (opsional, link ke patient/portal)
"""

from . import patient
from . import patient_identifier
from . import patient_allergy
from . import patient_condition
from . import patient_vital
from . import res_partner_inherit
from . import res_users_inherit

# # (Opsional) batasi ekspor simbol; tidak wajib untuk Odoo, hanya dokumentatif.
# __all__ = [
#     "patient",
#     "patient_identifier",
#     "patient_allergy",
#     "patient_condition",
#     "patient_vital",
#     "res_partner_inherit",
#     "res_users_inherit",
# ]

