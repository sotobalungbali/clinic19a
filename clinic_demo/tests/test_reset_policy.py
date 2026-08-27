from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.constants import (
    RESET_DELETE_SAFE,
    RESET_FRESH_DB_ONLY,
    RESET_RETAIN_IMMUTABLE,
)
from ..services.reference_service import DemoReferenceService
from ..services.reset_policy_registry import ResetPolicyRegistry
from ..services.reset_service import DemoResetService


@tagged("post_install", "-at_install")
class TestDemoResetFoundation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
        })

    def test_source_locked_policies(self):
        registry = ResetPolicyRegistry()
        self.assertEqual(
            registry.decision_for_values(
                "clinic.referral", {"state": "converted"}
            ).policy,
            RESET_FRESH_DB_ONLY,
        )
        self.assertEqual(
            registry.decision_for_values(
                "clinic.treatment.session", {"state": "done"}
            ).policy,
            RESET_FRESH_DB_ONLY,
        )
        self.assertEqual(
            registry.decision_for_values(
                "clinic.consent.form", {"state": "signed"}
            ).policy,
            RESET_RETAIN_IMMUTABLE,
        )

    def test_unknown_live_model_policy_blocks_destructive_reset(self):
        from odoo.exceptions import ValidationError

        partner = self.env["res.partner"].create({"name": "Synthetic Reset Record"})
        reference = DemoReferenceService(self.env).bind(
            self.run,
            "DEMO-TEST-RESET-CREATED",
            partner,
            "test.reset",
            reset_policy=RESET_DELETE_SAFE,
        )
        with self.assertRaises(ValidationError):
            DemoResetService(self.env).reset_reference(reference)
        self.assertTrue(partner.exists())
        self.assertEqual(reference.record_status, "bound")

    def test_reused_record_is_retained(self):
        partner = self.env["res.partner"].create({"name": "Existing Reused Record"})
        reference = DemoReferenceService(self.env).bind_reused(
            self.run,
            "DEMO-TEST-RESET-REUSED",
            partner,
            "test.reset",
            reset_policy=RESET_DELETE_SAFE,
        )
        result = DemoResetService(self.env).reset_reference(reference)
        self.assertEqual(result["status"], "retained_reused")
        self.assertTrue(partner.exists())
        self.assertEqual(reference.record_status, "reset_retained")
