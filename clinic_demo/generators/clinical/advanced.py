"""MASTER PROMPT 17 — source-driven advanced clinical workflows."""

import base64
from datetime import datetime, time, timedelta
import pytz

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.journey_read_context import actor_key, read_model
from ...services.telemedicine_scope import prepare_telemedicine_scope


ADVANCED_RUNTIME_CONTRACTS = {
    "clinic.consent.form": {
        "fields": {"name", "company_id", "patient_id", "doctor_id", "treatment_id",
                   "template_id", "title", "content_text", "state"},
        "methods": {"action_set_to_sign", "action_sign"},
    },
    "clinical.imaging.device": {
        "fields": {"name", "company_id", "modality", "room_id", "status"},
        "methods": {"action_set_operational"},
    },
    "clinical.imaging": {
        "fields": {"name", "company_id", "patient_id", "doctor_id", "device_id",
                   "imaging_type_id", "scheduled_datetime", "state"},
        "methods": {"action_request", "action_schedule", "action_start",
                    "action_complete", "action_review"},
    },
    "clinic.emar.prescription": {
        "fields": {"name", "company_id", "patient_id", "doctor_id", "line_ids", "state"},
        "methods": {"action_validate", "action_activate"},
    },
    "clinic.emar.order": {
        "fields": {"name", "company_id", "patient_id", "doctor_id",
                   "clinic_patient_id", "clinic_doctor_id", "line_ids", "state"},
        "methods": {"action_confirm", "action_approve", "action_activate"},
    },
    "clinic.emar.administration": {
        "fields": {"name", "company_id", "order_id", "line_id", "product_id",
                   "patient_scan_code", "product_scan_code", "state"},
        "methods": {"action_confirm", "action_start", "action_done",
                    "action_verify_administration"},
    },
    "clinic.care.plan": {
        "fields": {"name", "company_id", "patient_id", "doctor_id",
                   "protocol_template_id", "consent_id", "is_confidential",
                   "line_ids", "state"},
        "methods": {"action_generate_lines_from_protocol", "action_activate"},
    },
    "clinic.postcare.protocol": {
        "fields": {"name", "code", "company_id", "care_protocol_id", "state"},
        "methods": {"action_activate"},
    },
    "clinic.postcare.plan": {
        "fields": {"name", "company_id", "patient_id", "protocol_id",
                   "care_plan_id", "state"},
        "methods": {"action_activate"},
    },
    "clinic.telemedicine.session": {
        "fields": {"name", "company_id", "patient_id", "doctor_id",
                   "consent_form_id", "meeting_url", "thread_ids", "state"},
        "methods": {"action_schedule", "action_mark_ready"},
    },
    "clinic.telemedicine.thread": {
        "fields": {"name", "company_id", "session_id", "patient_id", "doctor_id", "state"},
        "methods": {"action_close", "action_reopen"},
    },
    "clinic.telemedicine.message": {
        "fields": {"thread_id", "body", "author_kind", "sent_at"},
        "methods": set(),
    },
}

ADVANCED_RELATION_CONTRACTS = {
    ("clinical.imaging.device", "room_id"): "clinic.room",
    ("clinical.imaging", "patient_id"): "res.partner",
    ("clinical.imaging", "device_id"): "clinical.imaging.device",
    ("clinic.emar.prescription", "patient_id"): "clinic.patient",
    ("clinic.emar.order", "patient_id"): "res.partner",
    ("clinic.emar.order", "doctor_id"): "hr.employee",
    ("clinic.emar.order", "clinic_patient_id"): "clinic.patient",
    ("clinic.emar.order", "clinic_doctor_id"): "clinic.doctor",
    ("clinic.emar.administration", "order_id"): "clinic.emar.order",
    ("clinic.care.plan", "protocol_template_id"): "clinic.care.protocol",
    ("clinic.care.plan", "consent_id"): "clinic.consent.form",
    ("clinic.postcare.plan", "care_plan_id"): "clinic.care.plan",
    ("clinic.telemedicine.session", "patient_id"): "clinic.patient",
    ("clinic.telemedicine.session", "consent_form_id"): "clinic.consent.form",
    ("clinic.telemedicine.thread", "session_id"): "clinic.telemedicine.session",
    ("clinic.telemedicine.message", "thread_id"): "clinic.telemedicine.thread",
}

