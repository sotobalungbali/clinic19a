
# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestBookingChannelCreateMulti(TransactionCase):
    """Regression for Odoo 19 model_create_multi on booking.channel."""

    def test_multi_create_accepts_vals_list(self):
        channels = self.env["booking.channel"].create([
            {
                "name": "Create-Multi Regression Walk-in",
                "code": "regression-create-multi-walkin",
                "channel_type": "walkin",
                "company_id": self.env.company.id,
            },
            {
                "name": "Create-Multi Regression Phone",
                "code": "regression-create-multi-phone",
                "channel_type": "phone",
                "company_id": self.env.company.id,
            },
        ])
        self.assertEqual(len(channels), 2)
        self.assertEqual(set(channels.mapped("channel_type")), {"walkin", "phone"})
