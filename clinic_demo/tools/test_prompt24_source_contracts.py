import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Prompt24SourceContracts(unittest.TestCase):
    def test_release_version_and_generator_freeze(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "19.0.1.0.61")
        constants = (ROOT / "services/constants.py").read_text(encoding="utf-8")
        self.assertIn('GENERATOR_VERSION = "19.0.1.0.61"', constants)

    def test_required_release_artifacts(self):
        for name in (
            "CLINIC_DEMO_EXECUTIVE_DEMO_SCRIPT.md",
            "CLINIC_DEMO_ENTERPRISE_COMPLETENESS_MATRIX.md",
            "CLINIC_DEMO_RELEASE_MANIFEST.md",
            "CLINIC_DEMO_CORE_PATCH_LEDGER.md",
            "PROMPT_24_FINAL_HARDENING_RELEASE.md",
        ):
            self.assertTrue((ROOT / "docs" / name).is_file(), name)

    def test_all_fourteen_chapters_and_real_keys(self):
        source = (ROOT / "docs/CLINIC_DEMO_EXECUTIVE_DEMO_SCRIPT.md").read_text(encoding="utf-8")
        for chapter in range(1, 15):
            self.assertIn(f"| {chapter}.", source)
        for key in ("DEMO-REF-001", "DEMO-QUEUE-WAIT-001", "DEMO-ENC-001", "DEMO-BILL-001", "DEMO-INC-001"):
            self.assertIn(key, source)

    def test_release_does_not_claim_unexecuted_fresh_db_proof(self):
        source = (ROOT / "docs/CLINIC_DEMO_RELEASE_MANIFEST.md").read_text(encoding="utf-8")
        self.assertIn("falsely reported as executed", source)
        self.assertIn("unknown models/states block reset", source)


if __name__ == "__main__":
    unittest.main()