# Exact operations exercised by the generator and by owner workflow methods.
# This is intentionally not a blanket read/create/write matrix: immutable
# evidence (for example Secure Messages) must never be preflighted for write,
# while nurse access to an eMAR Order is deliberately read-only.
ADVANCED_ACCESS_CONTRACTS = {
    "DEMO-USER-DOC-001": {
        "clinic.consent.form": ("read", "create", "write"),
        "clinic.consent.signature": ("read", "create"),
        "clinical.imaging.device": ("read", "create", "write"),
        "clinical.imaging": ("read", "create", "write"),
        "mail.activity": ("read", "create", "write"),
        "clinic.emar.prescription": ("read", "create", "write"),
        "clinic.emar.medication.line": ("read", "create", "write"),
        "clinic.emar.order": ("read", "create", "write"),
        "clinic.emar.alert": ("read", "create", "write"),
        "clinic.care.plan": ("read", "create", "write"),
        "clinic.care.plan.line": ("read", "create", "write"),
        "clinic.telemedicine.session": ("read", "create", "write"),
        "clinic.telemedicine.thread": ("read", "create", "write"),
        "clinic.telemedicine.message": ("read", "create"),
    },
    "DEMO-USER-NUR-001": {
        "clinic.emar.order": ("read",),
        "clinic.emar.medication.line": ("read",),
        "clinic.emar.administration": ("read", "create", "write"),
    },
    "DEMO-USER-MGR": {
        "clinic.emar.order": ("read", "write"),
        "clinic.emar.schedule": ("read", "create", "write"),
        "clinic.postcare.protocol": ("read", "create", "write"),
        "clinic.postcare.plan": ("read", "create", "write"),
        "clinic.postcare.task": ("read", "create", "write"),
    },
}

ADVANCED_ACTOR_GROUPS = {
    "DEMO-USER-DOC-001": (
        "clinic_emar.group_emar_prescriber",
        "clinic_telemedicine_secure_messaging.group_telemedicine_clinician",
    ),
    "DEMO-USER-NUR-001": ("clinic_emar.group_emar_nurse",),
    "DEMO-USER-MGR": (
        "clinic_emar.group_emar_manager",
        "clinic_post_care_followup.group_postcare_manager",
    ),
}

# Odoo's default record prefetch may include every simple stored field on a
# related model. That is unsafe for role-bound actors when hr.employee carries
# legitimate private fields from several installed addons. Actor workflows use
# an explicit no-bulk-prefetch context and fetch only fields their owner methods
# actually touch.
ADVANCED_ACTOR_CONTEXT = {"prefetch_fields": False}

ADVANCED_FIELD_READ_CONTRACTS = {
    "DEMO-USER-DOC-001": (
        ("DEMO-EMP-DOC-001", "hr.employee", ("work_contact_id", "user_id")),
        ("DEMO-DOC-001", "clinic.doctor", ("user_id",)),
    ),
    "DEMO-USER-MGR": (
        ("DEMO-STAFF-MGR", "clinic.staff", ("name",)),
    ),
}


