"""MASTER PROMPT 18 — deterministic commercial and finance journeys."""

from datetime import timedelta

from odoo import Command, _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


COMMERCIAL_SEQUENCE = ("commercial.billing", "commercial.ar", "commercial.ap")
COMMERCIAL_GROUPS = (
    "base.group_partner_manager",
    "clinic_billing.group_clinic_billing_manager",
    "clinic_treatment_session.group_treatment_session_manager",
    "clinic_ar.group_clinic_ar_manager",
    "clinic_ap.group_clinic_ap_manager",
    "clinic_membership.group_clinic_membership_manager",
    "account.group_account_invoice",
)
COMMERCIAL_CONTRACTS = {
    "clinic.treatment": ({"product_id", "product_tmpl_id", "base_price"},
                         {"get_service_product", "get_default_price"}),
    "clinic.treatment.session": ({"company_id", "branch_id", "state", "treatment_id",
                                   "billing_invoice_id", "line_ids"},
                                 {"action_create_clinic_billing", "action_prepare_billing"}),
    "clinic.treatment.session.line": ({"session_id", "display_type", "product_id",
                                        "product_uom_id", "quantity", "is_billable",
                                        "price_unit", "consumption_state"},
                                       {"prepare_billing_payload_line"}),
    "clinic.billing.invoice": ({"name", "state", "patient_id", "clinic_patient_id",
                                 "invoice_date", "invoice_date_due", "line_ids", "move_id"},
                                {"action_confirm", "action_generate_account_move",
                                 "action_post_account_move", "action_create_or_open_ar"}),
    "clinic.ar.invoice": ({"name", "state", "billing_id", "partner_id", "move_id",
                            "amount_total", "amount_residual", "due_date"},
                           {"create_from_billing", "action_post"}),
    "clinic.ap": ({"name", "state", "vendor_id", "reference", "invoice_date",
                    "invoice_date_due", "line_ids", "move_id", "amount_total"},
                   {"action_submit", "action_approve", "action_post"}),
    "clinic.ap.line": ({"ap_id", "name", "product_id", "product_uom_id",
                         "quantity", "price_unit", "tax_ids"}, set()),
    "product.product": ({"purchase_ok", "uom_id", "supplier_taxes_id"}, set()),
    "account.move": ({"state", "move_type", "partner_id", "invoice_date",
                      "invoice_date_due", "amount_total", "amount_residual"}, {"action_post"}),
}


