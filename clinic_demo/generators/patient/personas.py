
"""Deterministic Patient Master & Persona Engine for MASTER PROMPT 10."""

from datetime import datetime, time, timedelta

import pytz

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_DEACTIVATE, RESET_DELETE_SAFE
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.scenario_registry import ScenarioRegistry


CORE_PERSONAS = (
    {
        "code": "NEW-001", "name": "Anindya Larasati", "gender": "female", "age": 29,
        "branch": 1, "registered_days": 0, "stage": "new",
        "tags": ("New Patient", "Adult", "Booking Ready"),
        "journeys": ("SCN-PATIENT-NEW-01", "SCN-BOOKING-TODAY-01", "SCN-ENCOUNTER-01"),
    },
    {
        "code": "RET-001", "name": "Bagas Wiratama", "gender": "male", "age": 42,
        "branch": 1, "registered_days": 540, "stage": "registered",
        "tags": ("Returning Patient", "Adult", "Longitudinal History"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-ENCOUNTER-RET-01"),
    },
    {
        "code": "ELDER-001", "name": "Ratna Prameswari", "gender": "female", "age": 69,
        "branch": 2, "registered_days": 800, "stage": "registered",
        "tags": ("Returning Patient", "Elderly", "Long-term Care"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-CARE-01"),
    },
    {
        "code": "PED-001", "name": "Nara Aditya", "gender": "male", "age": 11,
        "branch": 2, "registered_days": 180, "stage": "registered",
        "tags": ("Returning Patient", "Pediatric", "Family Care"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-BOOKING-TODAY-01"),
    },
    {
        "code": "CHRON-001", "name": "Sari Maheswari", "gender": "female", "age": 55,
        "branch": 3, "registered_days": 900, "stage": "registered",
        "tags": ("Returning Patient", "Chronic Care", "Long-term Care"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-CARE-01", "SCN-EMAR-01"),
        "condition": True,
    },
    {
        "code": "FREQ-001", "name": "Dimas Arjuno", "gender": "male", "age": 37,
        "branch": 1, "registered_days": 700, "stage": "registered",
        "tags": ("Returning Patient", "High Frequency", "Operational Trend"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-BOOKING-HIST-01", "SCN-REPORT-01"),
    },
    {
        "code": "PKG-001", "name": "Keisha Maharani", "gender": "female", "age": 32,
        "branch": 2, "registered_days": 365, "stage": "registered",
        "tags": ("Returning Patient", "Package", "Treatment Session"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-PACKAGE-01", "SCN-SESSION-01"),
    },
    {
        "code": "IMG-001", "name": "Banyu Mahardika", "gender": "male", "age": 46,
        "branch": 3, "registered_days": 420, "stage": "registered",
        "tags": ("Returning Patient", "Imaging", "Clinical Safety"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-IMAGING-01"),
        "imaging": True,
    },
    {
        "code": "EMAR-001", "name": "Tania Prameswari", "gender": "female", "age": 39,
        "branch": 1, "registered_days": 500, "stage": "registered",
        "tags": ("Returning Patient", "Medication / eMAR", "Allergy Safety"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-EMAR-01"),
        "allergy": True,
    },
    {
        "code": "TELE-001", "name": "Ari Purnama", "gender": "other", "age": 34,
        "branch": 2, "registered_days": 280, "stage": "registered",
        "tags": ("Returning Patient", "Telemedicine", "Portal Ready"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-TELE-01"),
        "telemedicine": True,
    },
    {
        "code": "MEM-001", "name": "Mira Adiningsih", "gender": "female", "age": 44,
        "branch": 1, "registered_days": 620, "stage": "registered",
        "tags": ("Returning Patient", "Membership", "Commercial"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-MEMBERSHIP-01"),
        "membership": True,
    },
    {
        "code": "INS-001", "name": "Agung Prasetya", "gender": "male", "age": 51,
        "branch": 3, "registered_days": 460, "stage": "registered",
        "tags": ("Returning Patient", "Insurance", "Receivable"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-INSURANCE-01", "SCN-AR-01"),
        "insurance": True,
    },
    {
        "code": "INC-001", "name": "Livia Permata", "gender": "female", "age": 27,
        "branch": 2, "registered_days": 210, "stage": "registered",
        "tags": ("Returning Patient", "Incident", "Quality"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-INCIDENT-01", "SCN-QUALITY-01"),
    },
    {
        "code": "NOSHOW-001", "name": "Fajar Santosa", "gender": "male", "age": 35,
        "branch": 1, "registered_days": 330, "stage": "registered",
        "tags": ("Returning Patient", "No-show / Cancel", "Service Recovery"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-SESSION-02", "SCN-FEEDBACK-01"),
    },
    {
        "code": "VIP-001", "name": "Selma Nirmala", "gender": "female", "age": 48,
        "branch": 2, "registered_days": 760, "stage": "registered",
        "tags": ("Returning Patient", "VIP", "Wallet"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-WALLET-01", "SCN-BILLING-01"),
        "vip": True,
    },
    {
        "code": "REF-001", "name": "Rafi Kurniawan", "gender": "male", "age": 30,
        "branch": 3, "registered_days": 60, "stage": "registered",
        "tags": ("Returning Patient", "Referral", "Acquisition"),
        "journeys": ("SCN-PATIENT-RET-01", "SCN-REFERRAL-01"),
    },
)

COHORT = (
    ("001", "Nadia Kartika", "female", 24), ("002", "Rangga Aditya", "male", 31),
    ("003", "Putri Mahardini", "female", 36), ("004", "Yoga Pranoto", "male", 40),
    ("005", "Celine Widyasari", "female", 28), ("006", "Arman Nugraha", "male", 53),
    ("007", "Tasya Kirana", "female", 22), ("008", "Bayu Wicaksana", "male", 47),
    ("009", "Dewi Paramita", "female", 57), ("010", "Gilang Pradana", "male", 26),
    ("011", "Intan Maheswari", "female", 33), ("012", "Reza Kurnia", "male", 61),
    ("013", "Vania Laras", "female", 19), ("014", "Hendra Wijaya", "male", 45),
    ("015", "Nayla Puspita", "female", 38), ("016", "Surya Adinata", "male", 66),
)

COHORT_COUNTS = {"compact": 0, "standard": 8, "full_enterprise": 16}
PROFILE_PATIENT_COUNTS = {
    "compact": len(CORE_PERSONAS),
    "standard": len(CORE_PERSONAS) + 8,
    "full_enterprise": len(CORE_PERSONAS) + 16,
}


@GENERATOR_REGISTRY.register
class PatientPersonaGenerator(BaseDemoGenerator):
    key = "patient.personas"
    phase = "10_patient"
    sequence = 310
    depends_on = ("workforce.staff",)
    scenario_keys = ("SCN-PATIENT-NEW-01", "SCN-PATIENT-RET-01")
    owned_models = (
        "res.partner", "clinic.patient", "clinic.patient.tag",
        "clinic.patient.identifier.type", "clinic.patient.identifier",
        "clinic.patient.condition", "clinic.patient.allergy",
    )
    required_groups = ("base.group_system",)

    def _counters(self):
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _ensure(
        self, ctx, counters, key, model, values, policy, reset_sequence,
        scenario_key=None, prepare_update=None,
    ):
        Model = ctx.env[model].with_company(ctx.run.company_id)
        existing_reference = ctx.reference_service._reference(ctx.run, key)

        def create():
            return Model.create(dict(values))

        def update_record(record):
            write_values = dict(values)
            if prepare_update:
                write_values = prepare_update(record, write_values)
            if write_values:
                record.write(write_values)

        record, reference, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=scenario_key or ctx.scenario.key,
            create_callback=create,
            update_callback=(
                None
                if existing_reference and existing_reference.ownership_kind == "reused"
                else update_record
            ),
            reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record, reference

    def _preflight(self, ctx):
        required_partner_fields = {
            "branch_id", "is_patient", "patient_id", "nik", "bpjs_no",
            "allow_portal_booking", "consent_portal_opt_out", "billing_policy",
            "pacs_patient_id", "dicom_patient_id", "contrast_allergy",
            "contrast_allergy_severity", "imaging_portal_opt_out", "share_images_on_portal",
        }
        required_patient_fields = {
            "patient_code", "partner_id", "company_id", "active", "gender",
            "birth_date", "registered_date", "stage_id", "tag_ids", "is_vip",
            "emar_barcode", "identifier_ids",
        }
        required_identifier_fields = {"patient_id", "type_id", "value", "is_primary", "active"}
        required_identifier_type_fields = {
            "name", "code", "active", "is_mrn", "is_national_id",
            "is_insurance_member", "partner_mapping",
        }
        missing_partner = sorted(required_partner_fields - set(ctx.env["res.partner"]._fields))
        missing_patient = sorted(required_patient_fields - set(ctx.env["clinic.patient"]._fields))
        missing_identifier = sorted(
            required_identifier_fields - set(ctx.env["clinic.patient.identifier"]._fields)
        )
        missing_identifier_type = sorted(
            required_identifier_type_fields
            - set(ctx.env["clinic.patient.identifier.type"]._fields)
        )
        if missing_partner or missing_patient or missing_identifier or missing_identifier_type:
            raise UserError(_(
                "MASTER PROMPT 10 preflight failed. Missing source fields — "
                "res.partner: %(partner)s; clinic.patient: %(patient)s"
            ) % {
                "partner": ", ".join(missing_partner) or "-",
                "patient": ", ".join(missing_patient) or "-",
            } + (
                " Identifier fields: %(identifier)s; identifier-type fields: %(identifier_type)s"
                % {
                    "identifier": ", ".join(missing_identifier) or "-",
                    "identifier_type": ", ".join(missing_identifier_type) or "-",
                }
            ))

        sequence = ctx.env["ir.sequence"].search([
            ("code", "=", "clinic_patient.seq_patient_code")
        ], limit=1)
        if not sequence:
            raise UserError(_(
                "MASTER PROMPT 10 preflight failed: sequence "
                "clinic_patient.seq_patient_code is missing."
            ))

        for xmlid in ("clinic_patient.patient_stage_new", "clinic_patient.patient_stage_registered"):
            if not ctx.env.ref(xmlid, raise_if_not_found=False):
                raise UserError(_("MASTER PROMPT 10 preflight failed: missing %s.") % xmlid)

        for number in range(1, {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile] + 1):
            ctx.reference_service.resolve(
                ctx.run, f"DEMO-BRANCH-{number:03d}", "clinic.branch"
            )

        for spec in CORE_PERSONAS:
            for journey in spec["journeys"]:
                ScenarioRegistry.get(journey)

    def _branch(self, ctx, number):
        maximum = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        number = min(number, maximum)
        return ctx.reference_service.resolve(
            ctx.run, f"DEMO-BRANCH-{number:03d}", "clinic.branch"
        )

    @staticmethod
    def _birth_date(anchor, age, day_shift=0):
        target = anchor - timedelta(days=day_shift)
        try:
            return target.replace(year=target.year - age)
        except ValueError:
            return target.replace(month=2, day=28, year=target.year - age)

    @staticmethod
    def _slug(code):
        return code.lower().replace("-", ".")

    @staticmethod
    def _nik(index):
        return f"00000000{index:08d}"

    @staticmethod
    def _bpjs(index):
        return f"00000{index:08d}"

    def _registered_datetime(self, ctx, days):
        if not days:
            return False
        tz = pytz.timezone(ctx.run.timezone or "UTC")
        local = tz.localize(datetime.combine(ctx.run.anchor_date - timedelta(days=days), time(hour=9)))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _ensure_tag(self, ctx, counters, label):
        key = "DEMO-PAT-TAG-" + "".join(ch if ch.isalnum() else "-" for ch in label.upper()).strip("-")
        existing = ctx.env["clinic.patient.tag"].search([
            ("name", "=", f"ClinicOne Demo — {label}")
        ], limit=1)
        reference = ctx.reference_service._reference(ctx.run, key)
        if existing and not reference:
            ctx.reference_service.bind_reused(
                run=ctx.run,
                demo_key=key,
                record=existing,
                generator_key=self.key,
                scenario_key="SCN-PATIENT-RET-01",
                reset_policy=RESET_DELETE_SAFE,
                reset_sequence=300,
            )
            counters["reused"] += 1
            return existing

        tag, _ref = self._ensure(
            ctx, counters, key, "clinic.patient.tag",
            {"name": f"ClinicOne Demo — {label}"},
            RESET_DELETE_SAFE, 300, scenario_key="SCN-PATIENT-RET-01",
        )
        return tag

    def _ensure_identifier_type(self, ctx, counters, code, values):
        key = f"DEMO-PAT-IDTYPE-{code}"
        reference = ctx.reference_service._reference(ctx.run, key)
        if reference:
            record, _reference = self._ensure(
                ctx, counters, key, "clinic.patient.identifier.type",
                values, RESET_DEACTIVATE, 500, scenario_key="SCN-PATIENT-RET-01",
            )
            return record

        existing = ctx.env["clinic.patient.identifier.type"].search(
            [("code", "=", code)], limit=1
        )
        if existing:
            ctx.reference_service.bind_reused(
                run=ctx.run,
                demo_key=key,
                record=existing,
                generator_key=self.key,
                scenario_key="SCN-PATIENT-RET-01",
                reset_policy=RESET_DEACTIVATE,
                reset_sequence=500,
            )
            counters["reused"] += 1
            return existing

        record, _reference = self._ensure(
            ctx, counters, key, "clinic.patient.identifier.type",
            values, RESET_DEACTIVATE, 500, scenario_key="SCN-PATIENT-RET-01",
        )
        return record

    def _identifier_types(self, ctx, counters):
        return {
            "mrn": self._ensure_identifier_type(ctx, counters, "MRN", {
                "name": "Medical Record Number",
                "code": "MRN",
                "active": True,
                "sequence": 10,
                "is_mrn": True,
                "single_primary_per_patient": True,
                "partner_mapping": "ref",
                "barcode_symbology": "code128",
            }),
            "nik": self._ensure_identifier_type(ctx, counters, "NIK", {
                "name": "National ID (Synthetic NIK)",
                "code": "NIK",
                "active": True,
                "sequence": 20,
                "is_national_id": True,
                "single_primary_per_patient": True,
                "partner_mapping": "custom_nik",
                "barcode_symbology": "qrcode",
            }),
            "bpjs": self._ensure_identifier_type(ctx, counters, "BPJS", {
                "name": "Insurance Member ID (Synthetic BPJS)",
                "code": "BPJS",
                "active": True,
                "sequence": 30,
                "is_insurance_member": True,
                "single_primary_per_patient": True,
                "partner_mapping": "custom_bpjs",
                "barcode_symbology": "qrcode",
            }),
        }

    def _ensure_identifiers(self, ctx, counters, patient, spec, index, identifier_types):
        code = spec["code"]
        issue_date = (
            ctx.run.anchor_date - timedelta(days=spec["registered_days"])
            if spec["registered_days"]
            else ctx.run.anchor_date
        )
        values = (
            ("MRN", identifier_types["mrn"], patient.patient_code),
            ("NIK", identifier_types["nik"], self._nik(index)),
        )
        for label, identifier_type, value in values:
            self._ensure(
                ctx, counters, f"DEMO-PATID-{label}-{code}",
                "clinic.patient.identifier",
                {
                    "patient_id": patient.id,
                    "type_id": identifier_type.id,
                    "value": value,
                    "is_primary": True,
                    "active": True,
                    "issue_date": issue_date,
                    "issuing_authority": "ClinicOne Synthetic Demo Registry",
                    "notes": "Synthetic identifier for enterprise demo presentation only.",
                },
                RESET_DEACTIVATE, 850,
                scenario_key=(
                    "SCN-PATIENT-NEW-01" if spec["stage"] == "new"
                    else "SCN-PATIENT-RET-01"
                ),
            )

        if spec.get("insurance"):
            self._ensure(
                ctx, counters, f"DEMO-PATID-BPJS-{code}",
                "clinic.patient.identifier",
                {
                    "patient_id": patient.id,
                    "type_id": identifier_types["bpjs"].id,
                    "value": self._bpjs(index),
                    "is_primary": True,
                    "active": True,
                    "issue_date": issue_date,
                    "issuing_authority": "Synthetic Demo Payer Registry",
                    "notes": "Synthetic insurance member identifier; not a real BPJS number.",
                },
                RESET_DEACTIVATE, 850, scenario_key="SCN-PATIENT-RET-01",
            )

    def _partner_prepare_update(self, branch):
        def prepare(record, values):
            if record.branch_id == branch:
                values.pop("branch_id", None)
            return values
        return prepare

    @staticmethod
    def _patient_prepare_update(record, values):
        commands = values.get("tag_ids")
        if commands and commands[0][0] == 6:
            wanted = set(commands[0][2])
            values["tag_ids"] = [(6, 0, sorted(set(record.tag_ids.ids) | wanted))]
        return values

    def _persona_note(self, spec):
        journeys = ", ".join(spec["journeys"])
        tags = ", ".join(spec["tags"])
        return f"MASTER PROMPT 10 persona: {tags}. Reserved downstream journeys: {journeys}."

    def _ensure_persona(self, ctx, counters, spec, index, identifier_types):
        branch = self._branch(ctx, spec["branch"])
        code = spec["code"]
        slug = self._slug(code)
        is_new = spec["stage"] == "new"
        scenario_key = "SCN-PATIENT-NEW-01" if is_new else "SCN-PATIENT-RET-01"

        partner_values = {
            "name": spec["name"],
            "email": f"patient.{slug}@clinicone-demo.invalid",
            "phone": f"+62000247{index:04d}",
            "company_type": "person",
            "type": "contact",
            "active": True,
            "company_id": ctx.run.company_id.id,
            "branch_id": branch.id,
            "street": f"Synthetic Demo Residence {index:03d}",
            "city": branch.city or "Synthetic Demo City",
            "zip": branch.zip or "00000",
            "country_id": branch.country_id.id if branch.country_id else False,
            "nik": self._nik(index),
            "bpjs_no": self._bpjs(index) if spec.get("insurance") else False,
            "allow_portal_booking": True,
            "consent_portal_opt_out": False,
            "billing_policy": (
                "membership_only" if spec.get("membership")
                else "allow_credit" if spec.get("insurance")
                else "pay_now"
            ),
            "is_billing_blocked": False,
            "imaging_portal_opt_out": False,
            "share_images_on_portal": True,
        }
        if spec.get("imaging"):
            partner_values.update({
                "pacs_patient_id": f"DEMO-PACS-{code}",
                "dicom_patient_id": f"DEMO-DICOM-{code}",
                "contrast_allergy": True,
                "contrast_allergy_severity": "mild",
                "contrast_allergy_notes": "Synthetic demo history: mild prior contrast reaction.",
            })

        partner, _partner_ref = self._ensure(
            ctx, counters, f"DEMO-PAT-PARTNER-{code}", "res.partner",
            partner_values, RESET_DEACTIVATE, 650,
            scenario_key=scenario_key,
            prepare_update=self._partner_prepare_update(branch),
        )

        stage = ctx.env.ref(
            "clinic_patient.patient_stage_new" if is_new
            else "clinic_patient.patient_stage_registered"
        )
        tag_ids = [self._ensure_tag(ctx, counters, label).id for label in spec["tags"]]
        patient_values = {
            "name": spec["name"],
            "partner_id": partner.id,
            "company_id": ctx.run.company_id.id,
            "active": True,
            "gender": spec["gender"],
            "birth_date": self._birth_date(ctx.run.anchor_date, spec["age"], index % 17),
            "blood_type": ("A", "B", "AB", "O")[index % 4],
            "rh_factor": "-" if index % 7 == 0 else "+",
            "is_vip": bool(spec.get("vip")),
            "stage_id": stage.id,
            "registered_date": self._registered_datetime(ctx, spec["registered_days"]),
            "mobile": f"+62000991{index:04d}",
            "tag_ids": [(6, 0, tag_ids)],
            "emar_barcode": f"DEMO-EMAR-{code}",
        }
        patient, patient_ref = self._ensure(
            ctx, counters, f"DEMO-PAT-{code}", "clinic.patient",
            patient_values, RESET_DEACTIVATE, 700,
            scenario_key=scenario_key,
            prepare_update=self._patient_prepare_update,
        )
        patient_ref.write({
            "note": self._persona_note(spec),
            "business_reference": patient.patient_code or patient.display_name,
        })
        self._ensure_identifiers(ctx, counters, patient, spec, index, identifier_types)

        if spec.get("condition"):
            condition, condition_ref = self._ensure(
                ctx, counters, f"DEMO-PATCOND-{code}", "clinic.patient.condition",
                {
                    "patient_id": patient.id,
                    "condition_name": "Synthetic demo chronic hypertension history",
                    "status": "active",
                    "verification_status": "confirmed",
                    "severity": "mild",
                    "onset_date": ctx.run.anchor_date - timedelta(days=1100),
                    "last_review_date": ctx.run.anchor_date - timedelta(days=30),
                    "chronic_override": "force_chronic",
                    "active": True,
                    "notes": "Synthetic demo condition for longitudinal-care presentation only.",
                },
                RESET_DEACTIVATE, 900, scenario_key="SCN-PATIENT-RET-01",
            )
            condition_ref.note = "Synthetic patient condition; no real clinical data."

        if spec.get("allergy"):
            allergy, allergy_ref = self._ensure(
                ctx, counters, f"DEMO-PATALLERGY-{code}", "clinic.patient.allergy",
                {
                    "patient_id": patient.id,
                    "allergen_name": "Penicillin — synthetic demo",
                    "status": "active",
                    "verification_status": "confirmed",
                    "severity": "moderate",
                    "criticality": "low",
                    "reaction_summary": "Synthetic demo: prior rash.",
                    "recorded_date": self._registered_datetime(ctx, 365),
                    "onset_date": ctx.run.anchor_date - timedelta(days=730),
                    "last_occurrence_date": ctx.run.anchor_date - timedelta(days=700),
                    "source": "self_report",
                    "notes": "Synthetic allergy record for medication-safety presentation only.",
                },
                RESET_DELETE_SAFE, 910, scenario_key="SCN-PATIENT-RET-01",
            )
            allergy_ref.note = "Synthetic allergy; no real clinical data."

        return patient

    def _cohort_specs(self, ctx):
        count = COHORT_COUNTS[ctx.profile]
        specs = []
        for idx, (token, name, gender, age) in enumerate(COHORT[:count], 1):
            specs.append({
                "code": f"COHORT-{token}",
                "name": name,
                "gender": gender,
                "age": age,
                "branch": ((idx - 1) % {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]) + 1,
                "registered_days": 90 + (idx * 37),
                "stage": "registered",
                "tags": ("Returning Patient", "General Cohort"),
                "journeys": ("SCN-PATIENT-RET-01", "SCN-REPORT-01", "SCN-DASH-01"),
            })
        return specs

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        counters = self._counters()
        identifier_types = self._identifier_types(ctx, counters)
        specs = list(CORE_PERSONAS) + self._cohort_specs(ctx)
        for index, spec in enumerate(specs, 1):
            self._ensure_persona(ctx, counters, spec, index, identifier_types)
        return counters

    def validate(self, ctx, scenario):
        failures = []
        expected = PROFILE_PATIENT_COUNTS[ctx.profile]
        refs = ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id),
            ("generator_key", "=", self.key),
            ("model_name", "=", "clinic.patient"),
            ("record_status", "=", "bound"),
        ])
        patients = ctx.env["clinic.patient"].browse(refs.mapped("res_id")).exists()
        if len(patients) != expected:
            failures.append(f"Expected {expected} Prompt-10 patients, found {len(patients)}.")

        required_keys = {f"DEMO-PAT-{spec['code']}" for spec in CORE_PERSONAS}
        actual_keys = set(refs.mapped("demo_key"))
        missing_keys = sorted(required_keys - actual_keys)
        if missing_keys:
            failures.append("Missing core persona references: " + ", ".join(missing_keys))

        codes = patients.mapped("patient_code")
        if any(not code for code in codes) or len(codes) != len(set(codes)):
            failures.append("Patient business sequence codes are missing or duplicated.")

        for patient in patients:
            partner = patient.partner_id
            if not partner or not partner.is_patient or partner.patient_id != patient:
                failures.append(f"{patient.display_name}: partner/patient identity bridge is inconsistent.")
                continue
            if patient.company_id != ctx.run.company_id or partner.company_id != ctx.run.company_id:
                failures.append(f"{patient.display_name}: company scope is inconsistent.")
            if not partner.branch_id or partner.branch_id.company_id != ctx.run.company_id:
                failures.append(f"{patient.display_name}: branch assignment is missing or cross-company.")
            if not (partner.email or "").endswith("@clinicone-demo.invalid"):
                failures.append(f"{patient.display_name}: synthetic .invalid email contract failed.")
            if not (partner.street or "").startswith("Synthetic Demo Residence"):
                failures.append(f"{patient.display_name}: synthetic-address contract failed.")
            if not patient.emar_barcode:
                failures.append(f"{patient.display_name}: medication/eMAR patient identity is not ready.")
            identifier_codes = set(patient.identifier_ids.filtered("active").mapped("type_id.code"))
            if not {"MRN", "NIK"} <= identifier_codes:
                failures.append(
                    f"{patient.display_name}: stable MRN/NIK identifier foundation is incomplete."
                )

        new_patient = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-NEW-001", "clinic.patient")
        if not new_patient.stage_id.is_default_new or new_patient.registered_date:
            failures.append("New-patient persona is not in the source-defined New stage.")

        returning = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-RET-001", "clinic.patient")
        if not returning.stage_id.is_registered or not returning.registered_date:
            failures.append("Returning-patient persona is not source-valid registered history.")

        elderly = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-ELDER-001", "clinic.patient")
        pediatric = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-PED-001", "clinic.patient")
        if elderly.birth_date >= ctx.run.anchor_date - timedelta(days=60 * 365):
            failures.append("Elderly persona birth-date band is not demonstrated.")
        if pediatric.birth_date <= ctx.run.anchor_date - timedelta(days=18 * 366):
            failures.append("Pediatric persona birth-date band is not demonstrated.")

        chronic = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-CHRON-001", "clinic.patient")
        if not chronic.condition_ids.filtered(lambda record: record.status == "active" and record.is_chronic):
            failures.append("Chronic/long-term persona has no active chronic patient condition.")

        emar = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-EMAR-001", "clinic.patient")
        if not emar.allergy_ids.filtered(lambda record: record.status == "active"):
            failures.append("Medication/eMAR persona has no active allergy-safety context.")

        imaging = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-IMG-001", "clinic.patient").partner_id
        if not imaging.pacs_patient_id or not imaging.dicom_patient_id or not imaging.contrast_allergy:
            failures.append("Imaging persona lacks source-supported imaging safety/identity context.")

        tele = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-TELE-001", "clinic.patient").partner_id
        if not tele.allow_portal_booking or not tele.email:
            failures.append("Telemedicine persona is not portal/contact ready.")

        membership = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-MEM-001", "clinic.patient").partner_id
        if membership.billing_policy != "membership_only":
            failures.append("Membership persona billing policy is not membership-ready.")

        insurance = ctx.reference_service.resolve(ctx.run, "DEMO-PAT-INS-001", "clinic.patient").partner_id
        if not insurance.bpjs_no or insurance.billing_policy != "allow_credit":
            failures.append("Insurance persona lacks insurance/receivable-ready patient master context.")
        insurance_patient = ctx.reference_service.resolve(
            ctx.run, "DEMO-PAT-INS-001", "clinic.patient"
        )
        if "BPJS" not in set(insurance_patient.identifier_ids.filtered("active").mapped("type_id.code")):
            failures.append("Insurance persona lacks source-native BPJS identifier foundation.")

        if failures:
            raise UserError(_("MASTER PROMPT 10 validation failed:\n%s") % "\n".join(f"- {item}" for item in failures))
        return []

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return True