class AdvancedClinicalBase(BaseDemoGenerator):
    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0,
                "skipped": 0, "warning": 0, "error": 0}

    def _resolve(self, ctx, key, model, missing_ok=False, record_user=None):
        # Validation and prerequisite reads must use the same functional actor
        # as creation. Resolve from verified run provenance, never ACL retries.
        if record_user is None:
            reference = ctx.reference_service._reference(ctx.run, key)
            if reference and actor_key(reference):
                record_user = read_model(ctx.run, reference).env.user
        record = ctx.reference_service.resolve(
            ctx.run, key, model, missing_ok=missing_ok, record_user=record_user,
        )
        if record and record_user:
            return self._as_actor(record, record_user).with_company(ctx.run.company_id).with_context(
                allowed_company_ids=[ctx.run.company_id.id],
            )
        return record

    @staticmethod
    def _as_actor(record, user):
        """Bind a record to one functional actor without broad field prefetch."""
        return record.with_user(user).with_context(**ADVANCED_ACTOR_CONTEXT)

    def _ensure(self, ctx, counters, key, model, values, scenario_key,
                reset_sequence, record_user=None):
        Model = ctx.env[model].with_company(ctx.run.company_id)
        if record_user:
            Model = self._as_actor(Model, record_user)

        def create():
            return Model.create(dict(values))

        record, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name=model,
            generator_key=self.key, scenario_key=scenario_key,
            create_callback=create, update_callback=None,
            reset_policy=RESET_FRESH_DB_ONLY,
            reset_sequence=reset_sequence, record_user=record_user,
        )
        if record_user:
            record = self._as_actor(record, record_user)
        counters[status if status in counters else "created"] += 1
        return record

    def _utc(self, ctx, offset, hour, minute=0):
        zone = pytz.timezone(ctx.run.timezone or "UTC")
        local = zone.localize(datetime.combine(
            ctx.run.anchor_date + timedelta(days=offset),
            time(hour=hour, minute=minute),
        ))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _doctor_actor(self, ctx):
        doctor = self._resolve(ctx, "DEMO-DOC-001", "clinic.doctor")
        if not doctor.user_id:
            raise UserError(_("Demo Doctor 001 has no linked clinical user."))
        return doctor, doctor.user_id

    def _reconcile_advanced_actor_entitlements(self, ctx):
        """Apply source-declared groups only to demo-owned functional actors.

        Prompt 09 is already frozen on a progressive run, so newly required
        Prompt-17 entitlements cannot be delegated to that completed generator.
        The change is bounded to synthetic users and occurs before clinical
        business records are written.
        """
        for key, xmlids in ADVANCED_ACTOR_GROUPS.items():
            user = self._resolve(ctx, key, "res.users")
            groups = ctx.env["res.groups"]
            for xmlid in xmlids:
                groups |= ctx.env.ref(xmlid)
            missing = groups - user.group_ids
            if missing:
                user.write({"group_ids": [(4, group.id) for group in missing]})

    def _preflight_all_advanced_paths(self, ctx):
        """Fail before the first Prompt-17 write if any downstream contract drifted."""
        issues = []
        for model_name, contract in ADVANCED_RUNTIME_CONTRACTS.items():
            Model = ctx.env[model_name]
            missing_fields = sorted(contract["fields"] - set(Model._fields))
            missing_methods = sorted(
                name for name in contract["methods"] if not hasattr(Model, name)
            )
            if missing_fields:
                issues.append(f"{model_name} missing fields: {', '.join(missing_fields)}")
            if missing_methods:
                issues.append(f"{model_name} missing methods: {', '.join(missing_methods)}")
        for (model_name, field_name), expected in ADVANCED_RELATION_CONTRACTS.items():
            field = ctx.env[model_name]._fields.get(field_name)
            actual = getattr(field, "comodel_name", None) if field else None
            if actual != expected:
                issues.append(
                    f"{model_name}.{field_name} comodel is {actual or 'missing'}, "
                    f"expected {expected}"
                )

        for key, groups in ADVANCED_ACTOR_GROUPS.items():
            user = self._resolve(ctx, key, "res.users", missing_ok=True)
            if not user:
                issues.append(f"required actor {key} is missing")
                continue
            for group in groups:
                if not user.has_group(group):
                    issues.append(f"{key} lacks {group}")

        for actor_key, model_operations in ADVANCED_ACCESS_CONTRACTS.items():
            user = self._resolve(ctx, actor_key, "res.users", missing_ok=True)
            if not user:
                continue
            for model_name, operations in model_operations.items():
                Model = ctx.env[model_name].with_user(user).browse()
                for mode in operations:
                    try:
                        Model.check_access(mode)
                    except Exception as error:
                        issues.append(f"{actor_key} cannot {mode} {model_name}: {error}")

        for actor_key, read_contracts in ADVANCED_FIELD_READ_CONTRACTS.items():
            user = self._resolve(ctx, actor_key, "res.users", missing_ok=True)
            if not user:
                continue
            for reference_key, model_name, field_names in read_contracts:
                record = self._resolve(
                    ctx, reference_key, model_name, missing_ok=True,
                    record_user=user,
                )
                if not record:
                    issues.append(
                        f"required field-read reference {reference_key} is missing"
                    )
                    continue
                try:
                    record.read(list(field_names))
                except Exception as error:
                    issues.append(
                        f"{actor_key} cannot read {model_name} fields "
                        f"{', '.join(field_names)}: {error}"
                    )

        prerequisites = (
            ("DEMO-PAT-IMG-001", "clinic.patient"),
            ("DEMO-PAT-CHRON-001", "clinic.patient"),
            ("DEMO-PAT-TELE-001", "clinic.patient"),
            ("DEMO-IMTYPE-XR-CHEST-PA", "clinical.imaging.type"),
            ("DEMO-PRODUCT-MED-PARA-500", "product.product"),
            ("DEMO-MED-PROFILE-PARA-500", "clinic.emar.medication.profile"),
            ("DEMO-PROTOCOL-CARE-RECOVERY", "clinic.care.protocol"),
            ("DEMO-CONSENT-TPL-GENERAL", "clinic.consent.template"),
            ("DEMO-CONSENT-TPL-TELE", "clinic.consent.template"),
            ("DEMO-TREAT-TELE-CONSULT", "clinic.treatment"),
            ("DEMO-ROOM-B001-IMG-01", "clinic.room"),
        )
        for key, model in prerequisites:
            if not self._resolve(ctx, key, model, missing_ok=True):
                issues.append(f"required provenance reference {key} ({model}) is missing")
        doctor = self._resolve(ctx, "DEMO-DOC-001", "clinic.doctor", missing_ok=True)
        care_protocol = self._resolve(
            ctx, "DEMO-PROTOCOL-CARE-RECOVERY", "clinic.care.protocol", missing_ok=True,
        )
        manager_staff = self._resolve(
            ctx, "DEMO-STAFF-MGR", "clinic.staff", missing_ok=True,
        )
        for key in ("DEMO-CONSENT-TPL-GENERAL", "DEMO-CONSENT-TPL-TELE"):
            template = self._resolve(ctx, key, "clinic.consent.template", missing_ok=True)
            if template and template.state != "published":
                issues.append(f"{key} must be Published before Prompt-17 execution")
        if doctor:
            if not doctor.user_id:
                issues.append("DEMO-DOC-001 has no linked clinical user")
            if not doctor.telemedicine_enabled:
                issues.append("DEMO-DOC-001 is not enabled for Telemedicine")
            if doctor.company_id != ctx.run.company_id:
                issues.append("DEMO-DOC-001 belongs to another company")
        if care_protocol:
            if care_protocol.company_id != ctx.run.company_id:
                issues.append("DEMO-PROTOCOL-CARE-RECOVERY belongs to another company")
            if care_protocol.version_state != "published":
                issues.append("DEMO-PROTOCOL-CARE-RECOVERY must be Published")
            if not care_protocol.step_ids:
                issues.append("DEMO-PROTOCOL-CARE-RECOVERY has no protocol steps")
        if manager_staff and manager_staff.company_id != ctx.run.company_id:
            issues.append("DEMO-STAFF-MGR belongs to another company")
        if issues:
            raise UserError(_(
                "MASTER PROMPT 17 whole-path runtime preflight failed: %s"
            ) % "; ".join(issues))
        return True

    def _prepare_advanced_runtime(self, ctx):
        """Reconcile and preflight the entire Prompt-17 path at every stage."""
        self._reconcile_advanced_actor_entitlements(ctx)
        prepare_telemedicine_scope(ctx.run, optional=True)
        return self._preflight_all_advanced_paths(ctx)

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}