class CommercialFinanceBase(BaseDemoGenerator):
    required_groups = ("base.group_user",)

    @staticmethod
    def _counters():
        return {"created": 0, "reused": 0, "updated": 0,
                "skipped": 0, "warning": 0, "error": 0}

    def _resolve(self, ctx, key, model, missing_ok=False, record_user=None):
        return ctx.reference_service.resolve(
            ctx.run, key, model, missing_ok=missing_ok, record_user=record_user,
        )

    def _manager(self, ctx):
        return self._resolve(ctx, "DEMO-USER-MGR", "res.users")

    @staticmethod
    def _actor(record, manager, ctx, branch_id=False):
        values = {
            "allowed_company_ids": [ctx.run.company_id.id],
            "allowed_branch_ids": manager.allowed_branch_ids.ids,
        }
        if branch_id:
            values["branch_id"] = branch_id
        return record.with_user(manager).with_company(ctx.run.company_id).with_context(**values)

    def _reference_res_id(self, ctx, key, expected_model):
        reference = ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id), ("demo_key", "=", key),
        ], limit=1)
        if not reference or reference.model_name != expected_model:
            return False
        return reference.res_id

    def _reconcile_actor_scope(self, ctx, manager):
        """Grant the synthetic enterprise manager the complete demo branch scope.

        IDs come from exact provenance references, so no branch-protected
        business record is read before the actor is correctly scoped.
        """
        count = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        branch_ids = []
        for number in range(1, count + 1):
            key = f"DEMO-BRANCH-{number:03d}"
            branch_id = self._reference_res_id(ctx, key, "clinic.branch")
            if not branch_id:
                raise UserError(_("MASTER PROMPT 18 actor-scope preflight missing %s") % key)
            branch_ids.append(branch_id)
        values = {}
        missing_company_ids = {ctx.run.company_id.id} - set(manager.company_ids.ids)
        missing_branch_ids = set(branch_ids) - set(manager.allowed_branch_ids.ids)
        if missing_company_ids:
            values["company_ids"] = [Command.link(item) for item in sorted(missing_company_ids)]
        if missing_branch_ids:
            values["allowed_branch_ids"] = [Command.link(item) for item in sorted(missing_branch_ids)]
        if values:
            manager.write(values)
        return branch_ids

    def _prepare_whole_path(self, ctx):
        """Reconcile the bounded demo actor, then inspect all Prompt-18 paths."""
        manager = self._manager(ctx)
        demo_branch_ids = self._reconcile_actor_scope(ctx, manager)
        groups = ctx.env["res.groups"]
        for xmlid in COMMERCIAL_GROUPS:
            groups |= ctx.env.ref(xmlid)
        missing_groups = groups - manager.group_ids
        if missing_groups:
            manager.write({"group_ids": [Command.link(group.id) for group in missing_groups]})

        issues = []
        for model_name, (fields, methods) in COMMERCIAL_CONTRACTS.items():
            Model = ctx.env[model_name]
            absent = sorted(fields - set(Model._fields))
            if absent:
                issues.append(f"{model_name} missing fields: {', '.join(absent)}")
            absent_methods = sorted(method for method in methods if not hasattr(Model, method))
            if absent_methods:
                issues.append(f"{model_name} missing methods: {', '.join(absent_methods)}")
        relations = {
            ("clinic.treatment.session", "billing_invoice_id"): "clinic.billing.invoice",
            ("clinic.billing.invoice", "clinic_patient_id"): "clinic.patient",
            ("clinic.billing.invoice", "patient_id"): "res.partner",
            ("clinic.billing.invoice", "move_id"): "account.move",
            ("clinic.ar.invoice", "billing_id"): "clinic.billing.invoice",
            ("clinic.ar.invoice", "move_id"): "account.move",
            ("clinic.ap", "move_id"): "account.move",
            ("clinic.ap.line", "ap_id"): "clinic.ap",
            ("product.product", "uom_id"): "uom.uom",
        }
        for (model_name, field_name), expected in relations.items():
            field = ctx.env[model_name]._fields.get(field_name)
            actual = getattr(field, "comodel_name", None) if field else None
            if actual != expected:
                issues.append(f"{model_name}.{field_name} comodel is {actual or 'missing'}, expected {expected}")
        for model_name, operations in {
            "clinic.treatment.session": ("read", "write"),
            "clinic.treatment.session.line": ("read", "write"),
            "clinic.billing.invoice": ("read", "create", "write"),
            "clinic.ar.invoice": ("read", "create", "write"),
            "clinic.ap": ("read", "create", "write"),
            "clinic.ap.line": ("read", "create", "write"),
            # The bounded AP path creates one synthetic vendor. It does not
            # mutate existing Contacts, so write is intentionally not claimed.
            "res.partner": ("read", "create"),
            "product.product": ("read",),
            "uom.uom": ("read",),
            "account.journal": ("read",),
            "account.account": ("read",),
            "account.move": ("read", "create", "write"),
        }.items():
            for operation in operations:
                try:
                    self._actor(ctx.env[model_name], manager, ctx).browse().check_access(operation)
                except Exception as error:
                    issues.append(f"DEMO-USER-MGR cannot {operation} {model_name}: {error}")

        session = self._resolve(
            ctx, "DEMO-SESSION-001", "clinic.treatment.session",
            missing_ok=True, record_user=manager,
        )
        session = self._actor(session, manager, ctx) if session else session
        service_line = self._resolve(
            ctx, "DEMO-SESSION-LINE-001", "clinic.treatment.session.line",
            missing_ok=True, record_user=manager,
        )
        service_line = self._actor(service_line, manager, ctx) if service_line else service_line
        product = self._resolve(
            ctx, "DEMO-PRODUCT-MED-PARA-500", "product.product",
            missing_ok=True, record_user=manager,
        )
        if not session:
            issues.append("required source DEMO-SESSION-001 is missing")
        elif session.state != "done":
            issues.append("DEMO-SESSION-001 must be Done")
        elif session.branch_id.id not in demo_branch_ids:
            issues.append("DEMO-SESSION-001 branch is outside the explicit demo actor scope")
        if not service_line:
            issues.append("required deferred billing line DEMO-SESSION-LINE-001 is missing")
        elif session and service_line.session_id != session:
            issues.append("DEMO-SESSION-LINE-001 belongs to another Treatment Session")
        elif service_line.display_type != "line" or service_line.consumption_state != "consumed":
            issues.append("DEMO-SESSION-LINE-001 is not a consumed monetary service line")
        treatment = session.treatment_id if session else False
        billing_product = treatment.get_service_product() if treatment else False
        billing_price = treatment.get_default_price() if treatment else 0.0
        if not treatment or not billing_product:
            issues.append("DEMO-SESSION-001 Treatment has no owner-resolved service product")
        if billing_price <= 0:
            issues.append("DEMO-SESSION-001 Treatment has no positive owner-resolved price")
        if not product:
            # Stable fallback from the treatment catalog, still reference-owned.
            product = self._resolve(
                ctx, "DEMO-PRODUCT-MED-CET-10", "product.product",
                missing_ok=True, record_user=manager,
            )
        if not product:
            issues.append("no deterministic referenced product is available for AP")
        elif not product.purchase_ok:
            issues.append(f"{product.display_name} is not purchase-enabled")
        company = ctx.run.company_id
        Journal = self._actor(ctx.env["account.journal"], manager, ctx)
        if not Journal.search_count([("company_id", "=", company.id), ("type", "=", "sale")]):
            issues.append("company has no Sales Journal")
        if not Journal.search_count([("company_id", "=", company.id), ("type", "=", "purchase")]):
            issues.append("company has no Purchase Journal")
        Account = self._actor(ctx.env["account.account"], manager, ctx)
        for account_type in ("income", "expense", "asset_receivable", "liability_payable"):
            if not Account.search_count([
                *Account._check_company_domain(company),
                ("account_type", "=", account_type),
            ]):
                issues.append(f"company has no {account_type} account")
        if issues:
            raise UserError(_("MASTER PROMPT 18 whole-path runtime preflight failed: %s") % "; ".join(issues))
        return manager, session, service_line, billing_product, billing_price, product, demo_branch_ids[0]

    def _prepare_deferred_billing_line(
        self, ctx, manager, session, line, product, price,
    ):
        """Complete Prompt-16's explicitly deferred billing projection once."""
        if line.is_billable and line.product_id == product and line.price_unit == price:
            return line
        if line.is_billable or line.product_id or line.price_unit:
            raise UserError(_(
                "DEMO-SESSION-LINE-001 differs from its exact deferred-billing shape; "
                "refusing an ambiguous financial mutation."
            ))
        actor_line = self._actor(line, manager, ctx, branch_id=session.branch_id.id)
        actor_line.write({
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "is_billable": True,
            "price_unit": price,
            "tax_ids": [Command.set(product.taxes_id.filtered(
                lambda tax: not tax.company_id or tax.company_id == ctx.run.company_id
            ).ids)],
            "note_internal": "Prompt-18 deterministic billing projection of the consumed service.",
        })
        payloads = self._actor(session, manager, ctx, session.branch_id.id).action_prepare_billing()["lines"]
        if len(payloads) != 1 or payloads[0].get("session_line_id") != line.id:
            raise UserError(_("Treatment Session owner billing projection is not exactly one deterministic line."))
        return actor_line

    def _bind(self, ctx, counters, key, record, scenario, reset_sequence, manager):
        existing = self._resolve(
            ctx, key, record._name, missing_ok=True, record_user=manager,
        )
        if existing:
            counters["reused"] += 1
            return existing
        ctx.reference_service.bind(
            ctx.run, key, record, self.key, scenario_key=scenario,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=reset_sequence,
            record_user=manager,
        )
        counters["created"] += 1
        return record

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        # Posted statutory ledgers are never deleted or silently put back in draft.
        return {"skipped": 1}


