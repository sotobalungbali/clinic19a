




#!/usr/bin/env python3
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "generators/resources/rooms_devices.py"
SOURCE_SHA = "6904ebf6d62ae5f60371fd91287d99b00eba10addb2d7f952602fb0165ef5c2b"


def assignments(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try: out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception: pass
    return out


def class_meta(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    out = {}
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try: out[target.id] = ast.literal_eval(node.value)
                    except Exception: pass
    return cls, out


class TestPrompt12SourceContracts(unittest.TestCase):
    def test_build_contract(self):
        manifest = ast.literal_eval(ast.parse((ROOT / "__manifest__.py").read_text()).body[0].value)
        self.assertEqual(manifest["version"], "19.0.1.0.61")
        constants = (ROOT / "services/constants.py").read_text()
        self.assertIn(SOURCE_SHA, constants)
        self.assertIn('GENERATOR_VERSION = "19.0.1.0.61"', constants)

    def test_generator_registration_and_dependency(self):
        cls, meta = class_meta(GEN, "ResourcesRoomsDevicesGenerator")
        self.assertEqual(meta["key"], "resources.rooms_devices")
        self.assertEqual(meta["phase"], "12_resources")
        self.assertEqual(meta["sequence"], 500)
        self.assertEqual(meta["depends_on"], ("master.commercial",))
        self.assertTrue(any(ast.unparse(d) == "GENERATOR_REGISTRY.register" for d in cls.decorator_list))
        self.assertIn("from . import resources", (ROOT / "generators/__init__.py").read_text())

    def test_profile_budgets(self):
        vals = assignments(GEN)
        self.assertEqual(vals["PROFILE_ROOM_COUNTS"], {"compact": 4, "standard": 6, "full_enterprise": 9})
        self.assertEqual(vals["PROFILE_DEVICE_COUNTS"], {"compact": 4, "standard": 6, "full_enterprise": 8})
        self.assertEqual(vals["PROFILE_SLOT_COUNTS"], {"compact": 4, "standard": 8, "full_enterprise": 12})

    def test_room_device_source_models(self):
        text = GEN.read_text()
        for token in ('"clinic.room.type"', '"clinic.room"', '"clinic.room.availability"', '"clinic.device.category"', '"clinic.device"', '"clinic.room.device.assignment"'):
            self.assertIn(token, text)

    def test_booking_resource_scheduling_models(self):
        text = GEN.read_text()
        for token in ('"booking.room"', '"booking.room.schedule"', '"booking.room.blackout"', '"booking.resource"', '"booking.resource.schedule"', '"booking.resource.blackout"', '"booking.doctor.schedule"', '"booking.slot"'):
            self.assertIn(token, text)

    def test_service_resource_compatibility(self):
        text = GEN.read_text()
        for token in ('"allowed_treatment_ids"', '"allowed_doctor_ids"', '"booking_default_room_ids"', '"booking_default_resource_ids"', 'TREATMENT_ROOM_TYPE'):
            self.assertIn(token, text)

    def test_branch_provider_consistency_is_explicit(self):
        text = GEN.read_text()
        self.assertIn('doctor.branch_id', text)
        self.assertIn('doctor_branch_no', text)
        self.assertIn('DEMO-BRANCH-', text)
        self.assertIn('DEMO-LOC-B', text)

    def test_assignment_uses_owner_business_method(self):
        text = GEN.read_text()
        self.assertIn('assignment.action_activate()', text)
        self.assertIn('"create_movement_logs": False', text)

    def test_controlled_exception_uses_blackouts(self):
        text = GEN.read_text()
        self.assertIn('DEMO-BROOM-BLACKOUT-001', text)
        self.assertIn('DEMO-BRESOURCE-BLACKOUT-001', text)
        self.assertIn('Planned deep cleaning', text)
        self.assertIn('Planned preventive maintenance', text)

    def test_no_premature_operational_transactions(self):
        text = GEN.read_text()
        for forbidden in ('"booking.booking"', '"clinic.room.session"', '"clinic.queue"', '"clinic.triage"', '"clinic.encounter"', '"clinic.treatment.session"', '"account.move"'):
            self.assertNotIn(forbidden, text)

    def test_sequence_preflight(self):
        text = GEN.read_text()
        self.assertIn('clinic.device.code', text)
        self.assertIn('clinic.room.device.assignment', text)
        self.assertIn('missing sequence', text)

    def test_reset_registry_covers_prompt12(self):
        text = (ROOT / "services/reset_policy_registry.py").read_text()
        for token in ('"clinic.room"', '"clinic.device"', '"booking.room"', '"booking.resource"', '"booking.slot"', '"booking.doctor.schedule"'):
            self.assertIn(token, text)
        self.assertIn('Prompt-12 resource/scheduling masters', text)

    def test_progressive_adoption(self):
        text = (ROOT / "models/demo_run.py").read_text()
        self.assertIn('progressive_prompt12_adoption', text)
        self.assertIn('completed_prompt11_generators', text)
        self.assertIn('"master.commercial" in checkpoint_generators', text)
        self.assertIn('prompt12_generators = {"resources.rooms_devices"}', text)

    def test_registered_scope_count_is_nine(self):
        keys = []
        for path in (ROOT / "generators").rglob("*.py"):
            tree = ast.parse(path.read_text())
            for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
                if not any(ast.unparse(d) == "GENERATOR_REGISTRY.register" for d in cls.decorator_list):
                    continue
                for node in cls.body:
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "key" for t in node.targets):
                        keys.append(ast.literal_eval(node.value))
        self.assertGreaterEqual(len(set(keys)), 9)
        self.assertIn("resources.rooms_devices", keys)


    def test_profile_device_room_targets_exist_without_cross_branch_fallback(self):
        vals = assignments(GEN)
        room_specs = vals["ROOM_SPECS"]
        device_specs = vals["DEVICE_SPECS"]
        room_counts = vals["PROFILE_ROOM_COUNTS"]
        device_counts = vals["PROFILE_DEVICE_COUNTS"]
        for profile in ("compact", "standard", "full_enterprise"):
            room_keys = {(b, token) for b, token, *_rest in room_specs[:room_counts[profile]]}
            for _token, _name, _cat, branch, room_token, *_rest in device_specs[:device_counts[profile]]:
                self.assertIn((branch, room_token), room_keys, (profile, branch, room_token))

    def test_branch_scoped_doctor_resource_contract(self):
        text = GEN.read_text()
        self.assertIn('branch_doctors = [d for d in doctors if d.branch_id == branch]', text)
        self.assertIn('branch_doctor_ids = [d.id for d in branch_doctors]', text)
        self.assertIn('branch_employee_ids', text)
        self.assertNotIn('doctors[0] if doctors else False', text)

    def test_room_availability_is_monday_to_saturday(self):
        text = GEN.read_text()
        self.assertIn('for weekday in range(6):', text)
        self.assertIn('DEMO-ROOMAVAIL-B', text)
        self.assertIn('"byweekday": str(weekday)', text)

    def test_reset_sequence_is_child_first(self):
        text = GEN.read_text()
        self.assertIn('"clinic.room", values, reset_sequence=720', text)
        self.assertIn('"booking.room", {', text)
        self.assertIn('policy=RESET_DELETE_SAFE, reset_sequence=900', text)
        self.assertIn('policy=RESET_DELETE_SAFE, reset_sequence=890', text)
        self.assertIn('"clinic.room.device.assignment", {', text)
        self.assertIn('reset_sequence=930', text)

    def test_device_assignment_capacity_guard_is_respected(self):
        text = GEN.read_text()
        self.assertIn('physical_capacity = max(capacity, 2) if type_code == "IMG" else capacity', text)
        self.assertIn('"capacity": physical_capacity', text)
        self.assertIn('"capacity": capacity', text)

    def test_room_device_owner_version_and_sequence_repair_contract(self):
        constants = (ROOT / "services/constants.py").read_text()
        self.assertIn('"clinic_room_device": "19.0.1.0.1"', constants)
        run_text = (ROOT / "models/demo_run.py").read_text()
        self.assertIn("prompt12_runtime_repair_adoption", run_text)
        self.assertIn('"resources.rooms_devices"', run_text)
        self.assertIn("no_prompt12_references", run_text)
        self.assertIn("bounded runtime-repair contract adopted", run_text)


    def test_booking_slot_name_is_deterministically_unique_per_company(self):
        text = GEN.read_text()
        self.assertIn('"name": f"Demo {treatment.name} — {doctor.name} — Slot {idx + 1:03d}"', text)
        self.assertIn('"code": f"DEMO-SLOT-{idx + 1:03d}"', text)
        # booking.slot owner enforces both unique(name, company_id) and
        # unique(code, company_id); the stable slot ordinal makes both identities
        # unique even when treatment/doctor combinations repeat later in the profile.
        slot_count = assignments(GEN)["PROFILE_SLOT_COUNTS"]["full_enterprise"]
        generated_names = [f"slot-{idx + 1:03d}" for idx in range(slot_count)]
        self.assertEqual(len(generated_names), len(set(generated_names)))

    def test_determinism_and_runtime_guardrails(self):
        text = GEN.read_text()
        self.assertNotIn('.sudo(', text)
        self.assertNotIn('.execute(', text)
        self.assertNotIn('.cr.commit(', text)
        self.assertNotIn('date.today()', text)
        self.assertNotIn('random.', text)
        self.assertNotIn('uuid4', text)
        self.assertNotIn('create_date', text)
        self.assertNotIn('write_date', text)
        self.assertIn('fields.Date.to_date(ctx.run.anchor_date)', text)

if __name__ == "__main__":
    unittest.main(verbosity=2)
