@GENERATOR_REGISTRY.register
class AdvancedImagingGenerator(AdvancedClinicalBase):
    key = "clinical.imaging"
    phase = "17_advanced"
    sequence = 710
    depends_on = ("operations.treatment_session",)
    scenario_keys = ("SCN-IMAGING-01",)
    owned_models = ("clinical.imaging.device", "clinical.imaging")
    required_groups = ("base.group_user",)

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._prepare_advanced_runtime(ctx)
        patient = self._resolve(ctx, "DEMO-PAT-IMG-001", "clinic.patient")
        imaging_type = self._resolve(
            ctx, "DEMO-IMTYPE-XR-CHEST-PA", "clinical.imaging.type"
        )
        _doctor, user = self._doctor_actor(ctx)
        employee = self._resolve(ctx, "DEMO-EMP-DOC-001", "hr.employee")
        room = self._resolve(ctx, "DEMO-ROOM-B001-IMG-01", "clinic.room")
        device = self._ensure(ctx, counters, "DEMO-IMG-DEVICE-001",
            "clinical.imaging.device", {
                "name": "Synthetic Digital Imaging Workstation",
                "code": "DEMO-DX-01", "company_id": ctx.run.company_id.id,
                "modality": "DX", "manufacturer": "DemoImage",
                "model_name": "DX-1", "serial_number": "SYN-DX-0001",
                "room_id": room.id, "status": "operational", "active": True,
            }, "SCN-IMAGING-01", 915, record_user=user)
        scheduled = self._utc(ctx, 1, 10)
        imaging = self._ensure(ctx, counters, "DEMO-IMG-001", "clinical.imaging", {
            "name": "DEMO-IMG-001",
            "company_id": ctx.run.company_id.id,
            "patient_id": patient.partner_id.id,
            "doctor_id": employee.id,
            "imaging_type_id": imaging_type.id,
            "device_id": device.id,
            "request_datetime": self._utc(ctx, 0, 9),
            "scheduled_datetime": scheduled,
            "expected_done_datetime": scheduled + timedelta(hours=2),
            "performed_datetime": scheduled + timedelta(minutes=30),
            "reviewed_datetime": scheduled + timedelta(minutes=45),
            "clinical_indication": "Synthetic chest imaging assessment.",
            "findings_summary": "Synthetic clear diagnostic-quality study.",
            "recommendations": "Synthetic routine clinical follow-up.",
        }, "SCN-IMAGING-01", 920, record_user=user)
        actor = self._as_actor(imaging, user)
        for state, method in (("draft", "action_request"),
                              ("requested", "action_schedule"),
                              ("scheduled", "action_start"),
                              ("in_progress", "action_complete"),
                              ("completed", "action_review")):
            if imaging.state == state:
                getattr(actor, method)()
        return counters

    def validate(self, ctx, scenario):
        rec = self._resolve(ctx, "DEMO-IMG-001", "clinical.imaging", True)
        return [] if rec and rec.state == "reviewed" and rec.device_id and rec.device_id.room_id else [
            "DEMO-IMG-001 must exist in Reviewed state."
        ]


