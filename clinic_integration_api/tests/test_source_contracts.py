from pathlib import Path
import ast
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class TestClinicIntegrationApiSourceContracts(unittest.TestCase):
    def test_manifest_version(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        self.assertEqual(manifest["version"], "19.0.1.0.0")

    def test_future_addons_are_not_direct_dependencies(self):
        depends = ast.literal_eval((ROOT / "__manifest__.py").read_text())["depends"]
        self.assertNotIn("clinic_audit", depends)
        self.assertNotIn("clinic_analytics", depends)

    def test_no_legacy_sql_constraints(self):
        constraint_count = 0
        for path in ROOT.rglob("*.py"):
            source = path.read_text()
            tree = ast.parse(source)
            constraint_count += source.count("models.Constraint(")
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        self.assertNotEqual(target.id, "_sql_constraints", path.as_posix())
        self.assertGreaterEqual(constraint_count, 5)

    def test_bearer_user_policy_is_unambiguous(self):
        source = (ROOT / "models/client.py").read_text()
        self.assertIn("UNIQUE(user_id)", source)
        service = (ROOT / "models/api_service.py").read_text()
        self.assertIn("limit=1", service)

    def test_event_branch_uses_resource_contract(self):
        source = (ROOT / "models/api_service.py").read_text()
        self.assertIn("def _event_branch", source)
        self.assertIn("spec=spec", source)

    def test_delivery_scope_has_backend_constraint(self):
        source = (ROOT / "models/delivery.py").read_text()
        self.assertIn('@api.constrains("event_id", "subscription_id")', source)

    def test_all_python_parses(self):
        for path in ROOT.rglob("*.py"):
            ast.parse(path.read_text())

    def test_all_xml_parses(self):
        for path in ROOT.rglob("*.xml"):
            ET.parse(path)

    def test_bearer_routes_are_explicit(self):
        source = (ROOT / "controllers/api.py").read_text()
        self.assertIn('auth="bearer"', source)
        self.assertIn("_require_explicit_bearer", source)

    def test_no_generic_rpc_surface(self):
        source = (ROOT / "models/api_service.py").read_text()
        self.assertNotIn("self.env[resource]", source)
        self.assertNotIn("self.env[model_name]", source)
        self.assertIn("RESOURCE_SPECS", source)

    def test_mutation_is_bounded(self):
        source = (ROOT / "models/api_service.py").read_text()
        self.assertIn('"patients"', source)
        self.assertIn('"bookings"', source)
        self.assertIn("_validated_mutation_values", source)

    def test_idempotency_uses_transaction_lock(self):
        source = (ROOT / "models/idempotency.py").read_text()
        self.assertIn("pg_advisory_xact_lock", source)
        self.assertIn("UNIQUE(client_id, idem_key)", source)

    def test_provider_transport_blocks_redirects(self):
        source = (ROOT / "models/provider.py").read_text()
        self.assertIn("class _NoRedirect", source)
        self.assertIn("ipaddress.ip_address", source)

    def test_business_bridges_exist(self):
        source = (ROOT / "models/bridges.py").read_text()
        self.assertIn('_inherit = "clinic.marketing.message"', source)
        self.assertIn('_inherit = "clinic.telemedicine.session"', source)
        self.assertIn('_inherit = "clinic.billing.gateway.tx"', source)

    def test_search_views_cover_persistent_models(self):
        source = "\n".join(p.read_text() for p in (ROOT / "views").glob("*.xml"))
        for model in ("clinic.api.client", "clinic.api.provider", "clinic.api.event", "clinic.api.webhook.subscription", "clinic.api.webhook.delivery", "clinic.api.scope", "clinic.api.event.type", "clinic.api.request.log", "clinic.api.idempotency"):
            self.assertIn(model, source)
            self.assertIn("<search", source)

    def test_operator_cannot_write_delivery_evidence(self):
        rows = (ROOT / "security/ir.model.access.csv").read_text()
        self.assertIn("access_api_delivery_operator,clinic.api.webhook.delivery operator,model_clinic_api_webhook_delivery,clinic_integration_api.group_api_operator,1,0,0,0", rows)

    def test_runtime_pending_is_documented(self):
        matrix = (ROOT / "docs/ENTERPRISE_COMPLETENESS_MATRIX.md").read_text()
        self.assertIn("Odoo 19 runtime installation | PENDING", matrix)
        self.assertIn("Source/static PASS is not runtime completion", matrix)


if __name__ == "__main__":
    unittest.main()
