# -*- coding: utf-8 -*-
"""
ClinicOne - Clinical Imaging Management
Models package initializer for the `clinic_imaging` addon.

This file imports ALL model definitions so Odoo can register them.
The import order is arranged from low-level references (types/devices),
to core imaging records and sub-structures (study/series/image/finding/report),
to transactional documents (request/result), analytics (kpi),
and finally model inheritances to keep dependencies stable during install/upgrade.
"""

# ---------------------------------------------------------------------------
# Dictionaries / Master data
# ---------------------------------------------------------------------------
from . import clinical_imaging_type #done
from . import clinical_imaging_device #done

# ---------------------------------------------------------------------------
# Core Imaging entities & hierarchy
# ---------------------------------------------------------------------------
from . import clinical_imaging #done
from . import clinical_imaging_study
from . import clinical_imaging_series
from . import clinical_imaging_image
from . import clinical_imaging_finding
from . import clinical_imaging_report

# ---------------------------------------------------------------------------
# Workflow documents
# ---------------------------------------------------------------------------
from . import clinical_imaging_request
from . import clinical_imaging_result # depends error

# ---------------------------------------------------------------------------
# Analytics / KPIs
# ---------------------------------------------------------------------------
from . import clinical_imaging_kpi

# ---------------------------------------------------------------------------
# Cross-module integrations (inherit existing models)
# ---------------------------------------------------------------------------
from . import res_partner_inherit
from . import hr_employee_inherit
from . import treatment_inherit
from . import encounter_inherit
from . import prescription_order_inherit
from . import consent_inherit
from . import account_move_inherit

# NOTE:
# - Add any new model file imports here to ensure they are loaded by Odoo.
# - Keep the ordering (masters → core → workflow → analytics → inherits) to reduce
#   transient dependency issues during module installation and migrations.
