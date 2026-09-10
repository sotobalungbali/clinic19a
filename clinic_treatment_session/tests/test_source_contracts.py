
from pathlib import Path
import ast
import csv
import re
import unittest
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def python_sources():
    return [
        path for path in (ROOT / "models").rglob("*.py")
        if not path.name.startswith(tuple("0123456789"))
    ]


class TestTreatmentSessionSourceContracts(unittest.TestCase):
    def test_manifest_release_identity(self):
        manifest = ast.literal_eval(
            (ROOT / "__manifest__.py").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "19.0.2.0.4")
        for dep in (
            "clinic_booking", "clinic_patient", "clinic_doctor",
            "clinic_referral", "clinic_billing",
        ):
            self.assertIn(dep, manifest["depends"])
        for rel in manifest["data"]:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_three_owned_models_preserved(self):
        source = "\n".join(
            p.read_text(encoding="utf-8") for p in python_sources()
        )
        for model in (
            'clinic.treatment.session',
            'clinic.treatment.session.line',
            'clinic.treatment.session.stage',
        ):
            self.assertIn(model, source)

    def test_historical_extension_contracts_preserved(self):
        required = {
            "models/extensions/ext_booking.py": (
                "treatment_session_ids",
                "treatment_session_count",
                "has_treatment_sessions",
                "auto_session_policy",
                "generate_treatment_sessions",
                "action_generate_treatment_sessions",
                "action_view_treatment_sessions",
                "action_generate_and_view_treatment_sessions",
                "_prepare_session_vals",
            ),
            "models/extensions/ext_patient.py": (
                "treatment_session_ids",
                "treatment_session_count",
                "last_session_id",
                "next_session_id",
                "action_view_treatment_sessions",
                "action_view_treatment_history",
                "get_treatment_statistics",
            ),
            "models/extensions/ext_doctor.py": (
                "treatment_session_ids",
                "treatment_session_count",
                "sessions_today_count",
                "sessions_in_progress_count",
                "action_view_treatment_sessions",
                "action_view_today_treatment_sessions",
                "get_treatment_statistics",
            ),
            "models/extensions/ext_room_device.py": (
                "treatment_session_ids",
                "treatment_session_count",
                "sessions_today_count",
                "occupancy_state",
                "is_available",
                "get_occupancy_summary",
                "action_view_treatment_sessions",
                "action_view_today_treatment_sessions",
            ),
        }
        for rel, tokens in required.items():
            source = (ROOT / rel).read_text(encoding="utf-8")
            for token in tokens:
                self.assertIn(token, source, f"{rel}: {token}")

    def test_room_availability_owner_api_repaired(self):
        path = ROOT / "models/extensions/ext_room_device.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = None
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef):
                for node in cls.body:
                    if isinstance(node, ast.FunctionDef) and node.name == "is_available":
                        method = node
        self.assertIsNotNone(method)
        args = [arg.arg for arg in method.args.args]
        self.assertEqual(
            args[:6],
            [
                "self", "start_dt", "end_dt",
                "ignore_booking_id", "consider_capacity", "ignore_session_ids",
            ],
        )
        segment = ast.get_source_segment(source, method) or ""
        for token in (
            "super().is_available",
            "ignore_booking_id=ignore_booking_id",
            "consider_capacity=consider_capacity",
            'self.env["clinic.treatment.session"]',
            '"start_datetime" in kwargs',
            '"end_datetime" in kwargs',
        ):
            self.assertIn(token, segment)

    def test_enterprise_booking_canonical_mapping(self):
        source = (ROOT / "models/enterprise_booking.py").read_text(encoding="utf-8")
        for token in (
            "def _get_booking_employee_doctor(",
            'vals["clinic_doctor_id"] = employee.id or False',
            'vals["doctor_id"] = self.doctor_id.id or False',
        ):
            self.assertIn(token, source)

    def test_stock_completion_guard(self):
        source = (ROOT / "models/enterprise_line.py").read_text(encoding="utf-8")
        for token in (
            "move._action_done()",
            'if move.state != "done":',
            "A completed inventory movement cannot be hidden",
        ):
            self.assertIn(token, source)

    def test_odoo19_constraints_and_no_legacy_sql_constraints(self):
        source = "\n".join(
            p.read_text(encoding="utf-8") for p in python_sources()
        )
        self.assertNotIn("_sql_constraints", source)
        self.assertGreaterEqual(source.count("models.Constraint("), 4)

    def test_python_ast_parses(self):
        for path in python_sources():
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_xml_parses_and_uses_odoo19_view_syntax(self):
        for path in ROOT.rglob("*.xml"):
            if path.name[:1].isdigit():
                continue
            ET.parse(path)
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("<tree", source, str(path))
            self.assertNotRegex(source, r"\sattrs\s*=", str(path))
            self.assertNotRegex(source, r"\sstates\s*=", str(path))

    def test_acl_matrix_preserved(self):
        with (ROOT / "security/ir.model.access.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 8)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["access_treatment_session_user"]["perm_write"], "1")
        self.assertEqual(by_id["access_treatment_session_line_user"]["perm_create"], "1")
        self.assertEqual(by_id["access_treatment_session_stage_user"]["perm_write"], "0")
        self.assertEqual(by_id["access_treatment_session_manager"]["perm_unlink"], "1")

    def test_required_enterprise_release_files_present(self):
        required = {
            "models/enterprise_session.py",
            "models/enterprise_line.py",
            "models/enterprise_booking.py",
            "models/enterprise_billing.py",
            "models/enterprise_navigation.py",
            "models/canonical_bridges.py",
            "models/referral_bridge.py",
            "models/ui_bridge.py",
            "migrations/19.0.2.0.0/pre-migrate.py",
            "docs/FULL_STRUCTURAL_INVENTORY.md",
            "docs/CROSS_ADDON_CONTRACT_AUDIT.md",
            "docs/UI_UX_MATRIX.md",
            "docs/SECURITY_MODEL.md",
            "docs/ENTERPRISE_COMPLETENESS_MATRIX.md",
            "docs/CLINIC_DEMO_CORE_PATCH_LEDGER.md",
        }
        missing = [rel for rel in sorted(required) if not (ROOT / rel).is_file()]
        self.assertEqual(missing, [])

    def test_digit_prefixed_backup_files_not_packaged(self):
        bad = [
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_file() and path.name[:1].isdigit()
        ]
        self.assertEqual(bad, [])

    def test_model_files_are_bounded(self):
        too_large = []
        for path in (ROOT / "models").rglob("*.py"):
            if path.name[:1].isdigit():
                continue
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count > 900:
                too_large.append((str(path.relative_to(ROOT)), line_count))
        self.assertEqual(too_large, [])

    def test_runtime_safe_ui_bridge_contract(self):
        source = (ROOT / "models/ui_bridge.py").read_text(encoding="utf-8")
        for token in (
            "raise_if_not_found=False",
            "_get_combined_arch()",
            "with self.env.cr.savepoint():",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
