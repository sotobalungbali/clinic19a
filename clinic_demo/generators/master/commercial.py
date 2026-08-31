
"""MASTER PROMPT 11 — package, membership, insurance and wallet policy masters.

This generator deliberately creates reusable commercial policy/catalog records only.
It does not create patient entitlements, allocations, wallet balances, insurance
policies/authorizations, invoices or payments; those belong to later Master Prompts.
"""

from odoo import _, Command, fields
from odoo.exceptions import AccessError, UserError

from ..base import BaseDemoGenerator
from ...services.constants import (
    RESET_DEACTIVATE,
    RESET_DELETE_SAFE,
    RESET_FRESH_DB_ONLY,
)
from ...services.generator_registry import GENERATOR_REGISTRY


PACKAGE_SPECS = (
    {
        "code": "RECOVERY", "name": "Recovery Therapy 4-Session Package",
        "price": 1450000.0, "cost": 850000.0,
        "lines": (("PHYSIO", 4.0), ("FOLLOW-UP", 1.0)),
    },
    {
        "code": "SKIN", "name": "Skin Care Program Package",
        "price": 2400000.0, "cost": 1300000.0,
        "lines": (("SKIN-PROC", 3.0), ("FOLLOW-UP", 1.0)),
    },
    {
        "code": "DIAG", "name": "Diagnostic Imaging Package",
        "price": 900000.0, "cost": 520000.0,
        "lines": (("IMG-XR", 1.0), ("IMG-US", 1.0)),
    },
    {
        "code": "WELLNESS", "name": "Wellness Continuity Package",
        "price": 2650000.0, "cost": 1350000.0,
        "lines": (("WELLNESS", 6.0), ("FOLLOW-UP", 2.0)),
    },
)
PROFILE_PACKAGE_COUNTS = {"compact": 2, "standard": 3, "full_enterprise": 4}

MEMBERSHIP_SPECS = (
    {
        "code": "ESSENTIAL", "name": "ClinicOne Essential Membership", "tier": "silver",
        "price": 1200000.0, "join": 100000.0, "renewal": 1000000.0,
        "priority": "normal", "treatments": ("CONSULT-GEN", "FOLLOW-UP", "PHYSIO"),
        "benefits": (
            {"code": "DISC", "name": "10% Consultation Benefit", "type": "discount_percent", "value": 10.0, "treatment": "CONSULT-GEN"},
            {"code": "PRIO", "name": "Standard Priority Booking", "type": "priority", "priority": "high"},
        ),
    },
    {
        "code": "PREMIUM", "name": "ClinicOne Premium Membership", "tier": "gold",
        "price": 2400000.0, "join": 0.0, "renewal": 2100000.0,
        "priority": "high", "treatments": ("CONSULT-GEN", "CONSULT-SPEC", "FOLLOW-UP", "PHYSIO", "TELE-CONSULT"),
        "benefits": (
            {"code": "DISC", "name": "15% Specialist Consultation Benefit", "type": "discount_percent", "value": 15.0, "treatment": "CONSULT-SPEC"},
            {"code": "QUOTA", "name": "Two Follow-up Sessions per Term", "type": "quota", "value": 2.0, "treatment": "FOLLOW-UP"},
            {"code": "PRIO", "name": "High Priority Booking", "type": "priority", "priority": "high"},
        ),
    },
    {
        "code": "SIGNATURE", "name": "ClinicOne Signature Membership", "tier": "platinum",
        "price": 4200000.0, "join": 0.0, "renewal": 3600000.0,
        "priority": "vip", "treatments": ("CONSULT-GEN", "CONSULT-SPEC", "FOLLOW-UP", "PHYSIO", "TELE-CONSULT", "IMG-XR", "IMG-US"),
        "benefits": (
            {"code": "DISC", "name": "20% Signature Consultation Benefit", "type": "discount_percent", "value": 20.0, "treatment": "CONSULT-SPEC"},
            {"code": "QUOTA", "name": "Four Follow-up Sessions per Term", "type": "quota", "value": 4.0, "treatment": "FOLLOW-UP"},
            {"code": "PRIO", "name": "VIP Priority Booking", "type": "priority", "priority": "vip"},
        ),
    },
)
PROFILE_MEMBERSHIP_COUNTS = {"compact": 1, "standard": 2, "full_enterprise": 3}