@GENERATOR_REGISTRY.register
class AdvancedEmarGenerator(AdvancedClinicalBase):
    key = "clinical.emar"
    phase = "17_advanced"
    sequence = 720
    depends_on = ("clinical.imaging",)
    scenario_keys = ("SCN-EMAR-01",)
    owned_models = ("clinic.emar.prescription", "clinic.emar.medication.line",
                    "clinic.emar.order", "clinic.emar.administration")
    required_groups = ("clinic_emar.group_emar_prescriber",)

    def _line_values(self, ctx, patient, doctor, product, profile, **header):
        values = {
            "company_id": ctx.run.company_id.id, "patient_id": patient.id,
            "doctor_id": doctor.id, "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "dose_uom_id": product.uom_id.id, "profile_id": profile.id,
            "name": "Synthetic oral medication instruction", "quantity": 1.0,
            "dose": 1.0, "frequency": "prn", "route": "oral",
            "duration_count": 7, "duration_unit": "day", "is_billable": False,
        }
        values.update(header)
        return values

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._prepare_advanced_runtime(ctx)
        patient = self._resolve(ctx, "DEMO-PAT-CHRON-001", "clinic.patient")
        doctor, doctor_user = self._doctor_actor(ctx)
        doctor_employee = self._resolve(ctx, "DEMO-EMP-DOC-001", "hr.employee")
        nurse_user = self._resolve(ctx, "DEMO-USER-NUR-001", "res.users")
        manager_user = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        product = self._resolve(ctx, "DEMO-PRODUCT-MED-PARA-500", "product.product")
        profile = self._resolve(ctx, "DEMO-MED-PROFILE-PARA-500",
                                "clinic.emar.medication.profile")
        start = self._utc(ctx, 0, 11)
        prescription = self._ensure(ctx, counters, "DEMO-EMAR-RX-001",
            "clinic.emar.prescription", {
                "name": "DEMO-EMAR-RX-001",
                "company_id": ctx.run.company_id.id, "patient_id": patient.id,
                "doctor_id": doctor.id,
                "diagnosis": "Synthetic recurring-care symptom management.",
                "date_start": start, "date_end": start + timedelta(days=7),
            }, "SCN-EMAR-01", 950, record_user=doctor_user)
        self._ensure(ctx, counters, "DEMO-EMAR-RX-LINE-001",
            "clinic.emar.medication.line",
            self._line_values(ctx, patient, doctor, product, profile,
                              prescription_id=prescription.id),
            "SCN-EMAR-01", 955, record_user=doctor_user)
        actor_rx = self._as_actor(prescription, doctor_user)
        if prescription.state == "draft":
            actor_rx.action_validate()
        if prescription.state == "validated":
            actor_rx.action_activate()

        order = self._ensure(ctx, counters, "DEMO-EMAR-ORDER-001",
            "clinic.emar.order", {
                "name": "DEMO-EMAR-ORDER-001",
                "company_id": ctx.run.company_id.id,
                "patient_id": patient.partner_id.id,
                "clinic_patient_id": patient.id,
                "doctor_id": doctor_employee.id,
                "clinic_doctor_id": doctor.id,
                "partner_id": patient.partner_id.id,
                "payer_partner_id": patient.partner_id.id,
                "prescription_id": prescription.id,
                "date_start": start, "date_end": start + timedelta(days=7),
            }, "SCN-EMAR-01", 960, record_user=doctor_user)
        order_line = self._ensure(ctx, counters, "DEMO-EMAR-ORDER-LINE-001",
            "clinic.emar.medication.line",
            self._line_values(ctx, patient, doctor, product, profile,
                              order_id=order.id),
            "SCN-EMAR-01", 965, record_user=doctor_user)
        if order.state == "draft":
            # Owner configuration may auto-create schedules. The synthetic
            # eMAR Manager has the exact schedule permission for either policy.
            self._as_actor(order, manager_user).action_confirm()
        actor_order = self._as_actor(order, doctor_user)
        for state, method in (("confirmed", "action_approve"),
                              ("approved", "action_activate")):
            if order.state == state:
                getattr(actor_order, method)()

        deterministic_barcode = "CLINICONE-DEMO-MED-PARA-500"
        barcode_owner = ctx.env["product.product"].search([
            ("barcode", "=", deterministic_barcode), ("id", "!=", product.id),
        ], limit=1)
        if barcode_owner:
            raise UserError(_(
                "Deterministic medication barcode %(barcode)s is already owned by %(product)s."
            ) % {"barcode": deterministic_barcode, "product": barcode_owner.display_name})
        if product.barcode != deterministic_barcode:
            product.write({"barcode": deterministic_barcode})
        admin = self._ensure(ctx, counters, "DEMO-EMAR-ADMIN-001",
            "clinic.emar.administration", {
                "name": "DEMO-EMAR-ADMIN-001",
                "company_id": ctx.run.company_id.id, "order_id": order.id,
                "line_id": order_line.id, "product_id": product.id,
                "dose_qty": 1.0, "administered_qty": 1.0,
                "dose_uom_id": product.uom_id.id, "inventory_qty": 0.0,
                "patient_scan_code": patient.emar_barcode,
                "product_scan_code": product.barcode,
                "notes": "Synthetic administration; billing and stock deferred.",
            }, "SCN-EMAR-01", 970, record_user=nurse_user)
        actor_admin = self._as_actor(admin, nurse_user)
        if admin.state == "draft":
            actor_admin.action_confirm()
        if admin.state == "confirmed":
            actor_admin.action_start()
        if admin.state == "in_progress":
            actor_admin.action_done(consume_inventory=False, create_invoice=False)
        return counters

    def validate(self, ctx, scenario):
        order = self._resolve(ctx, "DEMO-EMAR-ORDER-001", "clinic.emar.order", True)
        admin = self._resolve(ctx, "DEMO-EMAR-ADMIN-001", "clinic.emar.administration", True)
        issues = []
        if not order or order.state != "active" or not order.line_ids:
            issues.append("The demo eMAR Order must be Active with medication lines.")
        if not admin or admin.state != "done":
            issues.append("The demo eMAR Administration must be Done.")
        return issues


