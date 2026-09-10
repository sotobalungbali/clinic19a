




"""MASTER PROMPT 11 — source-driven clinical catalog and reusable clinical masters."""

from odoo import _, Command, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import (
    RESET_DEACTIVATE,
    RESET_DELETE_SAFE,
    RESET_FRESH_DB_ONLY,
)
from ...services.generator_registry import GENERATOR_REGISTRY


CATEGORY_SPECS = (
    ("CONSULT", "Consultation & Follow-up", 10),
    ("THERAPY", "Therapy & Recurring Care", 20),
    ("PROCEDURE", "Clinical Procedures", 30),
    ("IMAGING", "Diagnostic Imaging", 40),
    ("TELE", "Telemedicine & Remote Care", 50),
)

TREATMENT_SPECS = (
    {
        "code": "CONSULT-GEN", "name": "General Clinical Consultation",
        "category": "CONSULT", "duration": 30, "price": 250000,
        "minimum": 225000, "policy": "fixed", "online": True,
        "insurance": True,
    },
    {
        "code": "CONSULT-SPEC", "name": "Specialist Clinical Consultation",
        "category": "CONSULT", "duration": 45, "price": 450000,
        "minimum": 400000, "policy": "fixed", "online": True,
        "insurance": True,
    },
    {
        "code": "FOLLOW-UP", "name": "Clinical Follow-up Review",
        "category": "CONSULT", "duration": 20, "price": 180000,
        "minimum": 150000, "policy": "fixed", "online": True,
        "insurance": True,
    },
    {
        "code": "PHYSIO", "name": "Physiotherapy & Mobility Session",
        "category": "THERAPY", "duration": 60, "price": 350000,
        "minimum": 300000, "policy": "fixed", "online": True,
        "insurance": True,
    },
    {
        "code": "SKIN-PROC", "name": "Skin Rejuvenation Procedure",
        "category": "PROCEDURE", "duration": 60, "price": 850000,
        "minimum": 750000, "policy": "fixed", "online": False,
        "insurance": False,
        "consent_later": True,
    },
    {
        "code": "TELE-CONSULT", "name": "Telemedicine Consultation",
        "category": "TELE", "duration": 30, "price": 225000,
        "minimum": 200000, "policy": "fixed", "online": True,
        "insurance": True,
        "consent_later": True,
    },
    {
        "code": "IMG-XR", "name": "Chest X-Ray PA",
        "category": "IMAGING", "duration": 20, "price": 375000,
        "minimum": 350000, "policy": "fixed", "online": False,
        "insurance": True,
    },
    {
        "code": "IMG-US", "name": "Abdominal Ultrasound",
        "category": "IMAGING", "duration": 30, "price": 550000,
        "minimum": 500000, "policy": "fixed", "online": False,
        "insurance": True,
    },
    {
        "code": "IMG-MR", "name": "Brain MRI with Contrast",
        "category": "IMAGING", "duration": 60, "price": 2200000,
        "minimum": 2000000, "policy": "fixed", "online": False,
        "insurance": True,
        "consent_later": True,
    },
    {
        "code": "WELLNESS", "name": "Recurring Wellness Therapy",
        "category": "THERAPY", "duration": 45, "price": 325000,
        "minimum": 275000, "policy": "fixed", "online": True,
        "insurance": False,
    },
)

PROFILE_TREATMENT_COUNTS = {"compact": 8, "standard": 9, "full_enterprise": 10}

CARE_PROTOCOL_SPECS = (
    {
        "code": "CARE-RECOVERY", "title": "Recurring Recovery & Mobility Protocol",
        "category": "wellness", "risk": "low", "treatments": ("PHYSIO", "FOLLOW-UP"),
        "steps": (
            ("Initial Functional Review", "CONSULT-GEN", 30, 0, False),
            ("Therapy Session", "PHYSIO", 60, 1, False),
            ("Clinical Follow-up", "FOLLOW-UP", 20, 7, False),
        ),
    },
    {
        "code": "CARE-SKIN", "title": "Skin Rejuvenation Care Protocol",
        "category": "aesthetic", "risk": "moderate", "treatments": ("SKIN-PROC", "FOLLOW-UP"),
        "steps": (
            ("Pre-procedure Review", "CONSULT-SPEC", 30, 0, False),
            ("Skin Rejuvenation Procedure", "SKIN-PROC", 60, 7, True),
            ("Post-procedure Follow-up", "FOLLOW-UP", 20, 14, False),
        ),
    },
    {
        "code": "CARE-REMOTE", "title": "Remote Follow-up & Telemedicine Protocol",
        "category": "other", "risk": "low", "treatments": ("TELE-CONSULT", "FOLLOW-UP"),
        "steps": (
            ("Remote Clinical Review", "TELE-CONSULT", 30, 0, True),
            ("Follow-up Review", "FOLLOW-UP", 20, 14, False),
        ),
    },
)
PROFILE_PROTOCOL_COUNTS = {"compact": 1, "standard": 2, "full_enterprise": 3}

