"""MASTER PROMPT 21 — source-backed ClinicOne management reports."""

from datetime import timedelta

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


REPORT_SOURCE_GAPS = {
    "FIN-INS": "clinic.insurance.authorization; request_date; insurance plans are not authorizations",
    "OPS-INV": "clinic.treatment.product.usage; date_usage; state=done; product masters are not consumption",
    "OPS-MEM": "membership.contract; start_date; membership plans are not member contracts",
    "OPS-WALLET": "clinic.wallet.transaction; date; state=posted; wallet rules are not ledger transactions",
    "CLN-PROC": "clinic.procedure.session; date_start; encounter procedures and treatment sessions are different models",
}

REPORT_SPECS = (
    ("FIN-REV", "clinic_reports.report_definition_fin_revenue", "INVOICE_COUNT", True),
    ("FIN-AR", "clinic_reports.report_definition_fin_receivables", "AR_INVOICE_COUNT", True),
    ("FIN-AP", "clinic_reports.report_definition_fin_payables", "AP_DOCUMENT_COUNT", True),
    ("FIN-CASH", "clinic_reports.report_definition_fin_cashflow", "CASH_TX_COUNT", False),
    ("FIN-ACC", "clinic_reports.report_definition_fin_accounting", "JOURNAL_ITEM_COUNT", True),
    ("FIN-TAX-ID", "clinic_reports.report_definition_fin_tax", "TAX_REPORT_COUNT", False),
    ("FIN-INS", "clinic_reports.report_definition_fin_insurance", "AUTH_COUNT", True),
    ("OPS-BOOK", "clinic_reports.report_definition_ops_booking", "BOOKING_COUNT", True),
    ("OPS-QUEUE", "clinic_reports.report_definition_ops_queue", "QUEUE_COUNT", True),
    ("OPS-ROOM", "clinic_reports.report_definition_ops_room", "ROOM_ASSIGNMENTS", True),
    ("OPS-INV", "clinic_reports.report_definition_ops_inventory", "INVENTORY_USAGE_COUNT", True),
    ("OPS-MEM", "clinic_reports.report_definition_ops_membership", "MEMBERSHIP_CONTRACTS", True),
    ("OPS-WALLET", "clinic_reports.report_definition_ops_wallet", "WALLET_TX_COUNT", True),
    ("CLN-ENC", "clinic_reports.report_definition_clinical_encounter", "ENCOUNTER_COUNT", True),
    ("CLN-PROC", "clinic_reports.report_definition_clinical_procedure", "PROCEDURE_SESSION_COUNT", True),
    ("CLN-TRIAGE", "clinic_reports.report_definition_clinical_triage", "TRIAGE_COUNT", True),
    ("CLN-AE", "clinic_reports.report_definition_clinical_adverse", "AE_COUNT", False),
    ("CLN-POST", "clinic_reports.report_definition_clinical_postcare", "POSTCARE_PLAN_COUNT", True),
    ("CLN-FB", "clinic_reports.report_definition_clinical_feedback", "FEEDBACK_COUNT", True),
)

REPORT_ENGINE_METHODS = {
    "fin_revenue": "_generate_fin_revenue",
    "fin_receivables": "_generate_fin_receivables",
    "fin_payables": "_generate_fin_payables",
    "fin_cashflow": "_generate_fin_cashflow",
    "fin_accounting": "_generate_fin_accounting",
    "fin_tax": "_generate_fin_tax",
    "fin_insurance": "_generate_fin_insurance",
    "ops_booking": "_generate_ops_booking",
    "ops_queue": "_generate_ops_queue",
    "ops_room": "_generate_ops_room",
    "ops_inventory": "_generate_ops_inventory",
    "ops_membership": "_generate_ops_membership",
    "ops_wallet": "_generate_ops_wallet",
    "clinical_encounter": "_generate_clinical_encounter",
    "clinical_procedure": "_generate_clinical_procedure",
    "clinical_triage": "_generate_clinical_triage",
    "clinical_adverse": "_generate_clinical_adverse",
    "clinical_postcare": "_generate_clinical_postcare",
    "clinical_feedback": "_generate_clinical_feedback",
}

