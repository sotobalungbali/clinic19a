




from odoo.exceptions import UserError
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.safe_mode_service import DemoSafeModeService


@tagged("post_install", "-at_install")
class TestDemoSafeMode(TransactionCase):

    def test_safe_mode_blocks_external_effect(self):
        run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
            "safe_mode": True,
        })
        service = DemoSafeModeService(run)
        with self.assertRaises(UserError):
            service.assert_allowed("webhook", explicit_opt_in=True)

    def test_disabled_safe_mode_still_requires_explicit_opt_in(self):
        run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
            "safe_mode": False,
        })
        service = DemoSafeModeService(run)
        with self.assertRaises(UserError):
            service.assert_allowed("external_api_mutation")
        self.assertTrue(
            service.assert_allowed(
                "external_api_mutation",
                explicit_opt_in=True,
            )
        )

    def test_synthetic_email_is_non_routable(self):
        email = DemoSafeModeService.synthetic_email("DEMO-PAT-001")
        self.assertTrue(email.endswith("@clinicone-demo.invalid"))
























