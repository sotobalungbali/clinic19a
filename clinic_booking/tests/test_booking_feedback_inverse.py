
# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestBookingFeedbackInverse(TransactionCase):

    def test_feedback_inverse_is_effective_on_booking(self):
        booking = self.env["booking.booking"]
        self.assertIn("feedback_link_ids", booking._fields)
        self.assertTrue(hasattr(booking, "action_new_feedback_link"))

        feedback = self.env["booking.feedback.link"]
        self.assertEqual(feedback._fields["booking_id"].comodel_name, "booking.booking")


