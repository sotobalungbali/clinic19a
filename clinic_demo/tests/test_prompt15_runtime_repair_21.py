



"""Regression contract for clinic_demo 19.0.1.0.21."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "generators" / "operations" / "queue_triage.py"
RUN = ROOT / "models" / "demo_run.py"


class TestPrompt15RuntimeRepair21(unittest.TestCase):
    def test_appointment_preflight_matches_canonical_owner(self):
        source = GEN.read_text(encoding="utf-8")
        appointment_block = source.split('"clinic.appointment": {', 1)[1].split("},", 1)[0]
        self.assertIn('"patient_id"', appointment_block)
        self.assertIn('"doctor_id"', appointment_block)
        self.assertNotIn('"treatment_id"', appointment_block)
        self.assertIn('"patient_id": "clinic.patient"', source)

    def test_patient_validation_uses_same_identity_domain(self):
        source = GEN.read_text(encoding="utf-8")
        self.assertIn("triage.appointment_id.patient_id != triage.patient_id", source)
        self.assertNotIn("triage.appointment_id.patient_id != partner", source)

    def test_failed_prompt15_adoption_is_bounded(self):
        source = RUN.read_text(encoding="utf-8")
        for token in (
            "prompt15_queue_triage_failed",
            "no_prompt15_references",
            "prompt15_runtime_repair_checkpoint_shape",
            "prompt15_runtime_repair_adoption",
            'checkpoint.generator_key == "operations.queue_triage"',
            'checkpoint.state == "failed"',
            'reference.generator_key == "operations.queue_triage"',
            'self.state == "failed"',
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)