@GENERATOR_REGISTRY.register
class CommercialBillingGenerator(CommercialFinanceBase):
    key = "commercial.billing"
    phase = "18_commercial"
    sequence = 750
    depends_on = ("clinical.telemedicine",)
    scenario_keys = ("SCN-BILLING-01",)
    owned_models = ("clinic.billing.invoice", "account.move")

    def generate(self, ctx, scenario):
        counters = self._counters()
        manager, session, line, billing_product, billing_price, _ap_product, _branch_id = self._prepare_whole_path(ctx)
        self._prepare_deferred_billing_line(
            ctx, manager, session, line, billing_product, billing_price,
        )
        billing = self._resolve(
            ctx, "DEMO-BILL-001", "clinic.billing.invoice",
            missing_ok=True, record_user=manager,
        )
        if not billing:
            self._actor(session, manager, ctx, session.branch_id.id).with_context(
                clinic_demo_billing_name="DEMO-BILL-001"
            ).action_create_clinic_billing()
            billing = self._actor(session, manager, ctx, session.branch_id.id).billing_invoice_id
            self._actor(billing, manager, ctx, session.branch_id.id).write({
                "invoice_date": ctx.run.anchor_date - timedelta(days=45),
                "invoice_date_due": ctx.run.anchor_date - timedelta(days=15),
            })
            self._bind(ctx, counters, "DEMO-BILL-001", billing, scenario.key, 980, manager)
        else:
            counters["reused"] += 1
        billing = self._actor(billing, manager, ctx, session.branch_id.id)
        if billing.state == "draft":
            billing.action_confirm()
        if not billing.move_id:
            billing.action_generate_account_move()
        if billing.move_id.state != "posted":
            billing.action_post_account_move()
        self._bind(ctx, counters, "DEMO-BILL-MOVE-001", billing.move_id, scenario.key, 990, manager)
        return counters

    def validate(self, ctx, scenario):
        manager = self._manager(ctx)
        billing = self._resolve(ctx, "DEMO-BILL-001", "clinic.billing.invoice", missing_ok=True, record_user=manager)
        return [] if billing and billing.move_id.state == "posted" and billing.amount_total > 0 else ["DEMO-BILL-001 is not a positive posted accounting journey"]


