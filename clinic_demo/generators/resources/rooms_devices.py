
"""MASTER PROMPT 12 — Rooms, Devices, Resources & Scheduling."""

from datetime import datetime, time, timedelta

from odoo import _, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_DEACTIVATE, RESET_DELETE_SAFE
from ...services.generator_registry import GENERATOR_REGISTRY


ROOM_TYPE_SPECS = (
    ("CONS", "Consultation Room", "consultation", "exclusive", 1),
    ("TREAT", "Treatment Room", "treatment", "shared", 2),
    ("IMG", "Diagnostic Imaging Room", "imaging", "exclusive", 1),
    ("TRIAGE", "Triage & Observation Bay", "other", "queue_based", 2),
)

DEVICE_CATEGORY_SPECS = (
    ("MON", "Clinical Monitoring", "monitoring", "immediate", 180, 365),
    ("US", "Ultrasound Equipment", "ultrasound", "prep_required", 180, 180),
    ("IMG", "Diagnostic Imaging Equipment", "imaging", "technician_required", 90, 90),
    ("THER", "Therapy Equipment", "other", "prep_required", 180, 365),
)

ROOM_SPECS = (
    ("001", "CONS-01", "Consultation Room 01", "CONS", "CONSULT", 1),
    ("001", "TREAT-01", "Treatment Room 01", "TREAT", "TREAT-A", 2),
    ("001", "IMG-01", "Diagnostic Imaging Room 01", "IMG", "SITE", 1),
    ("001", "TRIAGE-01", "Triage & Observation Bay 01", "TRIAGE", "RECEPTION", 2),
    ("002", "CONS-01", "Consultation Room 01", "CONS", "CONSULT", 1),
    ("002", "TREAT-01", "Treatment Room 01", "TREAT", "TREAT-A", 2),
    ("002", "TRIAGE-01", "Triage & Observation Bay 01", "TRIAGE", "RECEPTION", 2),
    ("003", "CONS-01", "Consultation Room 01", "CONS", "SITE", 1),
    ("003", "TREAT-01", "Treatment Room 01", "TREAT", "TREAT-A", 2),
)
PROFILE_ROOM_COUNTS = {"compact": 4, "standard": 6, "full_enterprise": 9}

DEVICE_SPECS = (
    ("MON-01", "Multiparameter Monitor 01", "MON", "001", "TRIAGE-01", "DemoMed", "MP-7", ("CONSULT-GEN", "FOLLOW-UP")),
    ("US-01", "Ultrasound Unit 01", "US", "001", "IMG-01", "DemoSono", "US-X1", ("IMG-US",)),
    ("THER-01", "Therapy Device 01", "THER", "001", "TREAT-01", "DemoThera", "TH-200", ("PHYSIO", "WELLNESS")),
    ("IMG-01", "Imaging Workstation 01", "IMG", "001", "IMG-01", "DemoImage", "DX-1", ("IMG-XR", "IMG-MR")),
    ("MON-02", "Multiparameter Monitor 02", "MON", "002", "CONS-01", "DemoMed", "MP-7", ("CONSULT-GEN", "FOLLOW-UP")),
    ("THER-02", "Therapy Device 02", "THER", "002", "TREAT-01", "DemoThera", "TH-200", ("PHYSIO", "WELLNESS")),
    ("MON-03", "Multiparameter Monitor 03", "MON", "003", "CONS-01", "DemoMed", "MP-7", ("CONSULT-GEN", "FOLLOW-UP")),
    ("THER-03", "Therapy Device 03", "THER", "003", "TREAT-01", "DemoThera", "TH-300", ("PHYSIO", "WELLNESS")),
)
PROFILE_DEVICE_COUNTS = {"compact": 4, "standard": 6, "full_enterprise": 8}
PROFILE_SLOT_COUNTS = {"compact": 4, "standard": 8, "full_enterprise": 12}

TREATMENT_ROOM_TYPE = {
    "CONSULT-GEN": "CONS", "CONSULT-SPEC": "CONS", "FOLLOW-UP": "CONS",
    "TELE-CONSULT": "CONS", "PHYSIO": "TREAT", "WELLNESS": "TREAT",
    "SKIN-PROC": "TREAT", "IMG-XR": "IMG", "IMG-US": "IMG", "IMG-MR": "IMG",
}


