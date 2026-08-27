
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Staff (Nurse & Therapist) Management
# File: clinic_staff/models/practitioner.py
#
# Model "clinic.practitioner" dipakai lintas modul (mis. clinic_care_plan: m2m ke practitioner).
# Disusun CE-safe: tanpa hard dependency ke modul Enterprise. Integrasi ke modul lain dilakukan
# secara longgar (env.get, optional domains, compute toleran jika model lain belum terpasang).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date, datetime, timedelta


class ClinicPractitioner(models.Model):
    _inherit = "clinic.practitioner"

    # pindah ke addon clinic_care_plan
    # =====================================================================
    # DELETE GUARDS (avoid orphan references)
    # =====================================================================
    def unlink(self):
        CarePlan = self.env.get("clinic.care.plan")
        for rec in self:
            if CarePlan:
                # The canonical Care Plan field is ``practitioner_ids``.
                # Do not place speculative/non-existent field names in an ORM
                # domain: Odoo validates domain fields at runtime.
                linked = CarePlan.search_count(
                    [("practitioner_ids", "in", rec.id)]
                ) > 0
                if linked:
                    raise ValidationError(
                        _("Cannot delete practitioner '%s' because it is referenced by one or more Care Plans.")
                        % (rec.display_name or rec.name)
                    )
        return super().unlink()
