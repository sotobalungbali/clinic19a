




from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.seed_service import DeterministicSeedService


@tagged("post_install", "-at_install")
class TestDeterministicSeedService(TransactionCase):

    def test_namespace_is_order_independent(self):
        service = DeterministicSeedService("247001")
        first = service.token("patient:DEMO-PAT-001")
        service.token("unrelated:inserted-later")
        second = service.token("patient:DEMO-PAT-001")
        self.assertEqual(first, second)

    def test_different_namespace_changes_value(self):
        service = DeterministicSeedService("247001")
        self.assertNotEqual(
            service.token("patient:DEMO-PAT-001"),
            service.token("patient:DEMO-PAT-002"),
        )
























