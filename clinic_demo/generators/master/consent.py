
"""MASTER PROMPT 11 — governed consent template masters without patient consent transactions."""

from odoo import _, fields
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_DEACTIVATE, RESET_DELETE_SAFE, RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


CONSENT_SPECS = (
    {
        "code": "GENERAL", "name": "General Treatment Consent",
        "scope": "treatment_general", "category": "clinical",
        "applicability": "generic", "treatment": None, "validity": 365,
        "title": "General Treatment Consent",
        "content": (
            "<p>This synthetic demo template documents the patient discussion, "
            "expected benefits, alternatives, material risks, and opportunity to ask questions.</p>"
        ),
        "items": (
            "I confirm that the proposed service was explained to me.",
            "I had an opportunity to ask questions.",
            "I understand that this is synthetic demonstration content.",
        ),
    },
    {
        "code": "SKIN", "name": "Skin Procedure Consent",
        "scope": "procedure_specific", "category": "clinical",
        "applicability": "treatment", "treatment": "SKIN-PROC", "validity": 90,
        "title": "Skin Rejuvenation Procedure Consent",
        "content": (
            "<p>Synthetic procedure-specific consent content for the ClinicOne demo. "
            "It demonstrates governed consent before a procedure without representing medical advice.</p>"
        ),
        "items": (
            "The planned procedure and expected course were explained.",
            "Procedure-specific risks and alternatives were discussed.",
        ),
    },
    {
        "code": "TELE", "name": "Telemedicine Consent",
        "scope": "telemedicine", "category": "clinical",
        "applicability": "treatment", "treatment": "TELE-CONSULT", "validity": 365,
        "title": "Telemedicine Service Consent",
        "content": (
            "<p>Synthetic consent covering remote consultation limitations, identity verification, "
            "privacy expectations, and escalation to in-person care when appropriate.</p>"
        ),
        "items": (
            "I understand the limitations of a remote consultation.",
            "I agree to the use of the synthetic demo communication channel.",
        ),
    },
    {
        "code": "MED", "name": "Medication Administration Consent",
        "scope": "medication_admin", "category": "clinical",
        "applicability": "generic", "treatment": None, "validity": 180,
        "title": "Medication Administration Consent",
        "content": (
            "<p>Synthetic medication-administration consent master used to demonstrate eMAR safety "
            "and acknowledgement workflows in later Master Prompts.</p>"
        ),
        "items": (
            "Medication purpose and administration process were explained.",
            "Known allergy information should be reviewed before administration.",
        ),
    },
    {
        "code": "MRI", "name": "MRI with Contrast Consent",
        "scope": "procedure_specific", "category": "clinical",
        "applicability": "treatment", "treatment": "IMG-MR", "validity": 30,
        "title": "MRI with Contrast Consent",
        "content": (
            "<p>Synthetic imaging consent master demonstrating contrast, renal-function, "
            "pregnancy-status, and device/implant safety review.</p>"
        ),
        "items": (
            "Imaging safety screening was reviewed.",
            "Contrast-related precautions were explained.",
        ),
    },
)
PROFILE_CONSENT_COUNTS = {"compact": 3, "standard": 4, "full_enterprise": 5}


