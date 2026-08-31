
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.constants import RESET_DELETE_SAFE
from ..services.reference_service import DemoReferenceService


@tagged("post_install", "-at_install")
class TestDemoReferenceIdempotency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
            "deterministic_seed": "1001",
        })
        self.service = DemoReferenceService(self.env)

    def _create_partner(self, suffix):
        return self.env["res.partner"].create({
            "name": f"ClinicOne Synthetic {suffix}",
            "email": f"synthetic-{suffix.lower()}@clinicone-demo.invalid",
        })

    def test_create_then_reuse_same_demo_key(self):
        calls = {"create": 0}

        def creator():
            calls["create"] += 1
            return self._create_partner("A")

        first, first_ref, first_status = self.service.ensure_record(
            self.run,
            "DEMO-TEST-PARTNER-A",
            "res.partner",
            "test.identity",
            creator,
            reset_policy=RESET_DELETE_SAFE,
        )
        second, second_ref, second_status = self.service.ensure_record(
            self.run,
            "DEMO-TEST-PARTNER-A",
            "res.partner",
            "test.identity",
            creator,
            reset_policy=RESET_DELETE_SAFE,
        )

        self.assertEqual(calls["create"], 1)
        self.assertEqual(first, second)
        self.assertEqual(first_ref, second_ref)
        self.assertEqual(first_status, "created")
        self.assertEqual(second_status, "reused")

    def test_missing_record_is_recreated_and_rebound(self):
        partner, reference, _status = self.service.ensure_record(
            self.run,
            "DEMO-TEST-PARTNER-B",
            "res.partner",
            "test.identity",
            lambda: self._create_partner("B1"),
            reset_policy=RESET_DELETE_SAFE,
        )
        old_id = partner.id
        partner.unlink()

        replacement, rebound, status = self.service.ensure_record(
            self.run,
            "DEMO-TEST-PARTNER-B",
            "res.partner",
            "test.identity",
            lambda: self._create_partner("B2"),
            reset_policy=RESET_DELETE_SAFE,
        )
        self.assertNotEqual(old_id, replacement.id)
        self.assertEqual(reference, rebound)
        self.assertEqual(rebound.res_id, replacement.id)
        self.assertEqual(rebound.record_status, "bound")
        self.assertEqual(status, "created")

    def test_reused_record_is_explicitly_marked_non_owned(self):
        partner = self._create_partner("REUSED")
        reference = self.service.bind_reused(
            self.run,
            "DEMO-TEST-REUSED",
            partner,
            "test.identity",
            reset_policy=RESET_DELETE_SAFE,
        )
        self.assertEqual(reference.ownership_kind, "reused")



