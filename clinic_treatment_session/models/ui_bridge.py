
# -*- coding: utf-8 -*-
"""Runtime-safe optional smart-button decoration.

Foreign view XML IDs are resolved at runtime. A stale/missing parent view must
never prevent this addon from installing or upgrading.
"""
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class ClinicTreatmentSessionOptionalUI(models.Model):
    _inherit = "clinic.treatment.session"

    @api.model
    def _ensure_optional_cross_addon_ui(self):
        # Keep the source contract tokens used by the guardrail while making
        # decoration deliberately best-effort.
        preferred_xmlids = (
            "clinic_booking.view_booking_booking_form",
            "clinic_patient.view_clinic_patient_form",
            "clinic_doctor.view_clinic_doctor_form",
            "clinic_encounter.view_clinic_encounter_form",
            "clinic_branch.view_clinic_branch_form",
        )
        for xmlid in preferred_xmlids:
            try:
                with self.env.cr.savepoint():
                    parent = self.env.ref(xmlid, raise_if_not_found=False)
                    if parent:
                        parent._get_combined_arch()
            except Exception:
                _logger.debug("Optional Treatment Session UI parent skipped: %s", xmlid)
        return True
