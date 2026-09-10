# -*- coding: utf-8 -*-
"""Patient-safety and medication-administration verification.

The eMAR must never treat form modifiers as a safety boundary.  Clinical gates
are enforced in ORM methods and leave a durable safety result on the record.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


SAFETY_SELECTION = [
    ("pending", "Pending"),
    ("pass", "Passed"),
    ("warning", "Warning / Review Required"),
    ("block", "Blocked"),
]


class ClinicEmarPatientSafetyMixin(models.AbstractModel):
    _name = "clinic.emar.patient.safety.mixin"
    _description = "ClinicOne eMAR Patient Safety Helper"

    def _safety_frequency_multiplier(self, frequency):
        return {
            "once": 1,
            "qd": 1,
            "bid": 2,
            "tid": 3,
            "qid": 4,
            "q4h": 6,
            "q6h": 4,
            "q8h": 3,
            "q12h": 2,
            "weekly": 1 / 7.0,
            "prn": 1,
        }.get(frequency or "qd", 1)

    def _active_product_allergies(self, patient, product):
        if not patient or not product:
            return self.env["clinic.patient.allergy"]
        return self.env["clinic.patient.allergy"].search(
            [
                ("patient_id", "=", patient.id),
                ("status", "=", "active"),
                ("verification_status", "!=", "refuted"),
                "|",
                ("product_id", "=", product.id),
                ("allergen_id.product_id", "=", product.id),
            ]
        )

    def _evaluate_medication_safety(self, patient, lines):
        """Return (state, warnings, flags) for the medication lines."""
        warnings = []
        blocked = False
        allergy_flag = dose_flag = high_alert_flag = False

        for line in lines:
            product = line.product_id
            if not product:
                continue

            allergies = self._active_product_allergies(patient, product)
            if allergies:
                allergy_flag = True
                critical = allergies.filtered(
                    lambda a: a.is_critical
                    or a.severity in ("severe", "life_threatening")
                    or a.criticality == "high"
                )
                if critical:
                    blocked = True
                    warnings.append(
                        _("BLOCK: %s matches a critical active patient allergy.")
                        % product.display_name
                    )
                else:
                    warnings.append(
                        _("WARNING: %s matches an active patient allergy.")
                        % product.display_name
                    )

            profile = getattr(line, "profile_id", False)
            dose = float(getattr(line, "dose", 0.0) or 0.0)
            if profile:
                # Dose limits are expressed in the profile's clinical dose UoM.
                # They must never be compared as bare numbers when the line uses
                # another clinical unit.  Odoo 19 groups related UoMs through
                # relative_uom_id; convert only inside the same root hierarchy.
                profile_dose_uom = profile.dose_uom_id
                line_dose_uom = getattr(line, "dose_uom_id", False)
                if dose and (profile.max_single_dose or profile.max_daily_dose) and profile_dose_uom:
                    if not line_dose_uom:
                        dose_flag = True
                        blocked = True
                        warnings.append(
                            _("BLOCK: %s has dose limits but the medication line has no clinical dose UoM.")
                            % product.display_name
                        )
                    else:
                        profile_root = line._uom_root(profile_dose_uom)
                        line_root = line._uom_root(line_dose_uom)
                        if not profile_root or not line_root or profile_root != line_root:
                            dose_flag = True
                            blocked = True
                            warnings.append(
                                _("BLOCK: %s dose UoM is not comparable with the configured medication-profile dose UoM.")
                                % product.display_name
                            )
                        elif line_dose_uom != profile_dose_uom:
                            dose = line_dose_uom._compute_quantity(
                                dose, profile_dose_uom, round=False
                            )

                if profile.high_alert:
                    high_alert_flag = True
                    warnings.append(
                        _("HIGH-ALERT medication: %s requires heightened verification.")
                        % product.display_name
                    )
                if profile.max_single_dose and dose > profile.max_single_dose:
                    dose_flag = True
                    blocked = True
                    warnings.append(
                        _("BLOCK: %s dose %.2f exceeds the configured single-dose limit %.2f.")
                        % (product.display_name, dose, profile.max_single_dose)
                    )
                if profile.max_daily_dose and dose:
                    multiplier = self._safety_frequency_multiplier(
                        getattr(line, "frequency", False)
                    )
                    daily_dose = dose * multiplier
                    if daily_dose > profile.max_daily_dose:
                        dose_flag = True
                        blocked = True
                        warnings.append(
                            _("BLOCK: %s estimated daily dose %.2f exceeds the configured daily limit %.2f.")
                            % (product.display_name, daily_dose, profile.max_daily_dose)
                        )

        state = "block" if blocked else ("warning" if warnings else "pass")
        return state, warnings, {
            "allergy_flag": allergy_flag,
            "dose_flag": dose_flag,
            "high_alert_flag": high_alert_flag,
        }

    def _create_safety_alerts(self, patient, lines, source, warnings, state):
        if not patient or not warnings:
            return
        Alert = self.env["clinic.emar.alert"]
        severity = "critical" if state == "block" else "high"
        for line in lines.filtered(lambda ln: ln.product_id):
            Alert.upsert_alert(
                {
                    "company_id": source.company_id.id,
                    "patient_id": patient.id,
                    "doctor_id": (
                        source.doctor_id.id
                        if source._name == "clinic.emar.prescription" and source.doctor_id
                        else getattr(source, "clinic_doctor_id", False).id
                        if getattr(source, "clinic_doctor_id", False)
                        else False
                    ),
                    "product_id": line.product_id.id,
                    "prescription_id": source.id if source._name == "clinic.emar.prescription" else getattr(source, "prescription_id", False).id,
                    "order_id": source.id if source._name == "clinic.emar.order" else False,
                    "line_id": line.id,
                    "alert_type": "allergy" if self._active_product_allergies(patient, line.product_id) else "dose_limit",
                    "severity": severity,
                    "headline": _("Medication safety review: %s") % line.product_id.display_name,
                    "description": "\n".join(warnings),
                    "recommendation": _("Review the patient safety findings before clinical approval."),
                    "source_key": "patient_safety:%s:%s" % (source._name, source.id),
                }
            )


class ClinicEmarPrescriptionSafety(models.Model):
    _name = "clinic.emar.prescription"
    _inherit = ["clinic.emar.prescription", "clinic.emar.patient.safety.mixin"]

    safety_state = fields.Selection(
        SAFETY_SELECTION, default="pending", required=True, tracking=True, index=True
    )
    safety_checked = fields.Boolean(readonly=True, copy=False)
    safety_checked_on = fields.Datetime(readonly=True, copy=False)
    safety_checked_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    safety_warnings = fields.Text(readonly=True, copy=False)
    allergy_flag = fields.Boolean(readonly=True, copy=False)
    dose_flag = fields.Boolean(readonly=True, copy=False)
    high_alert_flag = fields.Boolean(readonly=True, copy=False)

    def action_run_patient_safety_checks(self):
        for rec in self:
            state, warnings, flags = rec._evaluate_medication_safety(rec.patient_id, rec.line_ids)
            rec.write(
                {
                    "safety_state": state,
                    "safety_checked": True,
                    "safety_checked_on": fields.Datetime.now(),
                    "safety_checked_by_id": self.env.user.id,
                    "safety_warnings": "\n".join(warnings),
                    **flags,
                }
            )
            rec._create_safety_alerts(rec.patient_id, rec.line_ids, rec, warnings, state)
        return True

    def _run_prescription_safety_gate(self):
        for rec in self:
            rec.action_run_patient_safety_checks()
            if rec.safety_state == "block":
                raise UserError(
                    _("Prescription %s is blocked by medication safety checks. Review the Safety tab and alerts.")
                    % rec.display_name
                )
        return True

    def write(self, vals):
        clinical_keys = {
            "patient_id", "doctor_id", "line_ids", "diagnosis", "contraindications"
        }
        if clinical_keys.intersection(vals) and not self.env.context.get("emar_skip_safety_reset"):
            vals = dict(vals, safety_state="pending", safety_checked=False)
        return super().write(vals)


class ClinicEmarOrderSafety(models.Model):
    _name = "clinic.emar.order"
    _inherit = ["clinic.emar.order", "clinic.emar.patient.safety.mixin"]

    safety_state = fields.Selection(
        SAFETY_SELECTION, default="pending", required=True, tracking=True, index=True
    )
    safety_checked = fields.Boolean(readonly=True, copy=False)
    safety_checked_on = fields.Datetime(readonly=True, copy=False)
    safety_checked_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    safety_warnings = fields.Text(readonly=True, copy=False)
    allergy_flag = fields.Boolean(readonly=True, copy=False)
    dose_flag = fields.Boolean(readonly=True, copy=False)
    high_alert_flag = fields.Boolean(readonly=True, copy=False)

    def action_run_patient_safety_checks(self):
        for rec in self:
            patient = rec.clinic_patient_id
            state, warnings, flags = rec._evaluate_medication_safety(patient, rec.line_ids)
            rec.with_context(emar_skip_safety_reset=True).write(
                {
                    "safety_state": state,
                    "safety_checked": True,
                    "safety_checked_on": fields.Datetime.now(),
                    "safety_checked_by_id": self.env.user.id,
                    "safety_warnings": "\n".join(warnings),
                    **flags,
                }
            )
            rec._create_safety_alerts(patient, rec.line_ids, rec, warnings, state)
        return True

    def _run_order_safety_gate(self):
        for rec in self:
            rec.action_run_patient_safety_checks()
            if rec.safety_state == "block":
                raise UserError(
                    _("Order %s is blocked by medication safety checks. Review the Safety tab and alerts.")
                    % rec.display_name
                )
        return True

    def write(self, vals):
        clinical_keys = {
            "clinic_patient_id", "patient_id", "clinic_doctor_id", "line_ids",
            "contraindications"
        }
        if clinical_keys.intersection(vals) and not self.env.context.get("emar_skip_safety_reset"):
            vals = dict(vals, safety_state="pending", safety_checked=False)
        return super().write(vals)


class ClinicEmarAdministrationSafety(models.Model):
    _inherit = "clinic.emar.administration"

    verification_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("passed", "Verified"),
            ("warning", "Verified with Warning"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    patient_scan_code = fields.Char(copy=False)
    product_scan_code = fields.Char(copy=False)
    verified_on = fields.Datetime(readonly=True, copy=False)
    verified_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    verification_note = fields.Text(readonly=True, copy=False)
    refused = fields.Boolean(readonly=True, copy=False, tracking=True)
    refusal_reason = fields.Text(readonly=True, copy=False)
    skipped = fields.Boolean(readonly=True, copy=False, tracking=True)
    skip_reason = fields.Text(readonly=True, copy=False)
    missed = fields.Boolean(readonly=True, copy=False, tracking=True)
    adverse_event = fields.Boolean(tracking=True)
    adverse_event_note = fields.Text()
    vitals_intake_id = fields.Many2one("clinic.vitals.intake", string="Administration Vitals")

    def _profile(self):
        self.ensure_one()
        return self.line_id.profile_id if self.line_id and self.line_id.profile_id else self.env["clinic.emar.medication.profile"].search(
            [("product_id", "=", self.product_id.id), ("company_id", "=", self.company_id.id), ("active", "=", True)],
            limit=1,
        )

    def action_verify_administration(self):
        for rec in self:
            problems = []
            warnings = []
            company = rec.company_id
            profile = rec._profile()
            patient = rec.patient_id

            require_patient_scan = bool(
                company.emar_require_patient_scan
                or (profile and profile.requires_patient_scan)
            )
            require_product_scan = bool(
                company.emar_require_product_scan
                or (profile and profile.requires_product_scan)
            )
            require_double = bool(
                profile
                and profile.high_alert
                and (company.emar_require_double_check_high_alert or profile.requires_double_check)
            )

            patient_code = getattr(patient, "emar_barcode", False) or getattr(patient, "patient_code", False)
            if require_patient_scan:
                if not patient_code:
                    problems.append(_("Patient has no eMAR barcode/patient code configured."))
                elif rec.patient_scan_code != patient_code:
                    problems.append(_("Patient barcode verification failed."))

            product_code = rec.product_id.barcode if rec.product_id else False
            if require_product_scan:
                if not product_code:
                    problems.append(_("Medication product has no barcode configured."))
                elif rec.product_scan_code != product_code:
                    problems.append(_("Medication barcode verification failed."))

            if profile and profile.requires_lot and not rec.lot_id:
                problems.append(_("Medication profile requires a Lot/Serial number."))
            if rec.lot_id and rec.lot_expired:
                problems.append(_("Selected Lot/Serial is expired."))

            if require_double:
                if not rec.double_check_user_id:
                    problems.append(_("Independent double-check is required for this high-alert medication."))
                elif rec.double_check_user_id == self.env.user:
                    problems.append(_("Double-check must be performed by a different user."))

            if patient and rec.product_id:
                allergies = self.env["clinic.patient.allergy"].search(
                    [
                        ("patient_id", "=", patient.id),
                        ("status", "=", "active"),
                        ("verification_status", "!=", "refuted"),
                        "|",
                        ("product_id", "=", rec.product_id.id),
                        ("allergen_id.product_id", "=", rec.product_id.id),
                    ]
                )
                if allergies.filtered(lambda a: a.is_critical):
                    problems.append(_("Critical active allergy matches the medication being administered."))
                elif allergies:
                    warnings.append(_("Active patient allergy matches this medication; clinical review required."))

            if problems:
                rec.write(
                    {
                        "verification_state": "failed",
                        "verified_on": fields.Datetime.now(),
                        "verified_by_id": self.env.user.id,
                        "verification_note": "\n".join(problems + warnings),
                    }
                )
                raise ValidationError("\n".join(problems))

            rec.write(
                {
                    "verification_state": "warning" if warnings else "passed",
                    "verified_on": fields.Datetime.now(),
                    "verified_by_id": self.env.user.id,
                    "verification_note": "\n".join(warnings),
                }
            )
        return True

    def _run_administration_safety_gate(self):
        for rec in self:
            rec.action_verify_administration()
            if rec.verification_state == "failed":
                raise UserError(_("Administration verification failed."))
        return True

    def action_refuse(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("A completed administration cannot be marked refused."))
            if not rec.refusal_reason:
                raise UserError(_("Enter the refusal reason before marking the dose refused."))
            rec._emar_guarded_write({"refused": True, "state": "cancelled"})
            if rec.schedule_id and rec.schedule_id.state != "administered":
                rec.schedule_id._emar_guarded_write({"state": "cancelled"})
        return True

    def action_skip(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("A completed administration cannot be skipped."))
            if not rec.skip_reason:
                raise UserError(_("Enter the skip reason before skipping the dose."))
            rec._emar_guarded_write({"skipped": True, "state": "cancelled"})
        return True

    def action_mark_missed(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("A completed administration cannot be marked missed."))
            rec._emar_guarded_write({"missed": True, "state": "cancelled"})
            if rec.schedule_id and rec.schedule_id.state not in ("administered", "cancelled"):
                rec.schedule_id._emar_guarded_write({"state": "missed"})
            self.env["clinic.emar.alert"].raise_time_window(
                rec.schedule_id, kind="missed_dose"
            ) if rec.schedule_id else None
        return True

