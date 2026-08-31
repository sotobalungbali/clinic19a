
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.constants import RESET_DEACTIVATE
from ..services.execution_engine import DemoExecutionEngine
from ..services.generator_registry import GENERATOR_REGISTRY
from ..services.reset_policy_registry import ResetPolicyRegistry


@tagged("post_install", "-at_install")
class TestPrompt08FoundationRegistry(TransactionCase):

    def test_registry_has_first_two_real_generators(self):
        GENERATOR_REGISTRY.validate()
        keys = {generator.key for generator in GENERATOR_REGISTRY.all()}
        self.assertIn("foundation.native", keys)
        self.assertIn("foundation.organization", keys)

    def test_organization_depends_on_native_foundation(self):
        organization = GENERATOR_REGISTRY.get("foundation.organization")
        self.assertEqual(organization.depends_on, ("foundation.native",))
        self.assertEqual(
            organization.required_groups,
            ("clinic_branch.group_branch_manager",),
        )

    def test_control_center_reports_partial_registry(self):
        generators = DemoExecutionEngine(self.env)._registered_generators()
        self.assertGreaterEqual(len(generators), 2)
        self.assertLess(len(generators), 35)

    def test_foundation_reset_policy_is_deactivate(self):
        registry = ResetPolicyRegistry()
        self.assertEqual(
            registry.decision_for_values("clinic.branch", {}).policy,
            RESET_DEACTIVATE,
        )
        self.assertEqual(
            registry.decision_for_values("clinic.branch.location", {}).policy,
            RESET_DEACTIVATE,
        )