@GENERATOR_REGISTRY.register
class CommercialARGenerator(CommercialFinanceBase):
    key = "commercial.ar"
    phase = "18_commercial"
    sequence = 760
    depends_on = ("commercial.billing",)
    scenario_keys = ("SCN-AR-01",)
    owned_models = ("clinic.ar.invoice",)

    def generate(self, ctx, scenario):
        counters = self._counters()
        manager, session, _line, _billing_product, _billing_price, _ap_product, _branch_id = self._prepare_whole_path(ctx)
        billing = self._resolve(ctx, "DEMO-BILL-001", "clinic.billing.invoice", record_user=manager)
        billing = self._actor(billing, manager, ctx, session.branch_id.id)
        ar = self._resolve(ctx, "DEMO-AR-001", "clinic.ar.invoice", missing_ok=True, record_user=manager)
        if not ar:
            ar = self._actor(ctx.env["clinic.ar.invoice"], manager, ctx, session.branch_id.id).with_context(
                clinic_demo_ar_name="DEMO-AR-001"
            ).create_from_billing(billing)
            self._bind(ctx, counters, "DEMO-AR-001", ar, scenario.key, 1000, manager)
        else:
            counters["reused"] += 1
        if ar.state == "draft":
            self._actor(ar, manager, ctx, session.branch_id.id).action_post()
        return counters

    def validate(self, ctx, scenario):
        manager = self._manager(ctx)
        ar = self._resolve(ctx, "DEMO-AR-001", "clinic.ar.invoice", missing_ok=True, record_user=manager)
        return [] if ar and ar.state == "posted" and ar.move_id and ar.amount_residual > 0 else ["DEMO-AR-001 is not an outstanding posted receivable"]


@GENERATOR_REGISTRY.register
class CommercialAPGenerator(CommercialFinanceBase):
    key = "commercial.ap"
    phase = "18_commercial"
    sequence = 770
    depends_on = ("commercial.ar",)
    scenario_keys = ("SCN-AP-01",)
    owned_models = ("res.partner", "clinic.ap", "account.move")

    def generate(self, ctx, scenario):
        counters = self._counters()
        manager, _session, _line, _billing_product, _billing_price, product, branch_id = self._prepare_whole_path(ctx)
        vendor = self._resolve(ctx, "DEMO-VENDOR-001", "res.partner", missing_ok=True, record_user=manager)
        if not vendor:
            vendor = self._actor(ctx.env["res.partner"], manager, ctx, branch_id).create({
                "name": "Synthetic Clinical Supplies Vendor", "supplier_rank": 1,
                "company_type": "company", "company_id": ctx.run.company_id.id,
                "ref": "DEMO-VENDOR-001",
                "branch_id": branch_id,
            })
            self._bind(ctx, counters, "DEMO-VENDOR-001", vendor, scenario.key, 1010, manager)
        else:
            counters["reused"] += 1
        ap = self._resolve(ctx, "DEMO-AP-001", "clinic.ap", missing_ok=True, record_user=manager)
        if not ap:
            ap = self._actor(ctx.env["clinic.ap"], manager, ctx, branch_id).create({
                "name": "DEMO-AP-001", "company_id": ctx.run.company_id.id,
                "currency_id": ctx.run.company_id.currency_id.id, "vendor_id": vendor.id,
                "reference": "DEMO-VENDOR-BILL-001",
                "invoice_date": ctx.run.anchor_date - timedelta(days=35),
                "invoice_date_due": ctx.run.anchor_date - timedelta(days=5),
                "line_ids": [Command.create({
                    "name": "Synthetic clinical supplies replenishment",
                    "product_id": product.id, "product_uom_id": product.uom_id.id,
                    "quantity": 2.0, "price_unit": 175000.0,
                })],
            })
            self._bind(ctx, counters, "DEMO-AP-001", ap, scenario.key, 1020, manager)
        else:
            counters["reused"] += 1
        ap = self._actor(ap, manager, ctx, branch_id)
        if ap.state == "draft":
            ap.action_submit()
        if ap.state == "to_approve":
            ap.action_approve()
        if ap.state == "approved":
            ap.action_post()
        if ap.move_id:
            self._bind(ctx, counters, "DEMO-AP-MOVE-001", ap.move_id, scenario.key, 1030, manager)
        return counters

    def validate(self, ctx, scenario):
        manager = self._manager(ctx)
        ap = self._resolve(ctx, "DEMO-AP-001", "clinic.ap", missing_ok=True, record_user=manager)
        return [] if ap and ap.state == "posted" and ap.move_id.state == "posted" and ap.amount_total > 0 else ["DEMO-AP-001 is not a positive posted vendor payable"]






