from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.checkpoint_service import DemoCheckpointService


@tagged("post_install", "-at_install")
class TestCheckpointService(TransactionCase):

    def test_ensure_checkpoint_is_idempotent(self):
        run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
        })
        service = DemoCheckpointService(self.env)
        first = service.ensure(
            run,
            "08.foundation.organization",
            "08_foundation",
            "foundation.organization",
            110,
            "SCN-FOUNDATION-01",
        )
        second = service.ensure(
            run,
            "08.foundation.organization",
            "08_foundation",
            "foundation.organization",
            110,
            "SCN-FOUNDATION-01",
        )
        self.assertEqual(first, second)
        service.start(first)
        self.assertEqual(first.state, "running")
        service.complete(first, {"created": 2, "reused": 1})
        self.assertEqual(first.state, "done")
        self.assertEqual(first.created_count, 2)
        self.assertEqual(first.reused_count, 1)
        self.assertEqual(run.last_successful_checkpoint_key, first.checkpoint_key)
