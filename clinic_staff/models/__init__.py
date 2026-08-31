

# -*- coding: utf-8 -*-
"""
ClinicOne — Clinical Staff (Nurse & Therapist) Management
Odoo 18 CE
File: clinic_staff/models/__init__.py

Catatan:
- Urutan import disusun dari model dasar ke integrasi lintas-modul agar dependensi class/fields
  tersedia saat registry dibangun oleh Odoo.
- Masing-masing file model telah didesain "soft dependency" (env.get / ondelete, dsb) sehingga
  aman dipasang bersama 25 modul ClinicOne lainnya.
"""

# titipan bentar
# from . import res_partner_inherit

# === Core domain & capability models (fundamental) ===
from . import staff                # master staff, role/grade, eligibility, partner link
from . import staff_skill          # skill-matrix & validation
from . import staff_license        # license & expiry tracking
from . import staff_availability   # availability slots / calendar
from . import staff_roster         # shift templates & roster (Gantt)
from . import staff_assignment     # assignment to room/queue/procedure
from . import staff_workload       # workload target vs actual
from . import staff_presence       # presence (check-in/out) & readiness
from . import staff_kpi            # KPI aggregates & scorecards
from . import practitioner

# === Clinical flow integrations (operational runtime) ===
# from . import integration_queue        # queue/triage entry points into staff flow
# from . import integration_room         # room/bed linkage & capacity hints
# from . import integration_triage       # triage signals → eligibility/handover
# from . import integration_encounter    # encounter context linking
# from . import integration_procedure    # procedure performer/assistant hooks
# from . import integration_emar         # eMAR administration linkage
# from . import integration_postcare     # post-care task assignment
# from . import integration_incident     # incident reporting & staff involvement
# from . import integration_telemedicine # telemedicine session → staff host/agent

# === Commercial/finance/inventory integrations (backoffice) ===
# from . import integration_billing      # billing activities & revenue allocation bridge
# from . import integration_accounting   # account.move/line clinical context + auto allocation
# from . import integration_finance      # cost rate, accrual, settlement; analytic mapping
# from . import integration_inventory    # consumption & stock.scrap linkage
# from . import integration_insurance    # payer/plan/policy, pre-auth, claim & adjudication

# pindah ke addon clinic_treatment_catalog
# === Compliance / consent ===
# from . import integration_consent      # consent templates/versions/requests & enforcement