@GENERATOR_REGISTRY.register
class AdvancedCarePostcareGenerator(AdvancedClinicalBase):
    key = "clinical.care_postcare"
    phase = "17_advanced"
    sequence = 730
    depends_on = ("clinical.emar",)
    scenario_keys = ("SCN-CARE-01",)
    owned_models = ("clinic.consent.form", "clinic.care.plan",
                    "clinic.postcare.protocol", "clinic.postcare.plan")
    required_groups = ("clinic_post_care_followup.group_postcare_manager",)

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._prepare_advanced_runtime(ctx)
        patient = self._resolve(ctx, "DEMO-PAT-CHRON-001", "clinic.patient")
        protocol = self._resolve(ctx, "DEMO-PROTOCOL-CARE-RECOVERY",
                                 "clinic.care.protocol")
        consent_template = self._resolve(
            ctx, "DEMO-CONSENT-TPL-GENERAL", "clinic.consent.template",
        )
        doctor, doctor_user = self._doctor_actor(ctx)
        manager_user = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        manager_staff = self._resolve(ctx, "DEMO-STAFF-MGR", "clinic.staff")
        consent = self._ensure(ctx, counters, "DEMO-CONSENT-CARE-SIGNED-001",
            "clinic.consent.form", {
                "name": "DEMO-CONSENT-CARE-001",
                "company_id": ctx.run.company_id.id,
                "patient_id": patient.partner_id.id,
                "doctor_id": doctor.id,
                "template_id": consent_template.id,
                "title": "Synthetic Confidential Care Plan Consent",
                "content_text": (
                    "Synthetic consent for confidential recurring-care planning "
                    "and governed clinical coordination."
                ),
                "required_before_procedure": False,
                "validity_days": 365,
            }, "SCN-CARE-01", 972, record_user=doctor_user)
        actor_consent = self._as_actor(consent, doctor_user)
        if consent.state == "draft":
            actor_consent.action_set_to_sign()
        if consent.state == "to_sign":
            actor_consent.action_sign(
                signer_name=patient.partner_id.name,
                signature_binary=base64.b64encode(b"synthetic-care-consent-signature"),
                signer_relationship="self", user_agent="ClinicOne Demo",
                signed_dt=self._utc(ctx, 0, 9),
            )
        care = self._ensure(ctx, counters, "DEMO-CARE-PLAN-001",
            "clinic.care.plan", {
                "name": "DEMO-CARE-PLAN-001",
                "display_name": "Synthetic recurring recovery care plan",
                "plan_type": "chronic", "company_id": ctx.run.company_id.id,
                "patient_id": patient.id, "protocol_template_id": protocol.id,
                "doctor_id": doctor.id, "start_date": ctx.run.anchor_date,
                "end_date": ctx.run.anchor_date + timedelta(days=30),
                "is_confidential": True, "consent_id": consent.id,
                "diagnosis_summary": "Synthetic recurring-care progress scenario.",
                "currency_id": ctx.run.company_id.currency_id.id,
            }, "SCN-CARE-01", 975, record_user=doctor_user)
        actor_care = self._as_actor(care, doctor_user)
        if care.state == "draft":
            if care.consent_id != consent or not care.is_confidential:
                actor_care.write({"is_confidential": True, "consent_id": consent.id})
            actor_care.action_generate_lines_from_protocol()
            actor_care.action_activate()

        post_protocol = self._ensure(ctx, counters, "DEMO-POSTCARE-PROTOCOL-001",
            "clinic.postcare.protocol", {
                "name": "Synthetic Recurring Recovery Follow-up",
                "code": "DEMO-RECOVERY", "company_id": ctx.run.company_id.id,
                "care_protocol_id": protocol.id,
                "default_assignee_id": manager_staff.id,
                "default_duration_days": 14, "auto_generate_tasks": False,
                "instruction_html": "<p>Synthetic recovery instructions.</p>",
            }, "SCN-CARE-01", 980, record_user=manager_user)
        if post_protocol.state == "draft":
            self._as_actor(post_protocol, manager_user).action_activate()
        post = self._ensure(ctx, counters, "DEMO-POSTCARE-PLAN-001",
            "clinic.postcare.plan", {
                "name": "DEMO-POSTCARE-PLAN-001",
                "company_id": ctx.run.company_id.id, "patient_id": patient.id,
                "doctor_id": doctor.id, "responsible_staff_id": manager_staff.id,
                "protocol_id": post_protocol.id, "source_type": "care_plan",
                "care_plan_id": care.id, "start_datetime": self._utc(ctx, 0, 16),
                "expected_end_date": ctx.run.anchor_date + timedelta(days=14),
            }, "SCN-CARE-01", 985, record_user=manager_user)
        if post.state == "draft":
            self._as_actor(post, manager_user).action_activate()
        return counters

    def validate(self, ctx, scenario):
        care = self._resolve(ctx, "DEMO-CARE-PLAN-001", "clinic.care.plan", True)
        post = self._resolve(ctx, "DEMO-POSTCARE-PLAN-001", "clinic.postcare.plan", True)
        issues = []
        if not care or care.state != "active" or not care.line_ids:
            issues.append("The demo Care Plan must be Active with activities.")
        if not care or not care.is_confidential or not care.consent_id or care.consent_id.state != "signed":
            issues.append("The confidential demo Care Plan must retain its Signed Consent.")
        if not post or post.state != "active":
            issues.append("The demo Post-Care Plan must be Active.")
        return issues


