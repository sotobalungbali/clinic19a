# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase


class TestClinicAppointmentBridgeFields(TransactionCase):
    """Regression for clinic_booking soft coupling to clinic_doctor appointment fields."""

    def test_overlap_bridge_uses_canonical_appointment_window_fields(self):
        Appointment = self.env["clinic.appointment"]
        self.assertIn("start", Appointment._fields)
        self.assertIn("end", Appointment._fields)
        self.assertNotIn("start_datetime", Appointment._fields)
        self.assertNotIn("end_datetime", Appointment._fields)

        source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "models" / "clinic_doctor_inherit.py"
        ).read_text(encoding="utf-8")
        self.assertIn('start_field = "start" if "start" in app_fields', source)
        self.assertIn('end_field = "end" if "end" in app_fields', source)
        self.assertNotIn('("start_datetime", "<", fields.Datetime.to_string(end))', source)

    def test_create_bridge_maps_booking_window_to_canonical_start_end(self):
        source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "models" / "booking_booking.py"
        ).read_text(encoding="utf-8")
        self.assertIn('if "start" in app_fields:', source)
        self.assertIn('vals["start"] = rec.start_datetime', source)
        self.assertIn('if "end" in app_fields:', source)
        self.assertIn('vals["end"] = rec.end_datetime', source)
        self.assertIn('if "partner_id" in app_fields:', source)
