




from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDemoControlCenter(TransactionCase):

    def setUp(self):
        super().setUp()
        self.run = self.env["clinic.demo.run"].create({
            "profile": "compact",
            "anchor_date": fields.Date.today(),
            "safe_mode": True,
        })

    def test_navigation_actions_are_callable(self):
        for method_name, model_name in [
            ("action_open_references", "clinic.demo.reference"),
            ("action_open_checkpoints", "clinic.demo.checkpoint"),
            ("action_open_logs", "clinic.demo.log"),
            ("action_open_validation_results", "clinic.demo.validation.result"),
        ]:
            action = getattr(self.run, method_name)()
            self.assertEqual(action["type"], "ir.actions.act_window")
            self.assertEqual(action["res_model"], model_name)

    def test_framework_generation_button_is_safe_before_domain_generators(self):
        # The user running Odoo tests may not belong to the Demo Operator group,
        # so exercise the execution engine directly rather than weakening backend security.
        from ..services.execution_engine import DemoExecutionEngine

        action = DemoExecutionEngine(self.env).request_full_generation(self.run)
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")

    def test_registered_prompt04_scenario_count(self):
        from ..services.scenario_registry import ScenarioRegistry

        self.assertEqual(len(ScenarioRegistry.all()), 34)
























