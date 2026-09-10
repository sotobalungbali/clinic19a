# -*- coding: utf-8 -*-
from pathlib import Path
from odoo.tests.common import TransactionCase

class TestBookingAppointmentIdentityBridge(TransactionCase):
    def test_runtime_comodel_contract(self):
        Booking = self.env["booking.booking"]
        Appointment = self.env["clinic.appointment"]
        self.assertEqual(Booking._fields["patient_id"].comodel_name, "res.partner")
        self.assertEqual(Appointment._fields["partner_id"].comodel_name, "res.partner")
        self.assertEqual(Appointment._fields["patient_id"].comodel_name, "clinic.patient")

    def test_bridge_does_not_cross_copy_patient_ids(self):
        source = (
            Path(__file__).resolve().parents[1] / "models" / "booking_booking.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("rec.patient_id.partner_id", source)
        self.assertIn('vals["partner_id"] = patient_partner.id', source)
        self.assertIn('patient_comodel == "clinic.patient"', source)
        self.assertIn('("partner_id", "=", patient_partner.id)', source)
