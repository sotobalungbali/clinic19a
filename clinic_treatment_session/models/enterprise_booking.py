# -*- coding: utf-8 -*-

from odoo import fields, models


class BookingBookingTreatmentSessionEnterprise(models.Model):
    """Correct Booking → Session canonical Doctor/Patient mapping."""

    _inherit = "booking.booking"

    def _get_booking_employee_doctor(self):
        """Resolve the historical hr.employee doctor without mixing model IDs."""
        self.ensure_one()
        doctor = self.doctor_id
        if not doctor:
            return self.env["hr.employee"].browse()

        Employee = self.env["hr.employee"]
        if doctor.user_id:
            employee = Employee.search(
                [
                    ("user_id", "=", doctor.user_id.id),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if employee:
                return employee

        if doctor.partner_id:
            employee = Employee.search(
                [
                    ("work_contact_id", "=", doctor.partner_id.id),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if employee:
                return employee

        return Employee.browse()

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
        vals["doctor_id"] = self.doctor_id.id or False

        if self.patient_id:
            vals["patient_id"] = self.patient_id.id
            if (
                "branch_id" in self.patient_id._fields
                and self.patient_id.branch_id
            ):
                vals["branch_id"] = self.patient_id.branch_id.id

        if "referral_id" in self._fields and self.referral_id:
            vals["referral_id"] = self.referral_id.id

        if (
            "package_allocation_id" in self._fields
            and self.package_allocation_id
        ):
            vals["package_allocation_id"] = (
                self.package_allocation_id.id
            )

        if (
            "package_allocation_line_id" in self._fields
            and self.package_allocation_line_id
        ):
            vals["package_allocation_line_id"] = (
                self.package_allocation_line_id.id
            )

        return vals

    def action_confirm(self):
        result = super().action_confirm()
        for booking in self:
            if (
                booking.auto_session_policy == "on_confirm"
                and not booking.treatment_session_ids
            ):
                booking.action_generate_treatment_sessions()
        return result

    def action_start(self):
        result = super().action_start()
        for booking in self:
            if (
                booking.auto_session_policy == "on_checkin"
                and not booking.treatment_session_ids
            ):
                booking.action_generate_treatment_sessions()
        return result
