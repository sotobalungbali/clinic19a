

from datetime import datetime

import pytz
from odoo.tests.common import TransactionCase


class TestBookingTimezoneSchedule(TransactionCase):
    """Owner-level regression for local weekly schedule vs UTC Datetime storage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.user = cls.env.user
        cls.user.tz = "Asia/Makassar"

    def _utc(self, y, m, d, hour, minute=0):
        local = pytz.timezone("Asia/Makassar").localize(datetime(y, m, d, hour, minute))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def test_room_weekly_schedule_uses_context_timezone(self):
        room = self.env["booking.room"].create({
            "name": "TZ Regression Room",
            "code": "TZ-REG-ROOM",
            "company_id": self.company.id,
            "capacity": 1,
        })
        self.env["booking.room.schedule"].create({
            "room_id": room.id, "weekday": "0", "hour_from": 8.0, "hour_to": 18.0,
        })
        # Monday 09:00-10:00 WITA is 01:00-02:00 UTC. Raw-UTC comparison would fail.
        self.assertTrue(room.with_context(tz="Asia/Makassar")._fits_weekly_schedule(
            self._utc(2026, 8, 31, 9), self._utc(2026, 8, 31, 10)
        ))
        self.assertFalse(room.with_context(tz="Asia/Makassar")._fits_weekly_schedule(
            self._utc(2026, 8, 31, 7), self._utc(2026, 8, 31, 8)
        ))

    def test_resource_weekly_schedule_uses_context_timezone(self):
        resource = self.env["booking.resource"].create({
            "name": "TZ Regression Resource",
            "code": "TZ-REG-RES",
            "company_id": self.company.id,
            "capacity_concurrent": 1,
        })
        self.env["booking.resource.schedule"].create({
            "resource_id": resource.id, "weekday": "0", "hour_from": 8.0, "hour_to": 18.0,
        })
        self.assertTrue(resource.with_context(tz="Asia/Makassar")._fits_weekly_schedule(
            self._utc(2026, 8, 31, 9), self._utc(2026, 8, 31, 10)
        ))