IMAGING_SPECS = (
    {
        "code": "XR-CHEST-PA", "name": "Chest X-Ray PA", "modality": "XR",
        "treatment": "IMG-XR", "duration": 20, "risk": "low",
        "pregnancy": True, "consent": False, "contrast": False,
    },
    {
        "code": "US-ABD", "name": "Abdominal Ultrasound", "modality": "US",
        "treatment": "IMG-US", "duration": 30, "risk": "low",
        "pregnancy": False, "consent": False, "contrast": False,
    },
    {
        "code": "MR-BRAIN-CE", "name": "Brain MRI with Contrast", "modality": "MR",
        "treatment": "IMG-MR", "duration": 60, "risk": "moderate",
        "pregnancy": True, "consent": True, "contrast": True,
    },
)
PROFILE_IMAGING_COUNTS = {"compact": 2, "standard": 3, "full_enterprise": 3}

MEDICATION_SPECS = (
    ("PARA-500", "Demo Paracetamol 500 mg Tablet", "Analgesic / Antipyretic", "oral", "prn", False),
    ("CET-10", "Demo Cetirizine 10 mg Tablet", "Antihistamine", "oral", "qd", False),
    ("SALINE-10", "Demo Saline Flush 10 mL", "Support / Flush", "iv", "prn", False),
    ("OND-4", "Demo Ondansetron 4 mg Tablet", "Antiemetic", "oral", "prn", False),
    ("EPI-TRAIN", "Demo Epinephrine Training Ampoule", "Emergency / High Alert", "im", "once", True),
)
PROFILE_MEDICATION_COUNTS = {"compact": 3, "standard": 4, "full_enterprise": 5}

CATALOG_MANAGER_GROUPS = (
    "clinic_emar.group_emar_manager",
)


