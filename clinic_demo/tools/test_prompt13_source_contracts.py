




#!/usr/bin/env python3
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services/historical_service.py"
GEN = ROOT / "generators/history/patient_longitudinal.py"
SOURCE_SHA = "6904ebf6d62ae5f60371fd91287d99b00eba10addb2d7f952602fb0165ef5c2b"


def assignments(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def class_meta(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    out = {}
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        out[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    return cls, out


class TestPrompt13SourceContracts(unittest.TestCase):
    def test_build_contract(self):
        manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.61")
        constants = (ROOT / "services/constants.py").read_text()
        self.assertIn(SOURCE_SHA, constants)
        self.assertIn('GENERATOR_VERSION = "19.0.1.0.61"', constants)

    def test_historical_service_is_registered_as_runtime_service(self):
        self.assertTrue(SERVICE.is_file())
        self.assertIn("from . import historical_service", (ROOT / "services/__init__.py").read_text())

    def test_prompt13_generator_registration(self):
        cls, meta = class_meta(GEN, "HistoricalPatientLongitudinalGenerator")
        self.assertEqual(meta["key"], "history.patient_longitudinal")
        self.assertEqual(meta["phase"], "13_history")
        self.assertEqual(meta["sequence"], 550)
        self.assertEqual(meta["depends_on"], ("resources.rooms_devices",))
        self.assertEqual(meta["scenario_keys"], ("SCN-PATIENT-RET-01",))
        self.assertTrue(any(ast.unparse(d) == "GENERATOR_REGISTRY.register" for d in cls.decorator_list))
        self.assertIn("from . import history", (ROOT / "generators/__init__.py").read_text())

    def test_profile_history_budgets(self):
        service = assignments(SERVICE)
        gen = assignments(GEN)
        self.assertEqual(service["PROFILE_HISTORY_BUDGETS"], {
            "compact": 24, "standard": 48, "full_enterprise": 72,
        })
        self.assertEqual(gen["PROFILE_HISTORY_PATIENT_COUNTS"], {
            "compact": 6, "standard": 8, "full_enterprise": 12,
        })
        self.assertEqual(gen["PROFILE_CONDITION_EPISODES"], {
            "compact": 3, "standard": 4, "full_enterprise": 6,
        })

    def test_profile_positions_are_nested_and_cover_latest_history(self):
        positions = assignments(SERVICE)["PROFILE_SEGMENT_POSITIONS"]
        compact = set(positions["compact"])
        standard = set(positions["standard"])
        full = set(positions["full_enterprise"])
        self.assertTrue(compact <= standard <= full)
        self.assertTrue(min(compact) <= 6)  # Sunday shift can still remain within T-7.
        self.assertEqual(len(positions["compact"]) * 12, 24)
        self.assertEqual(len(positions["standard"]) * 12, 48)
        self.assertEqual(len(positions["full_enterprise"]) * 12, 72)

    def test_prompt13_bucket_contract_matches_master_prompt(self):
        text = SERVICE.read_text()
        for token in (
            '"baseline", "Baseline History", 181, 365',
            '"growth", "Growth Period", 91, 180',
            '"recent_quarter", "Recent Quarter", 31, 90',
            '"recent_activity", "Recent Activity", 8, 30',
            '"latest_history", "Latest History", 1, 7',
        ):
            self.assertIn(token, text)

    def test_business_dates_not_system_audit_dates(self):
        text = SERVICE.read_text()
        self.assertIn("BUSINESS_DATE_FIELDS", text)
        for model in (
            '"booking.booking"', '"clinic.referral"', '"clinic.encounter"',
            '"clinic.treatment.session"', '"clinical.imaging"', '"clinic.emar.order"',
            '"clinic.care.plan"', '"clinic.postcare.plan"', '"clinic.billing.invoice"',
            '"clinic.billing.payment"', '"clinic.feedback.request"', '"clinic.incident"',
            '"clinic.quality.check"',
        ):
            self.assertIn(model, text)
        # Documentation may mention the audit fields, but the contract mapping itself
        # must not register them as business-time fields.
        mapping_text = text.split("BUSINESS_DATE_FIELDS =", 1)[1].split("\n\n\nclass HistoricalTimelineService", 1)[0]
        self.assertNotIn('"create_date"', mapping_text)
        self.assertNotIn('"write_date"', mapping_text)

    def test_downstream_business_date_fields_match_source_actual_files(self):
        # Verify the field contract against the authoritative owner-addon source.
        # Some fields are additive _inherit extensions in a second runtime file,
        # so search the active Python tree for each owning addon instead of
        # assuming one class/file owns the whole runtime model.
        checks = {
            "clinic_booking": ("start_datetime", "end_datetime", "checkin_time", "checkout_time"),
            "clinic_referral": ("date_referral", "date_received", "date_converted", "date_cancelled"),
            "clinic_encounter": ("date_planned_start", "date_planned_end", "date_start", "date_end"),
            "clinic_treatment_session": ("start_datetime", "end_datetime", "actual_start_datetime", "actual_end_datetime"),
            "clinic_imaging": ("request_datetime", "desired_datetime", "performed_datetime", "reviewed_datetime"),
            "clinic_emar": ("date_prescribed", "date_start", "date_end", "date_completed"),
            "clinic_care_plan": ("start_date", "end_date"),
            "clinic_post_care_followup": ("start_datetime", "expected_end_date"),
            "clinic_billing": ("invoice_date", "invoice_date_due"),
            "clinic_incident_event": ("occurred_at", "detected_at", "reported_at"),
            "clinic_quality": ("planned_date", "started_at"),
        }
        for addon, fields in checks.items():
            owner_root = ROOT.parent / addon
            if not owner_root.is_dir():
                self.skipTest(f"Owner source sibling not present in standalone package: {addon}")
            combined = "\n".join(
                path.read_text()
                for path in owner_root.rglob("*.py")
                if not path.name[:1].isdigit()
            )
            for field in fields:
                self.assertRegex(combined, rf"\b{re.escape(field)}\s*=\s*fields\.", (addon, field))


    def test_longitudinal_models_only_in_prompt13_generator(self):
        _cls, meta = class_meta(GEN, "HistoricalPatientLongitudinalGenerator")
        self.assertEqual(set(meta["owned_models"]), {
            "clinic.patient.vital",
            "clinic.patient.condition.episode",
            "clinic.patient.allergy.reaction",
        })

    def test_no_premature_booking_clinical_or_financial_transaction_create(self):
        text = GEN.read_text()
        forbidden_models = (
            '"booking.booking"', '"clinic.referral"', '"clinic.encounter"',
            '"clinic.treatment.session"', '"clinical.imaging"', '"clinic.emar.order"',
            '"clinic.care.plan"', '"clinic.postcare.plan"', '"clinic.billing.invoice"',
            '"clinic.billing.payment"', '"clinic.feedback"', '"clinic.incident"',
            '"clinic.quality.check"',
        )
        # These names may appear in the historical service contract but must not be
        # owned or created by the Prompt-13 patient generator.
        for model in forbidden_models:
            self.assertNotIn(model, text)

    def test_vital_history_uses_source_business_datetime(self):
        text = GEN.read_text()
        self.assertIn('"measured_datetime": measured_datetime', text)
        self.assertIn('"DEMO-HIST-VITAL-{index:03d}"', text)
        self.assertIn('"DEMO-DEVICE-MON-01"', text)
        self.assertIn('"DEMO-USER-NUR-001"', text)

    def test_chronic_condition_episode_history(self):
        text = GEN.read_text()
        self.assertIn('"DEMO-PATCOND-CHRON-001"', text)
        self.assertIn('"clinic.patient.condition.episode"', text)
        self.assertIn('"episode_datetime": event_dt', text)
        self.assertIn("CONDITION_EPISODE_DAYS", text)

    def test_allergy_reaction_history(self):
        text = GEN.read_text()
        self.assertIn('"DEMO-PATALLERGY-EMAR-001"', text)
        self.assertIn('"DEMO-HIST-ALLERGY-REACTION-001"', text)
        self.assertIn('"onset_datetime": onset', text)
        self.assertIn('"outcome": "recovered"', text)

    def test_synthetic_nondiagnostic_contract(self):
        text = GEN.read_text()
        self.assertIn("presentation data only", text)
        self.assertIn("not a clinical diagnosis", text)
        self.assertIn("Synthetic", text)

    def test_reset_registry_covers_prompt13_history_children(self):
        text = (ROOT / "services/reset_policy_registry.py").read_text()
        for model in (
            '"clinic.patient.vital"',
            '"clinic.patient.condition.episode"',
            '"clinic.patient.allergy.reaction"',
        ):
            self.assertIn(model, text)
        self.assertIn("Prompt-13 longitudinal observations", text)
        self.assertIn("RESET_DELETE_SAFE", text)

    def test_progressive_prompt13_adoption(self):
        text = (ROOT / "models/demo_run.py").read_text()
        self.assertIn("progressive_prompt13_adoption", text)
        self.assertIn("completed_prompt12_generators", text)
        self.assertIn("prompt12_complete", text)
        self.assertIn('prompt13_generators = {"history.patient_longitudinal"}', text)
        self.assertIn('"resources.rooms_devices" in checkpoint_generators', text)
        self.assertIn("Prompt 13 progressive contract adopted after completed Prompt-12 scope", text)

    def test_registered_scope_count_is_ten(self):
        keys = []
        for path in (ROOT / "generators").rglob("*.py"):
            tree = ast.parse(path.read_text())
            for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
                if not any(ast.unparse(d) == "GENERATOR_REGISTRY.register" for d in cls.decorator_list):
                    continue
                for node in cls.body:
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "key" for t in node.targets):
                        keys.append(ast.literal_eval(node.value))
        self.assertGreaterEqual(len(set(keys)), 10)
        self.assertIn("history.patient_longitudinal", keys)

    def test_registered_scope_notification_mentions_prompt13(self):
        text = (ROOT / "services/execution_engine.py").read_text()
        self.assertIn("Prompt-13 longitudinal", text)
        self.assertIn("35-generator enterprise registry", text)

    def test_determinism_guardrails(self):
        service = SERVICE.read_text()
        gen = GEN.read_text()
        for text in (service, gen):
            self.assertNotIn(".sudo(", text)
            self.assertNotIn(".execute(", text)
            self.assertNotIn(".cr.commit(", text)
            self.assertNotIn("date.today()", text)
            self.assertNotIn("datetime.now()", text)
            self.assertNotIn("uuid4", text)
        self.assertIn("ctx.seed_service", gen)
        self.assertIn("fields.Date.to_date(run.anchor_date)", service)

    def test_runtime_preflight_checks_downstream_business_date_contract(self):
        text = GEN.read_text()
        self.assertIn("for model_name, date_fields in BUSINESS_DATE_FIELDS.items()", text)
        self.assertIn("missing historical business fields", text)

    def test_validation_requires_all_historical_buckets(self):
        text = GEN.read_text()
        self.assertIn("required_buckets = {bucket.key for bucket in HISTORICAL_BUCKETS}", text)
        self.assertIn("Historical vital coverage is missing buckets", text)

    def test_full_enterprise_prompt13_business_history_budget(self):
        service = assignments(SERVICE)
        gen = assignments(GEN)
        total = (
            service["PROFILE_HISTORY_BUDGETS"]["full_enterprise"]
            + gen["PROFILE_CONDITION_EPISODES"]["full_enterprise"]
            + 1
        )
        self.assertEqual(total, 79)


if __name__ == "__main__":
    unittest.main(verbosity=2)
