@GENERATOR_REGISTRY.register
class ResourcesRoomsDevicesGenerator(BaseDemoGenerator):
    key = "resources.rooms_devices"
    phase = "12_resources"
    sequence = 500
    depends_on = ("master.commercial",)
    scenario_keys = ("SCN-QUEUE-01",)
    owned_models = (
        "clinic.room.type", "clinic.room", "clinic.room.availability",
        "clinic.device.category", "clinic.device", "clinic.room.device.assignment",
        "booking.room", "booking.room.schedule", "booking.room.blackout",
        "booking.resource", "booking.resource.schedule", "booking.resource.blackout",
        "booking.doctor.schedule", "booking.slot",
    )
    required_groups = ("base.group_user",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _ensure(self, ctx, counters, key, model, values, policy=RESET_DEACTIVATE, reset_sequence=700, update=True):
        Model = ctx.env[model].with_company(ctx.run.company_id)
        def create():
            return Model.create(dict(values))
        def update_record(record):
            record.write(dict(values))
        record, reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name=model, generator_key=self.key,
            scenario_key=ctx.scenario.key, create_callback=create,
            update_callback=update_record if update else None,
            reset_policy=policy, reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record, reference

    def _preflight(self, ctx):
        requirements = {
            "clinic.room": {"name", "code", "company_id", "room_type_id", "capacity", "status", "location_id"},
            "clinic.device": {"name", "company_id", "category_id", "status", "serial_no", "qualified_doctor_ids"},
            "clinic.room.device.assignment": {"device_id", "room_id", "state", "start", "create_movement_logs"},
            "booking.room": {"clinic_room_id", "allowed_treatment_ids", "allowed_doctor_ids", "resource_ids", "schedule_ids"},
            "booking.resource": {"code", "allowed_treatment_ids", "allowed_doctor_ids", "room_ids", "schedule_ids", "blackout_ids"},
            "booking.doctor.schedule": {"doctor_id", "weekday", "hour_from", "hour_to"},
            "booking.slot": {"doctor_id", "room_id", "resource_ids", "treatment_id", "weekday", "hour_from", "hour_to", "date_start", "date_end"},
        }
        missing = []
        for model_name, required in requirements.items():
            if model_name not in ctx.env:
                missing.append(f"missing model {model_name}")
                continue
            absent = sorted(required - set(ctx.env[model_name]._fields))
            if absent:
                missing.append(f"{model_name} missing fields {', '.join(absent)}")
        Sequence = ctx.env["ir.sequence"].with_company(ctx.run.company_id)
        for code in ("clinic.device.code", "clinic.room.device.assignment"):
            if not Sequence.search([("code", "=", code), ("company_id", "in", [False, ctx.run.company_id.id])], limit=1):
                missing.append(f"missing sequence {code}")
        if missing:
            raise UserError(_("MASTER PROMPT 12 resource preflight failed: %s") % "; ".join(missing))

    def _branch(self, ctx, number):
        return ctx.reference_service.resolve(ctx.run, f"DEMO-BRANCH-{number}", "clinic.branch")

    def _branch_location(self, ctx, branch_no, token):
        key = f"DEMO-LOC-B{branch_no}-{token}"
        return ctx.reference_service.resolve(ctx.run, key, "clinic.branch.location", missing_ok=True)

    def _doctor_records(self, ctx):
        max_count = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        return [ctx.reference_service.resolve(ctx.run, f"DEMO-DOC-{i:03d}", "clinic.doctor") for i in range(1, max_count + 1)]

    def _doctor_branch_number(self, ctx, doctor):
        max_branch = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        for number in range(1, max_branch + 1):
            if self._branch(ctx, f"{number:03d}") == doctor.branch_id:
                return f"{number:03d}"
        raise UserError(_("Prompt 12 doctor %s is not assigned to a generated demo branch.") % doctor.display_name)

    def _treatment(self, ctx, token):
        return ctx.reference_service.resolve(ctx.run, f"DEMO-TREAT-{token}", "clinic.treatment", missing_ok=True)

    def _ensure_room_types(self, ctx, counters):
        result = {}
        for seq, (code, name, usage, policy, capacity) in enumerate(ROOM_TYPE_SPECS, 1):
            rec, _ = self._ensure(ctx, counters, f"DEMO-ROOMTYPE-{code}", "clinic.room.type", {
                "name": name, "code": f"DEMO-{code}", "sequence": seq * 10,
                "active": True, "company_id": ctx.run.company_id.id,
                "usage_kind": usage, "booking_policy": policy,
                "default_capacity": capacity, "default_is_bookable": True,
                "description": f"<p>ClinicOne synthetic demo {name.lower()} master.</p>",
            }, reset_sequence=700)
            result[code] = rec
        return result

    def _ensure_device_categories(self, ctx, counters):
        result = {}
        for seq, (code, name, usage, readiness, maint, calib) in enumerate(DEVICE_CATEGORY_SPECS, 1):
            rec, _ = self._ensure(ctx, counters, f"DEMO-DEVCAT-{code}", "clinic.device.category", {
                "name": name, "code": f"DEMO-{code}", "sequence": seq * 10,
                "active": True, "company_id": ctx.run.company_id.id,
                "usage_kind": usage, "readiness_hint": readiness,
                "default_maintenance_interval_days": maint,
                "default_calibration_interval_days": calib,
                "training_required": readiness != "immediate",
                "training_description": "Synthetic ClinicOne demo competency requirement." if readiness != "immediate" else False,
            }, reset_sequence=700)
            result[code] = rec
        return result

    def _ensure_rooms(self, ctx, counters, room_types, doctors):
        rooms = {}
        booking_rooms = {}
        count = PROFILE_ROOM_COUNTS[ctx.profile]
        for idx, (branch_no, token, name, type_code, location_token, capacity) in enumerate(ROOM_SPECS[:count], 1):
            branch = self._branch(ctx, branch_no)
            location = self._branch_location(ctx, branch_no, location_token) or self._branch_location(ctx, branch_no, "SITE")
            stock_location = location.stock_location_id if location and location.stock_location_id else False
            room_code = f"DEMO-B{branch_no}-{token}"
            # clinic_room_device uses clinic.room.capacity as its active-device placement
            # guard as well as a people/session hint. The B001 imaging room intentionally
            # houses two source-valid devices, while booking.room below still enforces
            # single-patient concurrency.
            physical_capacity = max(capacity, 2) if type_code == "IMG" else capacity
            values = {
                "name": f"{branch.name} — {name}", "code": room_code, "sequence": idx * 10,
                "active": True, "company_id": ctx.run.company_id.id,
                "room_type_id": room_types[type_code].id, "capacity": physical_capacity,
                "is_bookable": True, "status": "available",
                "notes": f"<p>Synthetic Prompt-12 room mapped to {branch.display_name}.</p>",
            }
            if stock_location:
                values["location_id"] = stock_location.id
            branch_doctors = [d for d in doctors if d.branch_id == branch]
            room, _ = self._ensure(ctx, counters, f"DEMO-ROOM-B{branch_no}-{token}", "clinic.room", values, reset_sequence=720)
            rooms[(branch_no, token)] = room

            treatments = [self._treatment(ctx, t) for t, rt in TREATMENT_ROOM_TYPE.items() if rt == type_code]
            treatments = [t for t in treatments if t]
            booking_room, _ = self._ensure(ctx, counters, f"DEMO-BROOM-B{branch_no}-{token}", "booking.room", {
                "clinic_room_id": room.id, "name": room.name, "code": room_code,
                "active": True, "company_id": ctx.run.company_id.id,
                "sequence": idx * 10, "capacity": capacity,
                "buffer_before_minutes": 5 if type_code != "IMG" else 10,
                "buffer_after_minutes": 10 if type_code != "IMG" else 20,
                "allowed_treatment_ids": [(6, 0, [t.id for t in treatments])],
                "allowed_doctor_ids": [(6, 0, [d.id for d in branch_doctors])],
            }, reset_sequence=740)
            booking_rooms[(branch_no, token)] = booking_room

            anchor = fields.Date.to_date(ctx.run.anchor_date)
            for weekday in range(6):
                day = anchor + timedelta(days=(weekday - anchor.weekday()) % 7)
                self._ensure(ctx, counters, f"DEMO-ROOMAVAIL-B{branch_no}-{token}-{weekday}", "clinic.room.availability", {
                    "name": f"{room_code} {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][weekday]} Operating Window",
                    "active": True, "company_id": ctx.run.company_id.id, "room_id": room.id,
                    "start": datetime.combine(day, time(8, 0)),
                    "stop": datetime.combine(day, time(18, 0) if weekday < 5 else time(14, 0)),
                    "shift": "custom", "capacity_hint": capacity,
                    "is_template": True, "recurrence": "weekly", "interval": 1,
                    "byweekday": str(weekday), "until": anchor + timedelta(days=90), "state": "active",
                }, policy=RESET_DELETE_SAFE, reset_sequence=900)

                self._ensure(ctx, counters, f"DEMO-BROOM-SCHED-B{branch_no}-{token}-{weekday}", "booking.room.schedule", {
                    "room_id": booking_room.id, "company_id": ctx.run.company_id.id,
                    "active": True, "weekday": str(weekday), "hour_from": 8.0,
                    "hour_to": 18.0 if weekday < 5 else 14.0,
                    "note": "ClinicOne deterministic Prompt-12 operating schedule.",
                }, policy=RESET_DELETE_SAFE, reset_sequence=890)
        return rooms, booking_rooms

    def _ensure_devices_and_resources(self, ctx, counters, categories, rooms, booking_rooms, doctors):
        devices = {}
        resources = {}
        count = PROFILE_DEVICE_COUNTS[ctx.profile]
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        for idx, (token, name, cat, branch_no, room_token, maker, model, treatment_tokens) in enumerate(DEVICE_SPECS[:count], 1):
            room = rooms.get((branch_no, room_token))
            booking_room = booking_rooms.get((branch_no, room_token))
            if not room or not booking_room:
                raise UserError(_("Prompt 12 resource %s has no room in branch %s for this dataset profile.") % (token, branch_no))
            branch = self._branch(ctx, branch_no)
            branch_doctors = [d for d in doctors if d.branch_id == branch]
            branch_doctor_ids = [d.id for d in branch_doctors]
            branch_employee_ids = [
                d.staff_id.employee_id.id for d in branch_doctors
                if d.staff_id and d.staff_id.employee_id
            ]
            treatment_ids = [t.id for t in (self._treatment(ctx, t) for t in treatment_tokens) if t]
            device_values = {
                "name": name, "active": True, "company_id": ctx.run.company_id.id,
                "category_id": categories[cat].id, "serial_no": f"DEMO-SN-{token}",
                "model": model, "manufacturer": maker, "status": "available",
                "maintenance_interval_days": 180, "last_maintenance_date": anchor - timedelta(days=30),
                "calibration_interval_days": 180, "calibration_date_last": anchor - timedelta(days=20),
                "purchase_date": anchor - timedelta(days=540), "warranty_months": 36,
                "qualified_doctor_ids": [(6, 0, branch_employee_ids)],
                "notes": "<p>Synthetic medical-device master for ClinicOne enterprise demo.</p>",
            }
            if room.location_id:
                device_values["location_id"] = room.location_id.id
            device, _ = self._ensure(ctx, counters, f"DEMO-DEVICE-{token}", "clinic.device", device_values, reset_sequence=720)
            devices[token] = device

            assignment, _ = self._ensure(ctx, counters, f"DEMO-DEVICE-ASG-{token}", "clinic.room.device.assignment", {
                "device_id": device.id, "room_id": room.id, "company_id": ctx.run.company_id.id,
                "active": True, "state": "draft", "start": datetime.combine(anchor, time(7, 30)),
                "reason": "initial", "create_movement_logs": False,
                "notes": "Prompt-12 deterministic room placement.",
            }, reset_sequence=930)
            if assignment.state == "draft":
                assignment.action_activate()

            resource, _ = self._ensure(ctx, counters, f"DEMO-BRESOURCE-{token}", "booking.resource", {
                "name": name, "code": f"DEMO-{token}", "resource_type": "device",
                "description": "Booking-resource mirror of the ClinicOne demo medical device.",
                "active": True, "sequence": idx * 10, "company_id": ctx.run.company_id.id,
                "capacity_concurrent": 1, "buffer_before_minutes": 5, "buffer_after_minutes": 10,
                "allowed_treatment_ids": [(6, 0, treatment_ids)],
                "allowed_doctor_ids": [(6, 0, branch_doctor_ids)],
                "room_ids": [(6, 0, [booking_room.id])],
            }, reset_sequence=740)
            resources[token] = resource
            for weekday in range(6):
                self._ensure(ctx, counters, f"DEMO-BRESOURCE-SCHED-{token}-{weekday}", "booking.resource.schedule", {
                    "resource_id": resource.id, "company_id": ctx.run.company_id.id,
                    "active": True, "weekday": str(weekday), "hour_from": 8.0,
                    "hour_to": 18.0 if weekday < 5 else 14.0,
                    "note": "ClinicOne deterministic Prompt-12 resource schedule.",
                }, policy=RESET_DELETE_SAFE, reset_sequence=890)

        if resources:
            first = resources[next(iter(resources))]
            self._ensure(ctx, counters, "DEMO-BRESOURCE-BLACKOUT-001", "booking.resource.blackout", {
                "resource_id": first.id, "company_id": ctx.run.company_id.id, "active": True,
                "start_datetime": datetime.combine(anchor + timedelta(days=21), time(12, 0)),
                "end_datetime": datetime.combine(anchor + timedelta(days=21), time(15, 0)),
                "reason": "Planned preventive maintenance", "internal_notes": "Synthetic future maintenance window.",
            }, policy=RESET_DELETE_SAFE, reset_sequence=880)
        return devices, resources

    def _configure_scheduling(self, ctx, counters, rooms, booking_rooms, resources, doctors):
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        for d_idx, doctor in enumerate(doctors, 1):
            for weekday in range(6):
                self._ensure(ctx, counters, f"DEMO-BDOC-SCHED-{d_idx:03d}-{weekday}", "booking.doctor.schedule", {
                    "doctor_id": doctor.id, "company_id": ctx.run.company_id.id, "active": True,
                    "weekday": str(weekday), "hour_from": 9.0 + (d_idx - 1),
                    "hour_to": 16.0 + (d_idx - 1), "note": "Prompt-12 booking availability aligned to demo provider roster.",
                }, policy=RESET_DELETE_SAFE, reset_sequence=870)

        slot_treatments = ("CONSULT-GEN", "CONSULT-SPEC", "FOLLOW-UP", "PHYSIO", "IMG-US", "SKIN-PROC")
        resource_list = list(resources.values())
        room_list = list(booking_rooms.values())
        slot_count = PROFILE_SLOT_COUNTS[ctx.profile]
        for idx in range(slot_count):
            token = slot_treatments[idx % len(slot_treatments)]
            treatment = self._treatment(ctx, token)
            if not treatment:
                continue
            desired = TREATMENT_ROOM_TYPE.get(token, "CONS")
            eligible_doctors = []
            for candidate_doctor in doctors:
                branch_no = self._doctor_branch_number(ctx, candidate_doctor)
                if any(
                    key[0] == branch_no and rooms[key].room_type_id.code == f"DEMO-{desired}"
                    for key in booking_rooms
                ):
                    eligible_doctors.append(candidate_doctor)
            doctor = (eligible_doctors or doctors)[idx % len(eligible_doctors or doctors)]
            doctor_branch_no = self._doctor_branch_number(ctx, doctor)
            candidates = [
                br for key, br in booking_rooms.items()
                if key[0] == doctor_branch_no and rooms[key].room_type_id.code == f"DEMO-{desired}"
            ]
            if not candidates:
                raise UserError(
                    _("Prompt 12 found no %s room in the selected doctor's branch for %s.")
                    % (desired, treatment.display_name)
                )
            room = candidates[idx % len(candidates)]
            compatible_resources = [
                r for r in resource_list
                if (not r.allowed_treatment_ids or treatment in r.allowed_treatment_ids)
                and (not r.room_ids or room in r.room_ids)
            ]
            resource = compatible_resources[idx % len(compatible_resources)] if compatible_resources else False
            weekday = idx % 6
            hour_from = 9.0 + float((idx // 6) * 2)
            self._ensure(ctx, counters, f"DEMO-SLOT-{idx + 1:03d}", "booking.slot", {
                "name": f"Demo {treatment.name} — {doctor.name} — Slot {idx + 1:03d}", "code": f"DEMO-SLOT-{idx + 1:03d}",
                "active": True, "sequence": (idx + 1) * 10, "company_id": ctx.run.company_id.id,
                "doctor_id": doctor.id, "room_id": room.id,
                "resource_ids": [(6, 0, [resource.id] if resource else [])],
                "treatment_id": treatment.id, "weekday": str(weekday),
                "hour_from": hour_from, "hour_to": hour_from + 2.0,
                "duration_minutes": int(treatment.booking_default_duration_minutes or 30),
                "date_start": anchor, "date_end": anchor + timedelta(days=90),
                "capacity": 1, "buffer_before_minutes": 5, "buffer_after_minutes": 10,
                "description": "Synthetic reusable scheduling window; no patient booking is created in Prompt 12.",
            }, reset_sequence=860)

        if room_list:
            first_room = room_list[0]
            self._ensure(ctx, counters, "DEMO-BROOM-BLACKOUT-001", "booking.room.blackout", {
                "room_id": first_room.id, "company_id": ctx.run.company_id.id, "active": True,
                "start_datetime": datetime.combine(anchor + timedelta(days=14), time(13, 0)),
                "end_datetime": datetime.combine(anchor + timedelta(days=14), time(16, 0)),
                "reason": "Planned deep cleaning", "internal_notes": "Synthetic controlled availability exception.",
            }, policy=RESET_DELETE_SAFE, reset_sequence=880)

        # Apply resource-compatible defaults to already demo-owned treatment/provider masters.
        for token, room_type in TREATMENT_ROOM_TYPE.items():
            treatment = self._treatment(ctx, token)
            if not treatment:
                continue
            candidate_rooms = [br for key, br in booking_rooms.items() if rooms[key].room_type_id.code == f"DEMO-{room_type}"]
            candidate_resources = [r for r in resource_list if not r.allowed_treatment_ids or treatment in r.allowed_treatment_ids]
            treatment.write({
                "booking_default_room_ids": [(6, 0, [r.id for r in candidate_rooms])],
                "booking_default_resource_ids": [(6, 0, [r.id for r in candidate_resources])],
                "allowed_doctor_ids": [(6, 0, [d.id for d in doctors])],
            })
        for idx, doctor in enumerate(doctors):
            doctor_branch_no = self._doctor_branch_number(ctx, doctor)
            candidate_rooms = [br for key, br in booking_rooms.items() if key[0] == doctor_branch_no] or room_list[:1]
            candidate_resources = [
                r for r in resource_list
                if not r.room_ids or any(room in r.room_ids for room in candidate_rooms)
            ]
            doctor.write({
                "booking_default_room_ids": [(6, 0, [r.id for r in candidate_rooms])],
                "booking_default_resource_ids": [(6, 0, [r.id for r in candidate_resources])],
            })
            clinic_room = candidate_rooms[0].clinic_room_id if candidate_rooms else False
            if clinic_room and "default_room_id" in doctor._fields:
                doctor.write({"default_room_id": clinic_room.id})

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        counters = self._counters()
        doctors = self._doctor_records(ctx)
        room_types = self._ensure_room_types(ctx, counters)
        categories = self._ensure_device_categories(ctx, counters)
        room_types["CONS"].write({"device_category_ids": [(6, 0, [categories["MON"].id])]})
        room_types["TRIAGE"].write({"device_category_ids": [(6, 0, [categories["MON"].id])]})
        room_types["TREAT"].write({"device_category_ids": [(6, 0, [categories["THER"].id])]})
        room_types["IMG"].write({"device_category_ids": [(6, 0, [categories["US"].id, categories["IMG"].id])]})
        rooms, booking_rooms = self._ensure_rooms(ctx, counters, room_types, doctors)
        _devices, resources = self._ensure_devices_and_resources(ctx, counters, categories, rooms, booking_rooms, doctors)
        self._configure_scheduling(ctx, counters, rooms, booking_rooms, resources, doctors)
        return counters

    def validate(self, ctx, scenario):
        warnings = []
        references = ctx.run.reference_ids.filtered(lambda r: r.generator_key == self.key and r.record_status == "bound")
        room_refs = references.filtered(lambda r: r.model_name == "clinic.room")
        resource_refs = references.filtered(lambda r: r.model_name == "booking.resource")
        slot_refs = references.filtered(lambda r: r.model_name == "booking.slot")
        if len(room_refs) < PROFILE_ROOM_COUNTS[ctx.profile]:
            warnings.append(_("Prompt 12 room coverage is below the configured profile budget."))
        if len(resource_refs) < PROFILE_DEVICE_COUNTS[ctx.profile]:
            warnings.append(_("Prompt 12 booking-resource coverage is below the configured profile budget."))
        if len(slot_refs) < PROFILE_SLOT_COUNTS[ctx.profile]:
            warnings.append(_("Prompt 12 scheduling-slot coverage is below the configured profile budget."))
        for ref in room_refs:
            room = ctx.env[ref.model_name].browse(ref.res_id).exists()
            if room and room.company_id != ctx.run.company_id:
                warnings.append(_("Prompt 12 room/company consistency mismatch: %s") % room.display_name)
        return warnings

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}