@GENERATOR_REGISTRY.register
class MasterConsentGenerator(BaseDemoGenerator):
    key = "master.consent"
    phase = "11_master"
    sequence = 410
    depends_on = ("master.catalog",)
    scenario_keys = ("SCN-CONSENT-01",)
    owned_models = (
        "clinic.consent.template",
        "clinic.consent.template.item",
        "clinic.consent.template.version",
    )
    required_groups = ("base.group_system",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _ensure(self, ctx, counters, key, model, values, policy, reset_sequence):
        Model = ctx.env[model].with_company(ctx.run.company_id)

        def create():
            return Model.create(dict(values))

        record, reference, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=ctx.scenario.key,
            create_callback=create,
            update_callback=None,
            reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record, reference

    def _preflight(self, ctx):
        sequence = ctx.env["ir.sequence"].with_company(ctx.run.company_id).search([
            ("code", "=", "clinic.consent.template"),
            ("company_id", "in", [False, ctx.run.company_id.id]),
        ], limit=1)
        if not sequence:
            raise UserError(_("MASTER PROMPT 11 consent preflight: missing sequence clinic.consent.template."))

    def _treatment(self, ctx, token):
        if not token:
            return False
        return ctx.reference_service.resolve(
            ctx.run, f"DEMO-TREAT-{token}", "clinic.treatment", missing_ok=True
        )

    def _ensure_template(self, ctx, counters, spec):
        treatment = self._treatment(ctx, spec["treatment"])
        if spec["treatment"] and not treatment:
            counters["skipped"] += 1
            return False

        values = {
            "sequence": 10,
            "name": spec["name"],
            "code": f"DEMO-CONS-{spec['code']}",
            "active": True,
            "scope": spec["scope"],
            "category": spec["category"],
            "requires_guardian": True,
            "requires_witness": spec["code"] in {"SKIN", "MRI"},
            "validity_days": spec["validity"],
            "allow_reuse": True,
            "legal_governed": True,
            "title": spec["title"],
            "company_id": ctx.run.company_id.id,
            "state": "draft",
            "consent_version": "v1.0",
            "version_major": 1,
            "version_minor": 0,
            "version_auto_bump": True,
            "effective_date": fields.Date.to_date(ctx.run.anchor_date),
            "applicability": spec["applicability"],
            "content_html": spec["content"],
            "content_text": "Synthetic ClinicOne enterprise demo consent master.",
            "risks_and_complications": (
                "<p>Synthetic risk disclosure content for demonstration. "
                "No clinical decision should be based on this demo record.</p>"
            ),
            "alternatives": "<p>Synthetic alternative-care discussion for demonstration.</p>",
            "required_before_procedure": spec["scope"] != "telemedicine",
            "notes": "Generated by ClinicOne Enterprise Demo Dataset — synthetic master only.",
        }
        if treatment:
            values["treatment_id"] = treatment.id

        template, _ = self._ensure(
            ctx, counters, f"DEMO-CONSENT-TPL-{spec['code']}",
            "clinic.consent.template", values,
            RESET_DEACTIVATE, 690,
        )

        for index, label in enumerate(spec["items"], start=1):
            self._ensure(
                ctx, counters, f"DEMO-CONSENT-ITEM-{spec['code']}-{index:02d}",
                "clinic.consent.template.item",
                {
                    "template_id": template.id,
                    "sequence": index * 10,
                    "label": label,
                    "required": True,
                    "default_value": "none",
                    "notes": "Synthetic acknowledgement item.",
                },
                RESET_DELETE_SAFE, 700,
            )

        self._ensure(
            ctx, counters, f"DEMO-CONSENT-VERSION-{spec['code']}-01",
            "clinic.consent.template.version",
            {
                "template_id": template.id,
                "version": 1,
                "title": spec["title"],
                "body_html": spec["content"],
                "effective_from": fields.Date.to_date(ctx.run.anchor_date),
                "effective_to": False,
                "changelog": "Initial synthetic enterprise demo version.",
                "state": "published",
            },
            RESET_FRESH_DB_ONLY, 695,
        )

        if template.state != "published":
            template.action_publish()

        if treatment:
            treatment.write({
                "consent_required": True,
                "consent_required_timing": (
                    "before_booking" if spec["code"] == "TELE" else "before_procedure"
                ),
                "consent_default_template_id": template.id,
                "consent_validity_days_override": spec["validity"],
                "consent_autogenerate_on_booking": spec["code"] == "TELE",
                "consent_advisory": (
                    "Synthetic demo consent policy. Use the published governed template."
                ),
            })
        return template

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        counters = self._counters()
        for spec in CONSENT_SPECS[:PROFILE_CONSENT_COUNTS[ctx.profile]]:
            self._ensure_template(ctx, counters, spec)
        return counters

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def validate(self, ctx, scenario):
        failures = []
        for spec in CONSENT_SPECS[:PROFILE_CONSENT_COUNTS[ctx.profile]]:
            treatment = self._treatment(ctx, spec["treatment"])
            if spec["treatment"] and not treatment:
                continue
            template = ctx.reference_service.resolve(
                ctx.run, f"DEMO-CONSENT-TPL-{spec['code']}", "clinic.consent.template"
            )
            if not template.legal_governed or template.state != "published":
                failures.append(f"Consent template {spec['code']} is not legally governed/published.")
            if not template.content_checksum:
                failures.append(f"Consent template {spec['code']} has no governance checksum.")
            if not template.latest_version_id or template.latest_version_id.state != "published":
                failures.append(f"Consent template {spec['code']} has no published canonical version.")
            if treatment:
                if not treatment.consent_required or treatment.consent_default_template_id != template:
                    failures.append(f"Treatment {spec['treatment']} is not linked to its consent policy.")

        if failures:
            raise UserError(_("Consent master validation failed: %s") % "; ".join(failures))
        return []