REPORT_MODEL_CONTRACTS = {
    "clinic.report.definition": {"code", "report_key", "family", "state", "allow_branch_filter"},
    "clinic.report.run": {"name", "definition_id", "company_id", "branch_id", "date_from", "date_to", "state", "metric_ids", "detail_ids", "csv_file"},
    "clinic.report.metric": {"run_id", "code", "value", "metric_type"},
    "clinic.report.detail": {"run_id", "source_model", "source_res_id", "event_date"},
}


@GENERATOR_REGISTRY.register
class ManagementReportsGenerator(BaseDemoGenerator):
    key = "management.reports"
    phase = "21_reports"
    sequence = 1000
    depends_on = ("operations.future_pipeline",)
    scenario_keys = ("SCN-REPORT-01",)
    owned_models = (
        "clinic.report.run", "clinic.report.metric", "clinic.report.detail",
        "clinic.insurance.policy", "clinic.insurance.authorization", "membership.contract",
        "clinic.treatment.product.usage", "clinic.wallet", "clinic.wallet.transaction",
        "clinic.procedure.session", "stock.move", "stock.location", "product.category",
        "product.product", "account.account", "account.journal", "account.move",
    )
    required_groups = ("clinic_reports.group_reports_manager",)

    @staticmethod
    def _counts():
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _actor(record, user, ctx):
        return record.with_user(user).with_company(ctx.run.company_id).with_context(
            allowed_company_ids=[ctx.run.company_id.id], prefetch_fields=False,
        )

    def _resolve(self, ctx, key, model, missing_ok=False, user=None):
        record = ctx.reference_service.resolve(ctx.run, key, model, missing_ok=missing_ok, record_user=user)
        if not record:
            return record
        return self._actor(record, user, ctx) if user else record.with_company(ctx.run.company_id).with_context(
            allowed_company_ids=[ctx.run.company_id.id], prefetch_fields=False,
        )

    def _prepare_actor(self, ctx):
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        group = ctx.env.ref("clinic_reports.group_reports_manager")
        if group not in manager.group_ids:
            manager.write({"group_ids": [(4, group.id)]})
        return manager

    def _whole_path_preflight(self, ctx, manager):
        issues = []
        for model_name, required_fields in REPORT_MODEL_CONTRACTS.items():
            missing = sorted(required_fields - set(ctx.env[model_name]._fields))
            if missing:
                issues.append(f"{model_name} missing fields: {', '.join(missing)}")
        Run = ctx.env["clinic.report.run"]
        for report_key, method_name in REPORT_ENGINE_METHODS.items():
            if not hasattr(Run, method_name):
                issues.append(f"clinic.report.run missing {method_name} for {report_key}")
        for method_name in ("action_generate", "action_finalize", "action_reset_to_draft"):
            if not hasattr(Run, method_name):
                issues.append(f"clinic.report.run missing workflow method {method_name}")

        seen_keys = set()
        for code, xmlid, _metric, _nonzero in REPORT_SPECS:
            definition = ctx.env.ref(xmlid, raise_if_not_found=False)
            if not definition:
                issues.append(f"missing report definition {xmlid}")
                continue
            if definition.code != code or definition.state != "active":
                issues.append(f"{xmlid} must be Active with code {code}")
            if definition.report_key in seen_keys:
                issues.append(f"duplicate report engine key {definition.report_key}")
            seen_keys.add(definition.report_key)
            if definition.report_key not in REPORT_ENGINE_METHODS:
                issues.append(f"{code} has no declared report engine")

        actor_run = self._actor(ctx.env["clinic.report.run"].browse(), manager, ctx)
        for mode in ("read", "create", "write"):
            try:
                actor_run.check_access(mode)
            except Exception as error:
                issues.append(f"DEMO-USER-MGR cannot {mode} clinic.report.run: {error}")
        if not manager.has_group("clinic_reports.group_reports_manager"):
            issues.append("DEMO-USER-MGR lacks clinic_reports.group_reports_manager")
        if issues:
            raise UserError(_("MASTER PROMPT 21 whole-path runtime preflight failed: %s") % "; ".join(issues))

    def _ensure_run(self, ctx, counts, manager, code, definition, refresh=False):
        key = f"DEMO-REPORT-{code}"
        Model = self._actor(ctx.env["clinic.report.run"], manager, ctx)
        values = {
            "name": key,
            "definition_id": definition.id,
            "company_id": ctx.run.company_id.id,
            "branch_id": False,
            "date_from": ctx.run.anchor_date - timedelta(days=365),
            "date_to": ctx.run.anchor_date + timedelta(days=90),
            "include_details": True,
            "detail_limit": 1000,
            "notes": "Synthetic source-backed MASTER PROMPT 21 report; no source transaction is mutated.",
        }
        run, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name="clinic.report.run",
            generator_key=self.key, scenario_key="SCN-REPORT-01",
            create_callback=lambda: Model.create(values), update_callback=None,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1300,
            record_user=manager,
        )
        run = self._actor(run, manager, ctx)
        counts[status if status in counts else "created"] += 1
        if refresh and run.state == "ready":
            run.action_reset_to_draft()
        if run.state in {"draft", "failed"}:
            if run.state == "failed":
                run.action_reset_to_draft()
            run.action_generate()
        if run.state != "ready":
            raise UserError(_("Report %s did not reach Ready state: %s") % (code, run.error_message or run.state))
        return run

    def generate(self, ctx, scenario, refresh=False, include_sources=True):
        counts = self._counts()
        manager = self._prepare_actor(ctx)
        self._whole_path_preflight(ctx, manager)
        from .source_journeys import ReportSourceJourneys
        source_counts = ReportSourceJourneys(self, ctx, manager).generate() if include_sources else {}
        for status, count in source_counts.items():
            counts[status] += count
        for code, xmlid, _primary_metric, _must_be_nonzero in REPORT_SPECS:
            self._ensure_run(ctx, counts, manager, code, ctx.env.ref(xmlid), refresh=refresh)
        return counts

    def _validate_source_journeys(self, ctx, manager):
        from .source_journeys import ReportSourceJourneys
        ReportSourceJourneys(self, ctx, manager).validate(reports=True)

    def validate(self, ctx, scenario):
        issues = []
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        self._validate_source_journeys(ctx, manager)
        for code, _xmlid, primary_metric, must_be_nonzero in REPORT_SPECS:
            run = self._resolve(ctx, f"DEMO-REPORT-{code}", "clinic.report.run", True, manager)
            if not run or run.state != "ready":
                issues.append(f"{code} report is missing or not Ready")
                continue
            if not run.metric_ids or not run.csv_file:
                issues.append(f"{code} has no governed metric/CSV output")
                continue
            metric = run.metric_ids.filtered(lambda item: item.code == primary_metric)[:1]
            if not metric:
                issues.append(f"{code} missing primary metric {primary_metric}")
            elif must_be_nonzero and metric.value <= 0:
                issues.append(f"{code} primary metric {primary_metric} unexpectedly zero")
                if code in REPORT_SOURCE_GAPS:
                    issues.append(
                        f"{code} source coverage gap: {REPORT_SOURCE_GAPS[code]}; "
                        f"report period {run.date_from} through {run.date_to}; "
                        "the report metric must not be fabricated or waived"
                    )
            invalid_details = run.detail_ids.filtered(lambda item: not item.source_model or not item.source_res_id)
            if invalid_details:
                issues.append(f"{code} contains details without source provenance")
        if issues:
            raise UserError(_("Report readiness failed: %s") % "; ".join(issues))
        return []

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}

















