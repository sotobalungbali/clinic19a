




from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.constants import RESET_DELETE_SAFE
from ..services.reference_service import DemoReferenceService


@tagged("post_install", "-at_install")
class TestDemoResetPreview(TransactionCase):

    def test_reset_preview_never_deletes_reused_record(self):
        run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
        })
        partner = self.env["res.partner"].create({
            "name": "ClinicOne Existing Reused Partner",
        })
        reference = DemoReferenceService(self.env).bind_reused(
            run,
            "DEMO-RESET-PREVIEW-REUSED",
            partner,
            "test.reset.preview",
            reset_policy=RESET_DELETE_SAFE,
        )

        from ..services.reset_service import DemoResetService

        preview = DemoResetService(self.env).preview_run(run)
        self.assertEqual(preview["retain"], 1)
        self.assertTrue(partner.exists())
        self.assertEqual(reference.ownership_kind, "reused")
