@GENERATOR_REGISTRY.register
class AdvancedTelemedicineGenerator(AdvancedClinicalBase):
    key = "clinical.telemedicine"
    phase = "17_advanced"
    sequence = 740
    depends_on = ("clinical.care_postcare",)
    scenario_keys = ("SCN-TELE-01",)
    owned_models = ("clinic.consent.form", "clinic.telemedicine.session",
                    "clinic.telemedicine.thread", "clinic.telemedicine.message")
    required_groups = ("clinic_telemedicine_secure_messaging.group_telemedicine_clinician",)

    def generate(self, ctx, scenario):
        counters = self._counters()
        self._prepare_advanced_runtime(ctx)
        patient = self._resolve(ctx, "DEMO-PAT-TELE-001", "clinic.patient")
        doctor, user = self._doctor_actor(ctx)
        treatment = self._resolve(ctx, "DEMO-TREAT-TELE-CONSULT", "clinic.treatment")
        template = self._resolve(ctx, "DEMO-CONSENT-TPL-TELE",
                                 "clinic.consent.template")
        consent = self._ensure(ctx, counters, "DEMO-CONSENT-TELE-SIGNED-001",
            "clinic.consent.form", {
                "name": "DEMO-CONSENT-TELE-001",
                "company_id": ctx.run.company_id.id,
                "patient_id": patient.partner_id.id, "doctor_id": doctor.id,
                "treatment_id": treatment.id, "template_id": template.id,
                "title": "Synthetic Telemedicine Consent",
                "content_text": "Synthetic telemedicine consent for demonstration.",
                "required_before_procedure": True,
            }, "SCN-TELE-01", 990, record_user=user)
        actor_consent = self._as_actor(consent, user)
        if consent.state == "draft":
            actor_consent.action_set_to_sign()
        if consent.state == "to_sign":
            actor_consent.action_sign(
                signer_name=patient.partner_id.name,
                signature_binary=base64.b64encode(b"synthetic-signature"),
                signer_relationship="self", user_agent="ClinicOne Demo",
                signed_dt=self._utc(ctx, 0, 8),
            )
        start = self._utc(ctx, 1, 13)
        session = self._ensure(ctx, counters, "DEMO-TELE-SESSION-001",
            "clinic.telemedicine.session", {
                "name": "DEMO-TELE-SESSION-001",
                "company_id": ctx.run.company_id.id,
                "branch_id": prepare_telemedicine_scope(ctx.run).id if patient.partner_id.branch_id else False,
                "patient_id": patient.id, "doctor_id": doctor.id,
                "consent_form_id": consent.id, "scheduled_start": start,
                "scheduled_end": start + timedelta(minutes=30),
                "provider_mode": "manual_url",
                "meeting_url": "https://meet.clinicone.invalid/demo-session-001",
            }, "SCN-TELE-01", 995, record_user=user)
        thread = self._ensure(ctx, counters, "DEMO-TELE-THREAD-001",
            "clinic.telemedicine.thread", {
                "name": "DEMO-TELE-THREAD-001",
                "company_id": ctx.run.company_id.id,
                "branch_id": session.branch_id.id if session.branch_id else False,
                "session_id": session.id,
                "patient_id": patient.id,
                "doctor_id": doctor.id,
                "subject": "Synthetic secure teleconsultation conversation",
            }, "SCN-TELE-01", 998, record_user=user)
        actor_session = self._as_actor(session, user)
        if session.state == "draft":
            actor_session.action_schedule()
        if session.state == "scheduled":
            actor_session.action_mark_ready()
        if thread not in session.thread_ids:
            raise UserError(_("Telemedicine workflow did not create its Secure Thread."))
        message = self._resolve(ctx, "DEMO-TELE-MESSAGE-001",
                                "clinic.telemedicine.message", True, user)
        if not message:
            message = self._as_actor(
                ctx.env["clinic.telemedicine.message"], user,
            ).create({
                "thread_id": thread.id,
                "body": "Synthetic secure pre-visit instruction from the clinical team.",
                "sent_at": self._utc(ctx, 0, 8, 30),
            })
            ctx.reference_service.bind(
                run=ctx.run, demo_key="DEMO-TELE-MESSAGE-001", record=message,
                generator_key=self.key, scenario_key="SCN-TELE-01",
                ownership_kind="created", reset_policy=RESET_FRESH_DB_ONLY,
                reset_sequence=999, record_user=user,
            )
            counters["created"] += 1
        else:
            counters["reused"] += 1
        return counters

    def validate(self, ctx, scenario):
        consent = self._resolve(ctx, "DEMO-CONSENT-TELE-SIGNED-001",
                                "clinic.consent.form", True)
        session = self._resolve(ctx, "DEMO-TELE-SESSION-001",
                                "clinic.telemedicine.session", True)
        message = self._resolve(ctx, "DEMO-TELE-MESSAGE-001",
                                "clinic.telemedicine.message", True)
        issues = []
        if not consent or consent.state != "signed":
            issues.append("Telemedicine Consent must be Signed.")
        if not session or session.state != "ready" or not session.thread_ids:
            issues.append("Telemedicine Session must be Ready with a Secure Thread.")
        if not message or not message.body:
            issues.append("Secure Message evidence is missing.")
        return issues
























