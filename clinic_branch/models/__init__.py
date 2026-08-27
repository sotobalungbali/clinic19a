
# -*- coding: utf-8 -*-
"""
ClinicOne — clinic_branch
models/__init__.py

Urutan import:
1) Mixin  (menyediakan field/constraint bersama)
2) Core   (master branch & location)
3) Inherit (extend model Odoo untuk mapping & preferensi per cabang)

Catatan:
- Folder models/bridges TIDAK di-import di sini demi soft-coupling.
  Integrasi lintas-modul (booking/patient/treatment/billing/inventory/portal/reports)
  sebaiknya diaktifkan dari modul terkait atau dengan guard di masing-masing bridge.
"""

# 1) MIXIN
from . import mixin_branch

# # 2) CORE MODELS
from . import branch
from . import branch_location

# # 3) INHERIT ODOO/CLINICONE
from . import res_company_inherit
from . import res_users_inherit
from . import res_partner_inherit          # contacts
from . import hr_employee_inherit          # hr
from . import stock_warehouse_inherit      # stock
from . import account_move_inherit         # account