INSURANCE_SPECS = (
    {
        "code": "CORP80", "name": "DemoCare Corporate 80", "coverage": 80.0,
        "copay": 20.0, "deductible": 0.0, "annual": 25000000.0,
        "authorization": True,
    },
    {
        "code": "PREM90", "name": "DemoCare Premium 90", "coverage": 90.0,
        "copay": 10.0, "deductible": 100000.0, "annual": 50000000.0,
        "authorization": True,
    },
)
PROFILE_INSURANCE_COUNTS = {"compact": 1, "standard": 1, "full_enterprise": 2}

COMMERCIAL_MANAGER_GROUPS = (
    "clinic_package.group_clinic_package_manager",
    "clinic_membership.group_clinic_membership_manager",
    "clinic_insurance_authorization.group_clinic_insurance_manager",
    "clinic_wallet.group_wallet_manager",
)

RESTRICTED_COMMERCIAL_MODELS = frozenset({
    "clinic.package.policy",
    "clinic.package.pricing",
    "clinic.package",
    "clinic.package.line",
    "clinic.package.integration.event",
    "membership.plan",
    "membership.plan.benefit",
    "membership.integration.event",
    "clinic.insurance.plan",
    "clinic.insurance.plan.rule",
    "clinic.wallet.rule",
})

# Models created directly by Prompt 11 must have a real owner ACL granting create
# to the functional manager actor. Integration-event models are intentionally
# excluded because they are emitted by owner business methods, not created
# directly by clinic_demo.
COMMERCIAL_CREATE_ACCESS_MODELS = (
    "clinic.package.policy",
    "clinic.package.pricing",
    "clinic.package",
    "clinic.package.line",
    "membership.plan",
    "membership.plan.benefit",
    "clinic.insurance.plan",
    "clinic.insurance.plan.rule",
    "clinic.wallet.rule",
)


