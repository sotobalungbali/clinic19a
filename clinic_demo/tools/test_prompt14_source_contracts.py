




#!/usr/bin/env python3
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REF_GEN = ROOT / "generators/operations/referral.py"
BOOK_GEN = ROOT / "generators/operations/booking.py"
SOURCE_SHA = "6904ebf6d62ae5f60371fd91287d99b00eba10addb2d7f952602fb0165ef5c2b"
SUITE_SHA = "0b28236cd75ba56f9dc86ac26230ba04aeeec9e8952f03907e9e8cc19a98aade"


def assignments(path):
    tree = ast.parse(path.read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def class_meta(path, name):
    tree = ast.parse(path.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    meta = {}
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        meta[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    return cls, meta


class TestPrompt14SourceContracts(unittest.TestCase):
    def test_build_contract(self):
        manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.61")
        constants = (ROOT / "services/constants.py").read_text()
        self.assertIn(SOURCE_SHA, constants)
        self.assertIn(SUITE_SHA, constants)
        self.assertIn('GENERATOR_VERSION = "19.0.1.0.61"', constants)
        self.assertIn('"clinic_booking": "19.0.1.0.5"', constants)
        self.assertIn('"clinic_referral": "19.0.2.0.6"', constants)

    def test_two_bounded_generators(self):
        _rcls, rmeta = class_meta(REF_GEN, "ReferralOperationsGenerator")
        _bcls, bmeta = class_meta(BOOK_GEN, "BookingOperationsGenerator")
        self.assertEqual(rmeta["key"], "operations.referral")
        self.assertEqual(rmeta["depends_on"], ("history.patient_longitudinal",))
        self.assertEqual(bmeta["key"], "operations.booking")
        self.assertEqual(bmeta["depends_on"], ("operations.referral",))
        self.assertEqual(rmeta["phase"], "14_frontoffice")
        self.assertEqual(bmeta["phase"], "14_frontoffice")

    def test_profile_budgets(self):
        r = assignments(REF_GEN)
        b = assignments(BOOK_GEN)
        self.assertEqual(r["PROFILE_REFERRAL_COUNTS"], {"compact": 5, "standard": 7, "full_enterprise": 10})
        self.assertEqual(b["PROFILE_HISTORICAL_BOOKINGS"], {"compact": 12, "standard": 18, "full_enterprise": 24})
        self.assertEqual(b["PROFILE_CURRENT_BOOKINGS"], {"compact": 6, "standard": 8, "full_enterprise": 10})
        self.assertEqual(b["PROFILE_FUTURE_BOOKINGS"], {"compact": 6, "standard": 8, "full_enterprise": 12})

    def test_referral_lifecycle_coverage(self):
        text = REF_GEN.read_text()
        for token in ('"draft"', '"confirmed"', '"converted"', '"cancelled"', '"expired"'):
            self.assertIn(token, text)
        self.assertIn("action_confirm(effective_datetime=", text)
        self.assertIn("action_convert(effective_datetime=", text)
        self.assertIn("action_cancel(effective_datetime=", text)
        self.assertIn("action_mark_expired(as_of_date=anchor)", text)

    def test_booking_owner_timezone_patch_contract(self):
        owner = ROOT.parent / "clinic_booking"
        if not owner.is_dir():
            self.skipTest("Owner source sibling not present in standalone package")
        manifest = ast.literal_eval(ast.parse((owner / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.5")
        for rel in ("models/booking_room.py", "models/booking_resource.py", "models/clinic_doctor_inherit.py"):
            text = (owner / rel).read_text()
            self.assertIn("fields.Datetime.context_timestamp", text)
            self.assertIn("local_start", text)
            self.assertIn("local_end", text)

    def test_referral_owner_patch_contract(self):
        owner = ROOT.parent / "clinic_referral"
        if not owner.is_dir():
            self.skipTest("Owner source sibling not present in standalone package")
        manifest = ast.literal_eval(ast.parse((owner / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.2.0.6")
        source = (owner / "models/referral.py").read_text()
        for sig in (
            "def action_confirm(self, effective_datetime=None):",
            "def action_convert(self, effective_datetime=None):",
            "def action_cancel(self, effective_datetime=None):",
            "def action_mark_expired(self, as_of_date=None):",
        ):
            self.assertIn(sig, source)
        self.assertIn("referral.action_convert(effective_datetime=effective_datetime)", source)

    def test_golden_referral_to_booking_conversion(self):
        rtext = REF_GEN.read_text(); btext = BOOK_GEN.read_text()
        self.assertIn('"DEMO-REF-001"', rtext)
        self.assertIn('"DEMO-BOOK-TODAY-REF-001"', btext)
        self.assertIn('referral.mark_converted(source_record=booking', btext)
        self.assertIn('"referral_id": referral.id if referral else False', btext)

    def test_booking_uses_owner_business_methods(self):
        text = BOOK_GEN.read_text()
        for token in (
            "booking.action_confirm()", "booking.action_done()", "booking.action_cancel(",
            "booking.action_mark_no_show()", "booking.action_apply_reschedule(",
        ):
            self.assertIn(token, text)
        self.assertNotIn('booking.write({"state"', text)

    def test_no_premature_downstream_creation(self):
        text = REF_GEN.read_text() + BOOK_GEN.read_text()
        for model in (
            "clinic.queue", "clinic.triage", "clinic.encounter", "clinic.treatment.session",
            "clinical.imaging", "clinic.emar.order", "clinic.billing.invoice", "account.move",
        ):
            self.assertNotIn(f'ctx.env["{model}"].create', text)

    def test_demo_safe_mode_booking_flags(self):
        text = BOOK_GEN.read_text()
        self.assertIn('"auto_create_appointment": False', text)
        self.assertIn('"lock_slot_on_confirm": False', text)
        self.assertIn('"website_published": False', text)

    def test_history_uses_prompt13_timeline_and_business_dates(self):
        text = REF_GEN.read_text() + BOOK_GEN.read_text()
        self.assertIn("HistoricalTimelineService", text)
        self.assertIn('with_context(tz=ctx.run.timezone or "UTC")', text)
        self.assertNotIn("create_date", text)
        self.assertNotIn("write_date", text)
        self.assertNotIn("datetime.now()", text)
        self.assertNotIn("date.today()", text)

    def test_current_schedule_sunday_safe(self):
        text = BOOK_GEN.read_text()
        self.assertIn("def _operating_day", text)
        self.assertIn("candidate.weekday() == 6", text)
        self.assertIn("lane_minutes", text)
        rtext = REF_GEN.read_text()
        self.assertIn("def _frontoffice_day", rtext)
        self.assertIn("anchor.weekday() == 6", rtext)
        self.assertIn("lane_counts", text)
        self.assertIn("slot_no * 55", text)
        self.assertIn("duration = min(30", text)

    def test_reset_registry_covers_prompt14(self):
        text = (ROOT / "services/reset_policy_registry.py").read_text()
        self.assertIn('"clinic.referral.program"', text)
        self.assertIn('"clinic.referral.source"', text)
        self.assertIn('"booking.channel"', text)
        self.assertIn('model_name == "booking.booking"', text)
        self.assertIn("Completed historical bookings", text)

    def test_progressive_prompt14_adoption(self):
        text = (ROOT / "models/demo_run.py").read_text()
        self.assertIn("progressive_prompt14_adoption", text)
        self.assertIn('prompt14_generators = {"operations.referral", "operations.booking"}', text)
        self.assertIn('"history.patient_longitudinal" in checkpoint_generators', text)
        self.assertIn("Prompt 14 progressive contract adopted after completed Prompt-13 scope", text)

    def test_scenario_registry_moves_today_booking_to_prompt14(self):
        text = (ROOT / "services/scenario_registry.py").read_text()
        self.assertIn("'key': 'SCN-BOOKING-TODAY-01'", text)
        self.assertIn("'generator_key': 'operations.booking'", text)
        self.assertIn("'phase': '14_frontoffice'", text)
        resources = (ROOT / "generators/resources/rooms_devices.py").read_text()
        self.assertNotIn('"booking.booking"', resources)

    def test_registered_scope_preserves_prompt14_minimum(self):
        keys = []
        for path in (ROOT / "generators").rglob("*.py"):
            tree = ast.parse(path.read_text())
            for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
                if not any(ast.unparse(d) == "GENERATOR_REGISTRY.register" for d in cls.decorator_list):
                    continue
                for node in cls.body:
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "key" for t in node.targets):
                        keys.append(ast.literal_eval(node.value))
        self.assertGreaterEqual(len(set(keys)), 12)
        self.assertIn("operations.referral", keys)
        self.assertIn("operations.booking", keys)

    def test_booking_channel_owner_create_is_odoo19_multi_safe(self):
        owner = ROOT.parent / "clinic_booking"
        if not owner.is_dir():
            self.skipTest("Owner source sibling not present in standalone package")
        source = (owner / "models/booking_channel.py").read_text()
        self.assertIn("@api.model_create_multi", source)
        self.assertIn("def create(self, vals_list):", source)
        self.assertIn("for original in vals_list:", source)
        self.assertNotIn("def create(self, vals):", source)

    def test_clinic_doctor_canonical_appointment_window_contract(self):
        owner = ROOT.parent / "clinic_doctor" / "models" / "appointment.py"
        if not owner.exists():
            self.skipTest("clinic_doctor owner source sibling not present in standalone package")
        text = owner.read_text(encoding="utf-8")
        self.assertIn('_name = "clinic.appointment"', text)
        self.assertIn('start = fields.Datetime(', text)
        self.assertIn('end = fields.Datetime(', text)
        self.assertIn('state = fields.Selection(', text)
        self.assertNotIn('start_datetime = fields.Datetime(', text)
        self.assertNotIn('end_datetime = fields.Datetime(', text)

    def test_booking_owner_appointment_field_bridge_contract(self):
        owner = ROOT.parent / "clinic_booking"
        doctor_bridge = (owner / "models/clinic_doctor_inherit.py").read_text(encoding="utf-8")
        booking_bridge = (owner / "models/booking_booking.py").read_text(encoding="utf-8")
        self.assertIn('start_field = "start" if "start" in app_fields', doctor_bridge)
        self.assertIn('end_field = "end" if "end" in app_fields', doctor_bridge)
        self.assertIn('("state", "not in", ["canceled", "no_show"])', doctor_bridge)
        self.assertIn('vals["start"] = rec.start_datetime', booking_bridge)
        self.assertIn('vals["end"] = rec.end_datetime', booking_bridge)
        self.assertIn('vals["partner_id"]', booking_bridge)

    def test_prompt14_booking_runtime_repair_adoption(self):
        text = (ROOT / "models/demo_run.py").read_text()
        self.assertIn("prompt14_booking_runtime_repair_adoption", text)
        self.assertIn('checkpoint.generator_key == "operations.booking"', text)
        self.assertIn('checkpoint.generator_key == "operations.referral"', text)
        self.assertIn('reference.generator_key == "operations.booking"', text)
        self.assertIn(
            "Prompt 14 bounded runtime-repair contract adopted after operations.booking rollback",
            text,
        )

    def test_treatment_session_room_availability_override_is_compositional(self):
        owner = ROOT.parent / "clinic_treatment_session"
        if not owner.is_dir():
            self.skipTest("clinic_treatment_session owner source sibling not present in standalone package")
        manifest = ast.literal_eval(
            ast.parse((owner / "__manifest__.py").read_text()).body[0].value
        )
        self.assertEqual(manifest["version"], "19.0.2.0.4")
        source = (owner / "models/extensions/ext_room_device.py").read_text(encoding="utf-8")
        self.assertIn("ignore_session_ids=None", source)
        self.assertIn("ignore_booking_id=None", source)
        self.assertIn("consider_capacity=True", source)
        self.assertIn("if not super().is_available(", source)
        self.assertIn("ignore_booking_id=ignore_booking_id", source)
        self.assertIn("consider_capacity=consider_capacity", source)
        self.assertIn('Session = self.env["clinic.treatment.session"]', source)

    def test_registered_scope_notification_mentions_prompt14(self):
        text = (ROOT / "services/execution_engine.py").read_text()
        self.assertIn("Prompt-14 referral/booking front-office operations", text)
        self.assertIn("35-generator enterprise registry", text)

    def test_no_security_or_sql_bypass(self):
        text = REF_GEN.read_text() + BOOK_GEN.read_text()
        for forbidden in (".sudo(", ".execute(", ".cr.commit("):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()






















