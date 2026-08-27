
# -*- coding: utf-8 -*-
# ClinicOne — Consent & Legal Forms
# models/__init__.py
#
# Import order (development flow):
# 1) Core domain models
#    a. consent_form_template   -> sumber konten & default
#    b. consent_form            -> entitas utama persetujuan
#    c. consent_signature       -> ledger tanda tangan (append-only)
#    d. consent_attachment      -> registri lampiran
# 2) Cross-module inherits (ekstensi model modul lain)
#    a. res_partner_inherit     -> statistik & smart actions di kontak/pasien
#    b. treatment_inherit       -> kebijakan consent per treatment
#    c. doctor_schedule_inherit -> kebijakan consent per sesi dokter
#    d. billing_invoice_inherit -> integrasi consent di invoice

# 1) Core domain models
from . import consent_form_template
from . import consent_form
from . import consent_signature
from . import consent_attachment

# 2) Cross-module inherits
from . import res_partner_inherit
from . import treatment_inherit
# from . import doctor_schedule_inherit
from . import appointment_inherit
from . import billing_invoice_inherit
