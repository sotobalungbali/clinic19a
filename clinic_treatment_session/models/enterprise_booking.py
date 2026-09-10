
# -*- coding: utf-8 -*-
from odoo import models


class BookingBookingTreatmentSessionEnterprise(models.Model):
    """Correct Booking → Session canonical Doctor/Patient mapping."""

    _inherit = "booking.booking"

    def _get_booking_employee_doctor(self):
        """Resolve the historical hr.employee doctor without mixing model IDs."""
        self.ensure_one()
        doctor = self.doctor_id if "doctor_id" in self._fields else False
        if not doctor:
            return super()._get_booking_employee_doctor()

        Employee = self.env["hr.employee"]
        if doctor._name == "hr.employee":
            return doctor

        if doctor._name == "clinic.doctor":
            if "user_id" in doctor._fields and doctor.user_id:
                employee = Employee.search([
                    ("user_id", "=", doctor.user_id.id),
                    ("company_id", "=", self.company_id.id),
                ], limit=1)
                if employee:
                    return employee

            if "partner_id" in doctor._fields and doctor.partner_id:
                employee = Employee.search([
                    ("work_contact_id", "=", doctor.partner_id.id),
                    ("company_id", "=", self.company_id.id),
                ], limit=1)
                if employee:
                    return employee

        return super()._get_booking_employee_doctor()

    def _prepare_session_vals(
        self,
        treatment=False,
        start_dt=False,
        end_dt=False,
        room=False,
    ):
        """Preserve legacy payload and repair cross-model Doctor assignment."""
        vals = super()._prepare_session_vals(
            treatment=treatment,
            start_dt=start_dt,
            end_dt=end_dt,
            room=room,
        )

        employee = self._get_booking_employee_doctor()
        vals["clinic_doctor_id"] = employee.id or False

        if "doctor_id" in self._fields and self.doctor_id:
            if self.doctor_id._name == "clinic.doctor":
                vals["doctor_id"] = self.doctor_id.id or False

        if "patient_id" in self._fields and self.patient_id:
            patient = self.patient_id
            if patient._name == "res.partner":
                vals["patient_id"] = patient.id
            elif patient._name == "clinic.patient":
                if "partner_id" in patient._fields and patient.partner_id:
                    vals["patient_id"] = patient.partner_id.id
                vals["clinic_patient_id"] = patient.id

            if "branch_id" in patient._fields and patient.branch_id:
                vals["branch_id"] = patient.branch_id.id

        if "referral_id" in self._fields and self.referral_id:
            vals["referral_id"] = self.referral_id.id

        if "package_allocation_id" in self._fields and self.package_allocation_id:
            vals["package_allocation_id"] = self.package_allocation_id.id

        if (
            "package_allocation_line_id" in self._fields
            and self.package_allocation_line_id
        ):
            vals["package_allocation_line_id"] = self.package_allocation_line_id.id

        return vals