@GENERATOR_REGISTRY.register
class MasterCatalogGenerator(BaseDemoGenerator):
    key = "master.catalog"
    phase = "11_master"
    sequence = 400
    depends_on = ("patient.personas",)
    scenario_keys = ("SCN-ENCOUNTER-01", "SCN-SESSION-01", "SCN-IMAGING-01", "SCN-EMAR-01", "SCN-CARE-01")
    owned_models = (
        "clinic.treatment.category",
        "clinic.treatment",
        "product.template",
        "product.product",
        "clinic.treatment.pricelist",
        "product.pricelist",
        "clinic.treatment.pricelist.item",
        "clinic.care.protocol",
        "clinic.care.protocol.step",
        "clinical.imaging.type",
        "clinical.imaging.protocol",
        "clinical.imaging.type.prep",
        "clinic.emar.medication.profile",
    )
    required_groups = ("base.group_system",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _ensure(self, ctx, counters, key, model, values, policy=RESET_DEACTIVATE, reset_sequence=600, scenario_key=None, update=False, record_user=None):
        Model = ctx.env[model]
        if record_user:
            Model = Model.with_user(record_user)
        Model = Model.with_company(ctx.run.company_id)

        def create():
            return Model.create(dict(values))

        def update_record(record):
            target = record.with_user(record_user) if record_user else record
            target.with_company(ctx.run.company_id).write(dict(values))

        record, reference, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=scenario_key or ctx.scenario.key,
            create_callback=create,
            update_callback=update_record if update else None,
            reset_policy=policy,
            reset_sequence=reset_sequence,
            record_user=record_user,
        )
        self._bump(counters, status)
        return record, reference

    def _bind_side_effect(self, ctx, counters, key, record, policy=RESET_DEACTIVATE, reset_sequence=550, scenario_key=None):
        reference = ctx.reference_service._reference(ctx.run, key)
        if reference:
            existing = ctx.reference_service.resolve(ctx.run, key, record._name, missing_ok=True)
            if existing:
                counters["reused"] += 1
                return existing
        ctx.reference_service.bind(
            run=ctx.run,
            demo_key=key,
            record=record,
            generator_key=self.key,
            scenario_key=scenario_key or ctx.scenario.key,
            ownership_kind="created",
            reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        counters["created"] += 1
        return record

    def _ensure_catalog_manager_actor(self, ctx):
        user = ctx.reference_service.resolve(
            ctx.run, "DEMO-USER-MGR", "res.users", missing_ok=True
        )
        if not user:
            raise UserError(_("Prompt 11 requires the Demo Clinic Manager actor from workforce.staff."))
        groups = []
        for xmlid in CATALOG_MANAGER_GROUPS:
            group = ctx.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                raise UserError(_("Prompt 11 catalog security group is missing: %s") % xmlid)
            groups.append(group)
        missing_groups = [group for group in groups if group not in user.group_ids]
        if missing_groups:
            user.write({"group_ids": [Command.link(group.id) for group in missing_groups]})
        return user

    def _preflight(self, ctx):
        sequence = ctx.env["ir.sequence"].with_company(ctx.run.company_id).search([
            ("code", "=", "clinic.care.protocol"),
            ("company_id", "in", [False, ctx.run.company_id.id]),
        ], limit=1)
        if not sequence:
            raise UserError(_("MASTER PROMPT 11 catalog preflight: missing sequence clinic.care.protocol."))

    def _branch_doctor(self, ctx):
        return ctx.reference_service.resolve(ctx.run, "DEMO-DOC-001", "clinic.doctor")

    def _ensure_categories(self, ctx, counters):
        categories = {}
        for token, name, sequence in CATEGORY_SPECS:
            record, _ = self._ensure(
                ctx, counters, f"DEMO-CAT-{token}", "clinic.treatment.category",
                {
                    "name": name,
                    "sequence": sequence,
                    "active": True,
                    "company_id": ctx.run.company_id.id,
                    "description": f"<p>ClinicOne synthetic demo master category: {name}.</p>",
                },
                RESET_DEACTIVATE, 900,
            )
            categories[token] = record
        return categories

    def _ensure_treatment(self, ctx, counters, spec, categories):
        key = f"DEMO-TREAT-{spec['code']}"
        values = {
            "name": spec["name"],
            "company_id": ctx.run.company_id.id,
            "category_id": categories[spec["category"]].id,
            "duration_value": float(spec["duration"]),
            "duration_uom": "minute",
            "allow_online_booking": bool(spec["online"]),
            "base_price": float(spec["price"]),
            "minimum_price": float(spec["minimum"]),
            "pricing_policy": spec["policy"],
            "insurance_applicable": bool(spec["insurance"]),
            "surcharge_applicable": True,
            "active": True,
            # Legal templates are created by master.consent. Creating the
            # treatment as non-blocking first avoids inventing a template or
            # bypassing the owner constraint.
            "consent_required": False,
            "consent_required_timing": "optional",
            "description": f"<p>Synthetic ClinicOne demo service master: {spec['name']}.</p>",
        }
        treatment, _ = self._ensure(
            ctx, counters, key, "clinic.treatment", values,
            RESET_DEACTIVATE, 850,
        )
        if treatment.catalog_id.product_tmpl_id:
            tmpl = treatment.catalog_id.product_tmpl_id
            self._bind_side_effect(
                ctx, counters, f"DEMO-PROD-TREAT-{spec['code']}",
                tmpl, RESET_DEACTIVATE, 820,
            )
            if tmpl.product_variant_id:
                self._bind_side_effect(
                    ctx, counters, f"DEMO-PRODUCT-TREAT-{spec['code']}",
                    tmpl.product_variant_id, RESET_DEACTIVATE, 825,
                )
        return treatment

    def _ensure_pricelist(self, ctx, counters, treatments):
        anchor = fields.Date.to_date(ctx.run.anchor_date)
        pricelist, _ = self._ensure(
            ctx, counters, "DEMO-PRICELIST-CLINICAL", "clinic.treatment.pricelist",
            {
                "name": "ClinicOne Demo Clinical Pricelist",
                "company_id": ctx.run.company_id.id,
                "sequence": 10,
                "active": True,
                "channel": "all",
                "apply_membership": True,
                "apply_promotions": True,
                "apply_surcharge": True,
                "apply_insurance": True,
                "tax_included": False,
                "valid_from": anchor,
                "valid_to": False,
                "notes": "<p>Synthetic reference pricing for ClinicOne enterprise demo journeys.</p>",
            },
            RESET_DEACTIVATE, 780,
        )
        if pricelist.product_pricelist_id:
            self._bind_side_effect(
                ctx, counters, "DEMO-ODOO-PRICELIST-CLINICAL",
                pricelist.product_pricelist_id, RESET_DEACTIVATE, 775,
            )

        rule_specs = (
            ("GEN-CONSULT", "CONSULT-GEN", "fixed", 250000),
            ("FOLLOW-UP", "FOLLOW-UP", "fixed", 180000),
            ("PHYSIO", "PHYSIO", "fixed", 350000),
            ("IMG-XR", "IMG-XR", "fixed", 375000),
        )
        available = set(treatments)
        for token, treatment_token, method, fixed_price in rule_specs:
            if treatment_token not in available:
                continue
            treatment = treatments[treatment_token]
            self._ensure(
                ctx, counters, f"DEMO-PRICE-RULE-{token}",
                "clinic.treatment.pricelist.item",
                {
                    "name": f"Demo Price — {treatment.display_name}",
                    "pricelist_id": pricelist.id,
                    "active": True,
                    "sequence": 10,
                    "scope": "treatment",
                    "treatment_id": treatment.catalog_id.id,
                    "channel": "inherit",
                    "base": "treatment_base",
                    "method": method,
                    "fixed_price": float(fixed_price),
                    "rounding_policy": "currency",
                    "enforce_minimum_price": True,
                },
                RESET_DEACTIVATE, 770,
            )
        return pricelist

    def _ensure_product(self, ctx, counters, code, name, product_type="consu", list_price=0.0):
        template, _ = self._ensure(
            ctx, counters, f"DEMO-PROD-{code}", "product.template",
            {
                "name": name,
                "type": product_type,
                "company_id": ctx.run.company_id.id,
                "list_price": float(list_price),
                "sale_ok": True,
                "purchase_ok": product_type != "service",
                "active": True,
            },
            RESET_DEACTIVATE, 760,
        )
        product = template.product_variant_id
        if not product:
            raise UserError(_("Product template %(name)s has no product variant.") % {"name": name})
        self._bind_side_effect(
            ctx, counters, f"DEMO-PRODUCT-{code}",
            product, RESET_DEACTIVATE, 765,
        )
        return product

    def _ensure_care_protocols(self, ctx, counters, treatments):
        doctor = self._branch_doctor(ctx)
        count = PROFILE_PROTOCOL_COUNTS[ctx.profile]
        for spec in CARE_PROTOCOL_SPECS[:count]:
            required = [token for token in spec["treatments"] if token in treatments]
            if not required:
                continue
            protocol, _ = self._ensure(
                ctx, counters, f"DEMO-PROTOCOL-{spec['code']}",
                "clinic.care.protocol",
                {
                    "display_name": spec["title"],
                    "description": f"Synthetic reusable ClinicOne care protocol: {spec['title']}.",
                    "company_id": ctx.run.company_id.id,
                    "owner_doctor_id": doctor.id,
                    "reviewer_ids": [(6, 0, [doctor.id])],
                    "version": "1.0",
                    "version_state": "draft",
                    "effective_date": fields.Date.to_date(ctx.run.anchor_date),
                    "category": spec["category"],
                    "risk_level": spec["risk"],
                    "treatment_ids": [(6, 0, [treatments[token].id for token in required])],
                    "currency_id": ctx.run.company_id.currency_id.id,
                    "active": True,
                    "preconditions": "<p>Use synthetic patient context and applicable consent before execution.</p>",
                    "patient_education": "<p>Demo education content only; not clinical advice.</p>",
                },
                RESET_DEACTIVATE, 740,
            )
            step_records = []
            for sequence, (title, treatment_token, duration, day_offset, require_consent) in enumerate(spec["steps"], start=1):
                if treatment_token not in treatments:
                    continue
                step, _ = self._ensure(
                    ctx, counters,
                    f"DEMO-PROTOCOL-STEP-{spec['code']}-{sequence:02d}",
                    "clinic.care.protocol.step",
                    {
                        "protocol_id": protocol.id,
                        "sequence": sequence * 10,
                        "name": title,
                        "instruction": f"Synthetic demo protocol step: {title}.",
                        "treatment_id": treatments[treatment_token].id,
                        "risk_level": "moderate" if require_consent else "low",
                        "require_consent": bool(require_consent),
                        "duration_minutes": int(duration),
                        "expected_day_offset": int(day_offset),
                        "currency_id": ctx.run.company_id.currency_id.id,
                        "active": True,
                    },
                    RESET_DEACTIVATE, 745,
                    scenario_key="SCN-CARE-01",
                )
                step_records.append(step)
            if protocol.version_state != "published":
                if protocol.version_state == "draft":
                    protocol.action_submit_review()
                protocol.action_publish()

    def _ensure_imaging(self, ctx, counters, treatments, contrast_product):
        count = PROFILE_IMAGING_COUNTS[ctx.profile]
        for spec in IMAGING_SPECS[:count]:
            if spec["treatment"] not in treatments:
                continue
            treatment = treatments[spec["treatment"]]
            product = treatment.catalog_id.product_tmpl_id.product_variant_id
            values = {
                "name": spec["name"],
                "code": spec["code"],
                "company_id": ctx.run.company_id.id,
                "active": True,
                "modality": spec["modality"],
                "category": "diagnostic",
                "description": f"Synthetic imaging master for {spec['name']}.",
                "default_product_id": product.id,
                "default_price_unit": treatment.base_price,
                "currency_id": ctx.run.company_id.currency_id.id,
                "is_billable": True,
                "default_duration_minutes": spec["duration"],
                "require_consent": spec["consent"],
                "safety_risk": spec["risk"],
                "require_pregnancy_check": spec["pregnancy"],
                "contrast_required": spec["contrast"],
                "fasting_hours": 4 if spec["contrast"] else 0,
            }
            if spec["contrast"]:
                values.update({
                    "contrast_agent_product_id": contrast_product.id,
                    "contrast_dose_mg_per_kg": 1.0,
                    "require_creatinine_check": True,
                    "creatinine_max_value": 1.5,
                })
            imaging, _ = self._ensure(
                ctx, counters, f"DEMO-IMTYPE-{spec['code']}",
                "clinical.imaging.type", values,
                RESET_DEACTIVATE, 720,
                scenario_key="SCN-IMAGING-01",
            )
            self._ensure(
                ctx, counters, f"DEMO-IMPROTO-{spec['code']}-01",
                "clinical.imaging.protocol",
                {
                    "imaging_type_id": imaging.id,
                    "sequence": 10,
                    "title": "Patient verification and positioning",
                    "instruction": "Synthetic demo acquisition protocol: verify identity, indication, and positioning.",
                    "expected_duration_minutes": max(5, int(spec["duration"]) // 3),
                    "requires_contrast": bool(spec["contrast"]),
                    "requires_sedation": False,
                    "note": "Demo protocol master only.",
                },
                RESET_FRESH_DB_ONLY, 715,
                scenario_key="SCN-IMAGING-01",
            )
            self._ensure(
                ctx, counters, f"DEMO-IMPREP-{spec['code']}-01",
                "clinical.imaging.type.prep",
                {
                    "imaging_type_id": imaging.id,
                    "sequence": 10,
                    "title": "Pre-imaging safety verification",
                    "instruction": "Verify source-supported safety checklist before acquisition.",
                    "responsible": "staff",
                    "min_hours_before": 0.0,
                    "note": "Synthetic preparation master.",
                },
                RESET_FRESH_DB_ONLY, 710,
                scenario_key="SCN-IMAGING-01",
            )

    def _ensure_medication_profiles(self, ctx, counters, manager_user):
        unit = ctx.env.ref("uom.product_uom_unit")
        count = PROFILE_MEDICATION_COUNTS[ctx.profile]
        products = {}
        for code, name, med_class, route, frequency, high_alert in MEDICATION_SPECS[:count]:
            product = self._ensure_product(ctx, counters, f"MED-{code}", name, "consu", 50000)
            products[code] = product
            self._ensure(
                ctx, counters, f"DEMO-MED-PROFILE-{code}",
                "clinic.emar.medication.profile",
                {
                    "active": True,
                    "company_id": ctx.run.company_id.id,
                    "product_id": product.id,
                    "medication_code": f"DEMO-{code}",
                    "medication_class": med_class,
                    "controlled_level": "none",
                    "high_alert": bool(high_alert),
                    "requires_double_check": bool(high_alert),
                    "requires_patient_scan": True,
                    "requires_product_scan": True,
                    "requires_lot": bool(high_alert),
                    "allow_substitution": not high_alert,
                    "default_route": route,
                    "default_frequency": frequency,
                    "dose_uom_id": unit.id,
                    "max_single_dose": 0.0,
                    "max_daily_dose": 0.0,
                    "notes": "<p>Synthetic medication master for ClinicOne eMAR demonstration only.</p>",
                },
                RESET_DEACTIVATE, 700,
                scenario_key="SCN-EMAR-01",
                record_user=manager_user,
            )
        return products

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        counters = self._counters()
        manager_user = self._ensure_catalog_manager_actor(ctx)
        categories = self._ensure_categories(ctx, counters)
        treatment_count = PROFILE_TREATMENT_COUNTS[ctx.profile]
        treatments = {}
        for spec in TREATMENT_SPECS[:treatment_count]:
            treatments[spec["code"]] = self._ensure_treatment(ctx, counters, spec, categories)

        self._ensure_pricelist(ctx, counters, treatments)
        medication_products = self._ensure_medication_profiles(ctx, counters, manager_user)
        contrast_product = self._ensure_product(
            ctx, counters, "CONTRAST-DEMO", "Demo Iodinated Contrast Agent",
            "consu", 250000,
        )
        self._ensure_imaging(ctx, counters, treatments, contrast_product)
        self._ensure_care_protocols(ctx, counters, treatments)
        return counters

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def validate(self, ctx, scenario):
        failures = []
        manager_user = self._ensure_catalog_manager_actor(ctx)
        treatment_count = PROFILE_TREATMENT_COUNTS[ctx.profile]
        for spec in TREATMENT_SPECS[:treatment_count]:
            treatment = ctx.reference_service.resolve(
                ctx.run, f"DEMO-TREAT-{spec['code']}", "clinic.treatment"
            )
            if not treatment.active or treatment.company_id != ctx.run.company_id:
                failures.append(f"Treatment {spec['code']} is inactive or company-misaligned.")
            if not treatment.catalog_id.product_tmpl_id:
                failures.append(f"Treatment {spec['code']} lacks its billable service product.")
            if treatment.base_price <= 0:
                failures.append(f"Treatment {spec['code']} has no positive reference price.")

        for spec in IMAGING_SPECS[:PROFILE_IMAGING_COUNTS[ctx.profile]]:
            if spec["treatment"] not in {item["code"] for item in TREATMENT_SPECS[:treatment_count]}:
                continue
            imaging = ctx.reference_service.resolve(
                ctx.run, f"DEMO-IMTYPE-{spec['code']}", "clinical.imaging.type"
            )
            if not imaging.default_product_id or not imaging.is_billable:
                failures.append(f"Imaging type {spec['code']} lacks billable product mapping.")
            if spec["contrast"] and not imaging.contrast_agent_product_id:
                failures.append(f"Contrast imaging type {spec['code']} lacks a contrast product.")

        for spec in CARE_PROTOCOL_SPECS[:PROFILE_PROTOCOL_COUNTS[ctx.profile]]:
            protocol = ctx.reference_service.resolve(
                ctx.run, f"DEMO-PROTOCOL-{spec['code']}", "clinic.care.protocol"
            )
            if protocol.version_state != "published" or not protocol.step_ids:
                failures.append(f"Care protocol {spec['code']} is not published with steps.")

        for code, *_rest in MEDICATION_SPECS[:PROFILE_MEDICATION_COUNTS[ctx.profile]]:
            profile = ctx.reference_service.resolve(
                ctx.run, f"DEMO-MED-PROFILE-{code}", "clinic.emar.medication.profile",
                record_user=manager_user,
            )
            if not profile.product_id or profile.product_id.type == "service":
                failures.append(f"Medication profile {code} has invalid product mapping.")

        if failures:
            raise UserError(_("Clinical master catalog validation failed: %s") % "; ".join(failures))
        return []









