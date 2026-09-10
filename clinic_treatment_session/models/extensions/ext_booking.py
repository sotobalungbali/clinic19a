
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BookingBooking(models.Model):
    """Historical Booking → Treatment Session bridge."""

    _inherit = "booking.booking"

    treatment_session_ids = fields.One2many("clinic.treatment.session", "booking_id", copy=False)
    treatment_session_count = fields.Integer(compute="_compute_treatment_session_count")
    has_treatment_sessions = fields.Boolean(compute="_compute_treatment_session_count")
    auto_session_policy = fields.Selection([
        ("manual", "Manual - Created On Demand"),
        ("auto_on_confirm", "Automatically When Booking Is Confirmed"),
        ("auto_on_checkin", "Automatically When Patient Checks In"),
    ], default="manual")

    @api.depends("treatment_session_ids.state")
    def _compute_treatment_session_count(self):
        for rec in self:
            rec.treatment_session_count = len(rec.treatment_session_ids)
            rec.has_treatment_sessions = bool(rec.treatment_session_count)

    def _get_booking_patient_partner(self):
        self.ensure_one()
        patient = self.patient_id if "patient_id" in self._fields else False
        if not patient:
            return self.env["res.partner"].browse()
        if patient._name == "res.partner":
            return patient
        if patient._name == "clinic.patient" and "partner_id" in patient._fields:
            return patient.partner_id
        return self.env["res.partner"].browse()

    def _get_booking_employee_doctor(self):
        self.ensure_one()
        Employee = self.env["hr.employee"]
        for fname in ("clinic_doctor_id", "employee_id"):
            if fname in self._fields and self[fname] and self[fname]._name == "hr.employee":
                return self[fname]
        return Employee.browse()

    def _prepare_session_vals(self, treatment=False, start_dt=False, end_dt=False, room=False):
        self.ensure_one()
        patient = self._get_booking_patient_partner()
        employee = self._get_booking_employee_doctor()
        room = room or (self.room_id if "room_id" in self._fields else False)
        start = start_dt or (self.start_datetime if "start_datetime" in self._fields else False)
        end = end_dt or (self.end_datetime if "end_datetime" in self._fields else False)
        if not patient:
            raise UserError(_("Booking has no patient/contact for Treatment Session."))
        if not start or not end:
            raise UserError(_("Booking start/end datetime is required before generating a session."))
        vals = {
            "company_id": self.company_id.id,
            "patient_id": patient.id,
            "clinic_doctor_id": employee.id or False,
            "treatment_id": treatment.id if treatment else False,
            "booking_id": self.id,
            "room_id": room.id if room else False,
            "start_datetime": start,
            "end_datetime": end,
            "duration_planned": max((fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)).total_seconds() / 60.0, 0.0),
        }
        vals.update(self._prepare_session_vals_extra(treatment=treatment) or {})
        return vals

    def _prepare_session_vals_extra(self, treatment=False):
        return {}

    def _post_generate_treatment_sessions(self, sessions):
        return True

    def _get_booking_treatments(self):
        self.ensure_one()
        Treatment = self.env["clinic.treatment"]
        for fname in ("treatment_ids", "service_ids"):
            if fname in self._fields and self[fname] and self[fname]._name == "clinic.treatment":
                return self[fname]
        for fname in ("treatment_id", "service_id"):
            if fname in self._fields and self[fname] and self[fname]._name == "clinic.treatment":
                return self[fname]
        return Treatment.browse()

    def generate_treatment_sessions(self):
        """Create Treatment Sessions through the owner business contract.

        Business generation is intentionally separated from UI navigation
        metadata so clinical actors need only business-model permissions.
        """
        Session = self.env["clinic.treatment.session"]
        created = Session.browse()
        for booking in self:
            if booking.treatment_session_ids and not self.env.context.get("allow_duplicate_sessions"):
                raise UserError(_("Treatment Sessions already exist for this Booking."))
            treatments = booking._get_booking_treatments()
            if treatments:
                for treatment in treatments:
                    created |= Session.create(booking._prepare_session_vals(treatment=treatment))
            else:
                created |= Session.create(booking._prepare_session_vals())
        self._post_generate_treatment_sessions(created)
        return created

    def action_generate_treatment_sessions(self):
        created = self.generate_treatment_sessions()
        action = self.env.ref("clinic_treatment_session.action_clinic_treatment_session").read()[0]
        action["domain"] = [("id", "in", created.ids)]
        if len(created) == 1:
            action.update({"view_mode": "form", "res_id": created.id})
        return action

    def action_view_treatment_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_treatment_session.action_clinic_treatment_session").read()[0]
        action["domain"] = [("booking_id", "=", self.id)]
        return action

    def action_generate_and_view_treatment_sessions(self):
        return self.action_generate_treatment_sessions()