@GENERATOR_REGISTRY.register
class MasterCommercialGenerator(BaseDemoGenerator):
    key = "master.commercial"
    phase = "11_master"
    sequence = 420
    depends_on = ("master.consent",)
    scenario_keys = (
        "SCN-PACKAGE-01", "SCN-MEMBERSHIP-01", "SCN-WALLET-01", "SCN-INSURANCE-01"
    )
    owned_models = (
        "clinic.package.policy", "clinic.package.pricing", "clinic.package",
        "clinic.package.line", "clinic.package.integration.event",
        "membership.plan", "membership.plan.benefit", "membership.integration.event",
        "clinic.insurance.plan", "clinic.insurance.plan.rule", "clinic.wallet.rule",
        "res.partner", "product.template", "product.product",
    )
    required_groups = ("base.group_system",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        counters[status if status in counters else "created"] += 1

    def _ensure_commercial_manager_actor(self, ctx):
        user = ctx.reference_service.resolve(
            ctx.run, "DEMO-USER-MGR", "res.users", missing_ok=True
        )
        if not user:
            raise UserError(_("Prompt 11 requires the Demo Clinic Manager actor from workforce.staff."))
        groups = []
        for xmlid in COMMERCIAL_MANAGER_GROUPS:
            group = ctx.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                raise UserError(_("Prompt 11 commercial security group is missing: %s") % xmlid)
            groups.append(group)
        missing_groups = [group for group in groups if group not in user.group_ids]
        if missing_groups:
            user.write({"group_ids": [Command.link(group.id) for group in missing_groups]})
        return user

    def _record_user_for_model(self, ctx, model_name):
        if model_name in RESTRICTED_COMMERCIAL_MODELS:
            return self._ensure_commercial_manager_actor(ctx)
        return False

    def _resolve(self, ctx, demo_key, model_name, missing_ok=False):
        return ctx.reference_service.resolve(
            ctx.run, demo_key, model_name, missing_ok=missing_ok,
            record_user=self._record_user_for_model(ctx, model_name),
        )

    def _ensure(self, ctx, counters, key, model, values, policy, reset_sequence, scenario_key=None, update=True):
        record_user = self._record_user_for_model(ctx, model)
        Model = ctx.env[model]
        if record_user:
            Model = Model.with_user(record_user)
        Model = Model.with_company(ctx.run.company_id)
        existing_reference = ctx.reference_service._reference(ctx.run, key)

        def create():
            return Model.create(dict(values))

        def update_record(record):
            if values:
                target = record.with_user(record_user) if record_user else record
                target.with_company(ctx.run.company_id).write(dict(values))

        record, reference, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=scenario_key or ctx.scenario.key,
            create_callback=create,
            update_callback=(
                update_record
                if update and not (existing_reference and existing_reference.ownership_kind == "reused")
                else None
            ),
            reset_policy=policy,
            reset_sequence=reset_sequence,
            record_user=record_user,
        )
        self._bump(counters, status)
        return record, reference

    def _bind_side_effect(self, ctx, counters, key, record, policy, reset_sequence, scenario_key):
        record_user = self._record_user_for_model(ctx, record._name)
        reference = ctx.reference_service._reference(ctx.run, key)
        if reference:
            existing = ctx.reference_service.resolve(
                ctx.run, key, record._name, missing_ok=True, record_user=record_user
            )
            if existing:
                counters["reused"] += 1
                return existing
        ctx.reference_service.bind(
            run=ctx.run,
            demo_key=key,
            record=record,
            generator_key=self.key,
            scenario_key=scenario_key,
            ownership_kind="created",
            reset_policy=policy,
            reset_sequence=reset_sequence,
            record_user=record_user,
        )
        counters["created"] += 1
        return record

    def _preflight(self, ctx):
        manager_user = self._ensure_commercial_manager_actor(ctx)
        access_failures = []
        for model_name in COMMERCIAL_CREATE_ACCESS_MODELS:
            if model_name not in ctx.env:
                continue
            try:
                ctx.env[model_name].with_user(manager_user).with_company(
                    ctx.run.company_id
                ).check_access("create")
            except AccessError as exc:
                access_failures.append(f"{model_name}: {exc}")
        if access_failures:
            raise UserError(_(
                "MASTER PROMPT 11 commercial ACL preflight failed. Upgrade the owning "
                "addon(s) before generation: %s"
            ) % "; ".join(access_failures))

        requirements = {
            "clinic.package": {"name", "company_id", "list_price", "policy_id", "pricing_id", "product_template_id", "line_ids", "state"},
            "membership.plan": {"name", "code", "company_id", "tier", "list_price", "product_id", "benefit_ids", "state"},
            "clinic.insurance.plan": {"name", "code", "company_id", "branch_id", "insurer_partner_id", "rule_ids", "state"},
            "clinic.wallet.rule": {"name", "company_id", "scope", "membership_tier_ids", "active", "state"},
        }
        missing = []
        for model_name, fields_required in requirements.items():
            if model_name not in ctx.env:
                missing.append(f"missing model {model_name}")
                continue
            absent = sorted(fields_required - set(ctx.env[model_name]._fields))
            if absent:
                missing.append(f"{model_name} missing fields {', '.join(absent)}")
        required_sequences = (
            "clinic.package",
            "clinic.package.integration.event",
            "membership.plan",
        )
        Sequence = ctx.env["ir.sequence"].with_company(ctx.run.company_id)
        for code in required_sequences:
            if not Sequence.search([
                ("code", "=", code),
                ("company_id", "in", [False, ctx.run.company_id.id]),
            ], limit=1):
                missing.append(f"missing sequence {code}")
        if missing:
            raise UserError(_("MASTER PROMPT 11 commercial preflight failed: %s") % "; ".join(missing))

    def _treatment(self, ctx, token):
        return ctx.reference_service.resolve(
            ctx.run, f"DEMO-TREAT-{token}", "clinic.treatment", missing_ok=True
        )

    def _doctor(self, ctx):
        return ctx.reference_service.resolve(ctx.run, "DEMO-DOC-001", "clinic.doctor", missing_ok=True)

    def _branch(self, ctx):
        for key in ("DEMO-BRANCH-01", "DEMO-BRANCH-HQ", "DEMO-BRANCH-001"):
            branch = ctx.reference_service.resolve(ctx.run, key, "clinic.branch", missing_ok=True)
            if branch:
                return branch
        return ctx.run.company_id.default_branch_id if "default_branch_id" in ctx.run.company_id._fields else False

    def _ensure_product(self, ctx, counters, code, name, list_price, scenario_key):
        template, _ = self._ensure(
            ctx, counters, f"DEMO-PROD-COMM-{code}", "product.template",
            {
                "name": name,
                "type": "service",
                "company_id": ctx.run.company_id.id,
                "list_price": float(list_price),
                "sale_ok": True,
                "purchase_ok": False,
                "active": True,
            },
            RESET_DEACTIVATE, 650, scenario_key=scenario_key,
        )
        if not template.product_variant_id:
            raise UserError(_("Commercial service product %(name)s has no product variant.") % {"name": name})
        self._bind_side_effect(
            ctx, counters, f"DEMO-PRODUCT-COMM-{code}", template.product_variant_id,
            RESET_DEACTIVATE, 655, scenario_key,
        )
        return template, template.product_variant_id

    def _ensure_package_profiles(self, ctx, counters):
        policy, _ = self._ensure(
            ctx, counters, "DEMO-PKG-POLICY-STANDARD", "clinic.package.policy",
            {
                "name": "ClinicOne Demo Standard Package Policy",
                "sequence": 10, "active": True, "company_id": ctx.run.company_id.id,
                "allow_pause": True, "max_pause_days": 30, "pause_min_days_each": 1,
                "pause_max_times": 2, "pause_require_manager": False,
                "allow_transfer": True, "transfer_scope": "family", "transfer_max_times": 1,
                "transfer_min_remaining_pct": 25.0, "transfer_fee_type": "none",
                "allow_refund": False, "refund_mode": "none", "allow_upgrade": True,
                "allow_downgrade": False,
                "note": "Synthetic ClinicOne demo package policy master.",
            }, RESET_DEACTIVATE, 640, scenario_key="SCN-PACKAGE-01",
        )
        pricing, _ = self._ensure(
            ctx, counters, "DEMO-PKG-PRICING-STANDARD", "clinic.package.pricing",
            {
                "name": "ClinicOne Demo Transparent Package Pricing",
                "active": True, "sequence": 10, "company_id": ctx.run.company_id.id,
                "floor_price": 0.0, "ceiling_price": 0.0, "allow_stack": False,
                "note": "Synthetic pricing profile; package reference values remain transaction-source driven.",
            }, RESET_DEACTIVATE, 635, scenario_key="SCN-PACKAGE-01",
        )
        return policy, pricing

    def _neutralize_package_events(self, ctx, counters, package, code):
        manager_user = self._ensure_commercial_manager_actor(ctx)
        Event = ctx.env["clinic.package.integration.event"].with_user(manager_user).with_company(ctx.run.company_id)
        events = Event.search([
            ("source_model", "=", "clinic.package"),
            ("source_res_id", "=", package.id),
            ("event_code", "=", "package.activated"),
        ], order="id asc")
        for index, event in enumerate(events, start=1):
            if event.state != "done" and event.state != "cancelled":
                event.action_cancel()
            self._bind_side_effect(
                ctx, counters, f"DEMO-PKG-EVENT-{code}-ACT-{index:02d}", event,
                RESET_DELETE_SAFE, 625, "SCN-PACKAGE-01",
            )

    def _ensure_packages(self, ctx, counters):
        policy, pricing = self._ensure_package_profiles(ctx, counters)
        doctor = self._doctor(ctx)
        count = PROFILE_PACKAGE_COUNTS[ctx.profile]
        packages = {}
        for spec in PACKAGE_SPECS[:count]:
            treatment_pairs = [(token, self._treatment(ctx, token)) for token, _qty in spec["lines"]]
            if any(not treatment for _token, treatment in treatment_pairs):
                counters["skipped"] += 1
                continue
            product_template, _product = self._ensure_product(
                ctx, counters, f"PKG-{spec['code']}", spec["name"], spec["price"], "SCN-PACKAGE-01"
            )
            package, _ = self._ensure(
                ctx, counters, f"DEMO-PKG-{spec['code']}", "clinic.package",
                {
                    "name": spec["name"], "company_id": ctx.run.company_id.id,
                    "list_price": spec["price"], "cost_price": spec["cost"],
                    "pricing_id": pricing.id, "policy_id": policy.id,
                    "product_template_id": product_template.id,
                    "duration_value": 12, "duration_uom": "month",
                    "valid_from": fields.Date.to_date(ctx.run.anchor_date), "valid_to": False,
                    "description": "<p>Synthetic ClinicOne enterprise demo package master.</p>",
                    "terms": "<p>Demo-only package policy terms. No real patient entitlement is created in Prompt 11.</p>",
                    "state": "draft", "active": True,
                }, RESET_DEACTIVATE, 620, scenario_key="SCN-PACKAGE-01",
                update=False,
            )
            if package.state not in ("draft", "paused", "active"):
                raise UserError(_("Demo package %(name)s is in unsupported state %(state)s.") % {"name": package.display_name, "state": package.state})
            if package.state in ("draft", "paused"):
                for line_index, (token, qty) in enumerate(spec["lines"], start=1):
                    treatment = self._treatment(ctx, token)
                    self._ensure(
                        ctx, counters, f"DEMO-PKG-LINE-{spec['code']}-{line_index:02d}",
                        "clinic.package.line",
                        {
                            "package_id": package.id, "sequence": line_index * 10,
                            "name": f"{treatment.display_name} — {qty:g} session(s)",
                            "line_type": "treatment", "treatment_id": treatment.id,
                            "qty": float(qty), "consume_per_use": 1.0,
                            "allowed_doctor_ids": [(6, 0, [doctor.id])] if doctor else [(5, 0, 0)],
                            "list_price": float(treatment.base_price or 0.0),
                            "cost_price": 0.0, "active": True,
                            "note": "Synthetic reusable package component; no allocation/usage created in Prompt 11.",
                        }, RESET_FRESH_DB_ONLY, 615, scenario_key="SCN-PACKAGE-01",
                    )
                if package.state == "draft":
                    package.action_activate()
            self._neutralize_package_events(ctx, counters, package, spec["code"])
            packages[spec["code"]] = package
        return packages

    def _neutralize_membership_event(self, ctx, counters, plan, code):
        manager_user = self._ensure_commercial_manager_actor(ctx)
        Event = ctx.env["membership.integration.event"].with_user(manager_user).with_company(ctx.run.company_id)
        events = Event.search([
            ("source_model", "=", "membership.plan"),
            ("source_res_id", "=", plan.id),
            ("event_code", "=", "plan.activated"),
        ], order="id asc")
        for index, event in enumerate(events, start=1):
            reference_key = f"DEMO-MEM-EVENT-{code}-ACT-{index:02d}"
            if event.state not in ("processed", "ignored"):
                event.action_ignore()
            self._bind_side_effect(
                ctx, counters, reference_key, event,
                RESET_DELETE_SAFE, 595, "SCN-MEMBERSHIP-01",
            )

    def _ensure_memberships(self, ctx, counters):
        doctor = self._doctor(ctx)
        count = PROFILE_MEMBERSHIP_COUNTS[ctx.profile]
        plans = {}
        for spec in MEMBERSHIP_SPECS[:count]:
            treatments = [self._treatment(ctx, token) for token in spec["treatments"]]
            treatments = [record for record in treatments if record]
            _template, product = self._ensure_product(
                ctx, counters, f"MEM-{spec['code']}", spec["name"], spec["price"], "SCN-MEMBERSHIP-01"
            )
            plan, _ = self._ensure(
                ctx, counters, f"DEMO-MEM-PLAN-{spec['code']}", "membership.plan",
                {
                    "name": spec["name"], "company_id": ctx.run.company_id.id,
                    "tier": spec["tier"], "list_price": spec["price"], "join_fee": spec["join"],
                    "renewal_fee": spec["renewal"], "product_id": product.id,
                    "duration_value": 12, "duration_unit": "month", "allow_hold": True,
                    "max_hold_days_per_term": 30, "rollover_enabled": False,
                    "priority_level": spec["priority"], "max_concurrent_bookings": 4,
                    "allowed_doctor_ids": [(6, 0, [doctor.id])] if doctor else [(5, 0, 0)],
                    "allowed_treatment_ids": [(6, 0, [record.id for record in treatments])],
                    "description": "<p>Synthetic ClinicOne membership plan master.</p>",
                    "internal_notes": "Prompt 11 creates plan policy only; no patient membership contract yet.",
                    "state": "draft", "active": True,
                }, RESET_DEACTIVATE, 600, scenario_key="SCN-MEMBERSHIP-01",
                update=False,
            )
            if plan.state == "draft":
                for index, benefit in enumerate(spec["benefits"], start=1):
                    treatment = self._treatment(ctx, benefit.get("treatment")) if benefit.get("treatment") else False
                    values = {
                        "plan_id": plan.id, "name": benefit["name"], "sequence": index * 10,
                        "benefit_type": benefit["type"], "active": True,
                        "treatment_id": treatment.id if treatment else False,
                        "stackable": False,
                    }
                    if benefit["type"] == "discount_percent":
                        values["discount_percent"] = benefit["value"]
                    elif benefit["type"] == "quota":
                        values.update({"quota_unit": "session", "quota_value": benefit["value"], "total_term_quota": benefit["value"]})
                    elif benefit["type"] == "priority":
                        values.update({"priority_order": 100, "booking_priority_delta": benefit["priority"]})
                    self._ensure(
                        ctx, counters, f"DEMO-MEM-BEN-{spec['code']}-{benefit['code']}",
                        "membership.plan.benefit", values,
                        RESET_FRESH_DB_ONLY, 590, scenario_key="SCN-MEMBERSHIP-01",
                    )
                plan.action_activate()
            self._neutralize_membership_event(ctx, counters, plan, spec["code"])
            plans[spec["code"]] = plan
        return plans

    def _ensure_insurance_manager_actor(self, ctx):
        return self._ensure_commercial_manager_actor(ctx)

    def _ensure_insurance(self, ctx, counters):
        manager_user = self._ensure_insurance_manager_actor(ctx)
        branch = self._branch(ctx)
        insurer, _ = self._ensure(
            ctx, counters, "DEMO-INSURER-DEMOCARE", "res.partner",
            {
                "name": "DemoCare Assurance Indonesia (Synthetic)",
                "company_type": "company", "is_company": True, "company_id": ctx.run.company_id.id,
                "email": ctx.safe_mode_service.synthetic_email("democare-insurer"),
                "phone": "+62 811 0000 8800", "is_insurer": True,
                "insurer_code": "DEMOCARE", "payer_external_id": "DEMO-PAYER-001",
                "payer_authorization_email": ctx.safe_mode_service.synthetic_email("democare-authorization"),
                "payer_claim_email": ctx.safe_mode_service.synthetic_email("democare-claims"),
                "payer_portal_url": "https://invalid.clinicone-demo.invalid/payer",
                "active": True,
            }, RESET_DEACTIVATE, 580, scenario_key="SCN-INSURANCE-01",
        )
        plans = {}
        for spec in INSURANCE_SPECS[:PROFILE_INSURANCE_COUNTS[ctx.profile]]:
            plan, _ = self._ensure(
                ctx, counters, f"DEMO-INS-PLAN-{spec['code']}", "clinic.insurance.plan",
                {
                    "name": spec["name"], "code": f"DEMO-{spec['code']}",
                    "company_id": ctx.run.company_id.id,
                    "branch_id": branch.id if branch else False,
                    "insurer_partner_id": insurer.id, "state": "draft",
                    "authorization_required_default": spec["authorization"],
                    "default_coverage_percent": spec["coverage"], "default_copay_percent": spec["copay"],
                    "default_deductible_amount": spec["deductible"], "annual_limit": spec["annual"],
                    "eligibility_valid_days": 30, "authorization_valid_days": 30,
                    "notes": "Synthetic payer plan master; no patient policy or authorization is created in Prompt 11.",
                }, RESET_FRESH_DB_ONLY, 575, scenario_key="SCN-INSURANCE-01",
                update=False,
            )
            if plan.state == "draft":
                self._ensure(
                    ctx, counters, f"DEMO-INS-RULE-{spec['code']}-GEN", "clinic.insurance.plan.rule",
                    {
                        "plan_id": plan.id, "sequence": 10, "active": True,
                        "authorization_required": spec["authorization"],
                        "coverage_percent": spec["coverage"], "copay_percent": spec["copay"],
                        "deductible_amount": spec["deductible"], "maximum_amount": 0.0,
                        "maximum_quantity": 0.0,
                        "note": "Generic synthetic coverage rule. Service-specific rules are added only when justified.",
                    }, RESET_FRESH_DB_ONLY, 570, scenario_key="SCN-INSURANCE-01",
                )
                plan.with_user(manager_user).action_activate()
            plans[spec["code"]] = plan
        return insurer, plans

    def _ensure_wallet_rules(self, ctx, counters, membership_plans):
        active_plan_ids = [plan.id for plan in membership_plans.values() if plan.state == "active"]
        self._ensure(
            ctx, counters, "DEMO-WALLET-RULE-GLOBAL", "clinic.wallet.rule",
            {
                "name": "ClinicOne Demo Wallet Responsible Use",
                "sequence": 10, "active": True, "company_id": ctx.run.company_id.id,
                "scope": "global", "membership_tier_ids": [(6, 0, active_plan_ids)],
                "date_start": fields.Date.to_date(ctx.run.anchor_date), "date_end": False,
                "min_amount": 0.0, "max_amount": 2000000.0,
                "daily_amount_limit": 3000000.0, "daily_tx_limit": 10,
                "monthly_amount_limit": 15000000.0, "monthly_tx_limit": 100,
                "max_ratio_per_invoice": 100.0,
                "currency_id": ctx.run.company_id.currency_id.id,
            }, RESET_DEACTIVATE, 560, scenario_key="SCN-WALLET-01",
        )

    def generate(self, ctx, scenario):
        self._preflight(ctx)
        self._ensure_commercial_manager_actor(ctx)
        counters = self._counters()
        self._ensure_packages(ctx, counters)
        memberships = self._ensure_memberships(ctx, counters)
        self._ensure_insurance(ctx, counters)
        self._ensure_wallet_rules(ctx, counters, memberships)
        return counters

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def validate(self, ctx, scenario):
        failures = []
        for spec in PACKAGE_SPECS[:PROFILE_PACKAGE_COUNTS[ctx.profile]]:
            package = self._resolve(ctx, f"DEMO-PKG-{spec['code']}", "clinic.package")
            if package.state != "active" or not package.line_ids or not package.product_template_id:
                failures.append(f"Package {spec['code']} is not active with components and service product.")
            pending = ctx.env["clinic.package.integration.event"].with_user(
                self._ensure_commercial_manager_actor(ctx)
            ).search_count([
                ("source_model", "=", "clinic.package"), ("source_res_id", "=", package.id),
                ("state", "in", ["pending", "processing"]),
            ])
            if ctx.run.safe_mode and pending:
                failures.append(f"Package {spec['code']} left pending integration events in Demo Safe Mode.")

        membership_plans = []
        for spec in MEMBERSHIP_SPECS[:PROFILE_MEMBERSHIP_COUNTS[ctx.profile]]:
            plan = self._resolve(ctx, f"DEMO-MEM-PLAN-{spec['code']}", "membership.plan")
            membership_plans.append(plan)
            if plan.state != "active" or not plan.benefit_ids or not plan.product_id:
                failures.append(f"Membership {spec['code']} is not active with benefits and service product.")
            pending = ctx.env["membership.integration.event"].with_user(
                self._ensure_commercial_manager_actor(ctx)
            ).search_count([
                ("source_model", "=", "membership.plan"), ("source_res_id", "=", plan.id),
                ("state", "in", ["pending", "failed"]),
            ])
            if ctx.run.safe_mode and pending:
                failures.append(f"Membership {spec['code']} left actionable integration events in Demo Safe Mode.")

        for spec in INSURANCE_SPECS[:PROFILE_INSURANCE_COUNTS[ctx.profile]]:
            plan = self._resolve(ctx, f"DEMO-INS-PLAN-{spec['code']}", "clinic.insurance.plan")
            if plan.state != "active" or not plan.rule_ids or not plan.insurer_partner_id.is_insurer:
                failures.append(f"Insurance plan {spec['code']} is not active with insurer and coverage rule.")

        wallet_rule = self._resolve(ctx, "DEMO-WALLET-RULE-GLOBAL", "clinic.wallet.rule")
        if not wallet_rule.active or wallet_rule.company_id != ctx.run.company_id:
            failures.append("Wallet rule master is inactive or company-misaligned.")

        forbidden_transaction_models = {
            "clinic.package.allocation", "clinic.package.usage", "membership.contract",
            "clinic.wallet", "clinic.wallet.transaction", "clinic.insurance.policy",
            "clinic.insurance.authorization", "clinic.billing.invoice", "clinic.billing.payment",
        }
        generated_models = set(ctx.run.reference_ids.filtered(lambda ref: ref.generator_key == self.key).mapped("model_name"))
        premature = sorted(forbidden_transaction_models & generated_models)
        if premature:
            failures.append("Prompt 11 created premature transaction models: " + ", ".join(premature))
        return failures

    def reset(self, ctx, scenario):
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}


