
# -*- coding: utf-8 -*-
"""
ClinicOne — clinic_triage_vitals
Models package initializer (Odoo 19 CE)

Import order matters due to cross-file dependencies:
1) triage_level   : defines SLA minutes/weight used by triage_session
2) triage_tag     : tag model used by triage_session (m2m)
3) triage_session : core triage session model (links to level, tag, vitals)
4) vitals_intake  : child/related records referenced by triage_session
5) patient_link   : light integration/inheritance to Patient module (clinic_patient)
6) encounter_link : light integration/inheritance to Clinical Encounter module

All field labels, help texts, and messages in individual model files
must be written in English as per product requirement.
"""

# Keep the imports explicit to ensure Odoo picks up model classes.
# DO NOT wrap these in try/except: failures should surface during module load.
from . import triage_level
from . import triage_tag
from . import triage_session
from . import vitals_intake
from . import patient_link
# Intentionally dormant: clinic.encounter ownership/inverse contract is resolved by the encounter addon.
# Codex may not activate this integration without an explicit architecture decision.
# from . import encounter_link

# Optional: explicitly declare the public API of this package.
# __all__ = [
#     "triage_level",
#     "triage_tag",
#     "triage_session",
#     "vitals_intake",
#     "patient_link",
#     "encounter_link",
# ]
