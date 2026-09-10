"""MASTER PROMPT 22 — source-backed KPI, Dashboard and Analytics evidence."""

from datetime import timedelta

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


DASHBOARD_CODES = ("EXECUTIVE", "FINANCIAL", "OPERATIONS", "CLINICAL", "ROOM", "EXPERIENCE")
ANALYTICS_PERIODS = (
    ("HISTORICAL", -365, -181),
    ("PRIOR", -180, -1),
    ("CURRENT_FUTURE", 0, 90),
)

DASHBOARD_CONTRACTS = {
    "clinic.dashboard.board": {"code", "company_id", "state", "widget_ids", "snapshot_ids"},
    "clinic.dashboard.widget": {"board_id", "definition_id", "metric_code", "active"},
    "clinic.dashboard.snapshot": {"name", "board_id", "company_id", "date_from", "date_to", "state", "line_ids"},
    "clinic.dashboard.snapshot.line": {"snapshot_id", "widget_id", "metric_id", "report_run_id", "status", "value"},
}
ANALYTICS_CONTRACTS = {
    "clinic.analytics.kpi": {"code", "source_key", "state", "forecastable"},
    "clinic.analytics.snapshot": {"name", "company_id", "date_from", "date_to", "state", "line_ids"},
    "clinic.analytics.snapshot.line": {"snapshot_id", "kpi_id", "value", "source_model", "source_count"},
    "clinic.analytics.forecast": {"name", "kpi_id", "as_of_date", "state", "point_ids"},
    "clinic.analytics.forecast.point": {"forecast_id", "point_type", "period_start", "period_end"},
}


class ManagementEvidenceBase(BaseDemoGenerator):
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

    def _manager(self, ctx, group_xmlid):
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        group = ctx.env.ref(group_xmlid)
        if group not in manager.group_ids:
            manager.write({"group_ids": [(4, group.id)]})
        return manager

    @staticmethod
    def _model_contract_issues(ctx, contracts):
        issues = []
        for model_name, required_fields in contracts.items():
            missing = sorted(required_fields - set(ctx.env[model_name]._fields))
            if missing:
                issues.append(f"{model_name} missing fields: {', '.join(missing)}")
        return issues

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return {"skipped": 1}


@GENERATOR_REGISTRY.register
class ManagementDashboardGenerator(ManagementEvidenceBase):
    key = "management.dashboard"
    phase = "22_management"
    sequence = 1100
    depends_on = ("management.reports",)
    scenario_keys = ("SCN-DASH-01",)
    owned_models = ("clinic.dashboard.snapshot", "clinic.dashboard.snapshot.line")
    required_groups = ("clinic_dashboard.group_dashboard_manager",)

    def _preflight(self, ctx, manager):
        issues = self._model_contract_issues(ctx, DASHBOARD_CONTRACTS)
        Board = ctx.env["clinic.dashboard.board"]
        for method in ("_refresh_snapshot", "_validate_runtime_scope", "_ensure_report_run"):
            if not hasattr(Board, method):
                issues.append(f"clinic.dashboard.board missing {method}")
        boards = self._actor(Board, manager, ctx).search([
            ("company_id", "=", ctx.run.company_id.id), ("code", "in", list(DASHBOARD_CODES)),
        ])
        found = set(boards.mapped("code"))
        if found != set(DASHBOARD_CODES):
            issues.append(f"dashboard board set incomplete: {sorted(set(DASHBOARD_CODES) - found)}")
        for board in boards:
            if board.state != "active" or not board.widget_ids:
                issues.append(f"dashboard {board.code} must be Active with widgets")
        ActorBoard = self._actor(Board.browse(), manager, ctx)
        for mode in ("read", "write"):
            try:
                ActorBoard.check_access(mode)
            except Exception as error:
                issues.append(f"DEMO-USER-MGR cannot {mode} clinic.dashboard.board: {error}")
        if not manager.has_group("clinic_dashboard.group_dashboard_manager"):
            issues.append("DEMO-USER-MGR lacks Dashboard Manager")
        if issues:
            raise UserError(_("MASTER PROMPT 22 Dashboard whole-path preflight failed: %s") % "; ".join(issues))
        return boards

    def generate(self, ctx, scenario):
        counts = self._counts()
        manager = self._manager(ctx, "clinic_dashboard.group_dashboard_manager")
        boards = self._preflight(ctx, manager)
        date_from = ctx.run.anchor_date - timedelta(days=365)
        date_to = ctx.run.anchor_date + timedelta(days=90)
        for board in boards.sorted(lambda item: DASHBOARD_CODES.index(item.code)):
            key = f"DEMO-DASH-SNAPSHOT-{board.code}"
            existing = self._resolve(ctx, key, "clinic.dashboard.snapshot", True, manager)
            if existing:
                counts["reused"] += 1
                continue
            snapshot = board._refresh_snapshot(date_from, date_to, branch=None, snapshot_name=key)
            ctx.reference_service.bind(
                run=ctx.run, demo_key=key, record=snapshot,
                generator_key=self.key, scenario_key="SCN-DASH-01",
                reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1400,
                record_user=manager,
            )
            counts["created"] += 1
        return counts

    def validate(self, ctx, scenario):
        issues = []
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        for code in DASHBOARD_CODES:
            snapshot = self._resolve(ctx, f"DEMO-DASH-SNAPSHOT-{code}", "clinic.dashboard.snapshot", True, manager)
            if not snapshot or snapshot.state != "ready" or not snapshot.line_ids:
                issues.append(f"{code} Dashboard snapshot is missing, empty, or not Ready")
                continue
            broken = snapshot.line_ids.filtered(lambda line: line.status in {"no_data", "unsupported_scope", "error"})
            if broken:
                issues.append(f"{code} Dashboard has {len(broken)} unpopulated KPI cards")
            unproven = snapshot.line_ids.filtered(lambda line: not line.report_run_id or not line.metric_id)
            if unproven:
                issues.append(f"{code} Dashboard has KPI cards without Report provenance")
        return issues


@GENERATOR_REGISTRY.register
class ManagementAnalyticsGenerator(ManagementEvidenceBase):
    key = "management.analytics"
    phase = "22_management"
    sequence = 1110
    depends_on = ("management.dashboard",)
    scenario_keys = ("SCN-ANALYTICS-01",)
    owned_models = ("clinic.analytics.snapshot", "clinic.analytics.snapshot.line", "clinic.analytics.forecast", "clinic.analytics.forecast.point", "clinic.analytics.insight")
    required_groups = ("clinic_analytics.group_analytics_manager",)

    def _preflight(self, ctx, manager):
        issues = self._model_contract_issues(ctx, ANALYTICS_CONTRACTS)
        Snapshot = ctx.env["clinic.analytics.snapshot"]
        Forecast = ctx.env["clinic.analytics.forecast"]
        Engine = ctx.env["clinic.analytics.engine"]
        for Model, methods in ((Snapshot, ("action_generate", "action_generate_insights")), (Forecast, ("action_run",)), (Engine, ("evaluate", "historical_periods", "future_periods"))):
            for method in methods:
                if not hasattr(Model, method):
                    issues.append(f"{Model._name} missing {method}")
        kpis = self._actor(ctx.env["clinic.analytics.kpi"], manager, ctx).search([("state", "=", "active"), ("active", "=", True)])
        if len(kpis) != 17:
            issues.append(f"expected 17 active Analytics KPIs, found {len(kpis)}")
        for kpi in kpis:
            if not hasattr(Engine, f"_metric_{kpi.source_key}"):
                issues.append(f"KPI {kpi.code} has no fixed-source adapter")
        for model_name in ("clinic.analytics.snapshot", "clinic.analytics.forecast"):
            Model = self._actor(ctx.env[model_name].browse(), manager, ctx)
            for mode in ("read", "create", "write"):
                try:
                    Model.check_access(mode)
                except Exception as error:
                    issues.append(f"DEMO-USER-MGR cannot {mode} {model_name}: {error}")
        integration_enabled = ctx.env["ir.config_parameter"].get_param("clinic.analytics.publish_integration_events", "false")
        if str(integration_enabled).strip().lower() in {"1", "true", "yes", "on"}:
            issues.append("clinic.analytics.publish_integration_events must be disabled in Demo Safe Mode")
        if not ctx.run.safe_mode:
            issues.append("Demo Safe Mode is required")
        if issues:
            raise UserError(_("MASTER PROMPT 22 Analytics whole-path preflight failed: %s") % "; ".join(issues))
        return kpis

    def _ensure_snapshot(self, ctx, counts, manager, label, start_offset, end_offset):
        key = f"DEMO-ANL-SNAPSHOT-{label}"
        Model = self._actor(ctx.env["clinic.analytics.snapshot"], manager, ctx)
        values = {"name": key, "company_id": ctx.run.company_id.id, "branch_id": False,
                  "date_from": ctx.run.anchor_date + timedelta(days=start_offset),
                  "date_to": ctx.run.anchor_date + timedelta(days=end_offset),
                  "notes": "Synthetic source-backed Prompt-22 KPI snapshot."}
        snapshot, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name="clinic.analytics.snapshot",
            generator_key=self.key, scenario_key="SCN-ANALYTICS-01",
            create_callback=lambda: Model.create(values), update_callback=None,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1450,
            record_user=manager,
        )
        snapshot = self._actor(snapshot, manager, ctx)
        counts[status if status in counts else "created"] += 1
        if snapshot.state in {"draft", "failed"}:
            snapshot.action_generate()
        if snapshot.state != "done":
            raise UserError(_("Analytics snapshot %s failed: %s") % (label, snapshot.error_message or snapshot.state))
        return snapshot

    def _ensure_forecast(self, ctx, counts, manager):
        key = "DEMO-ANL-FORECAST-BOOKING"
        Model = self._actor(ctx.env["clinic.analytics.forecast"], manager, ctx)
        kpi = ctx.env.ref("clinic_analytics.kpi_booking_count")
        values = {"name": key, "company_id": ctx.run.company_id.id, "branch_id": False,
                  "kpi_id": kpi.id, "as_of_date": ctx.run.anchor_date,
                  "frequency": "month", "history_periods": 12, "horizon_periods": 3,
                  "method": "linear_trend", "moving_average_window": 3,
                  "notes": "Transparent deterministic booking-volume forecast."}
        forecast, _reference, status = ctx.reference_service.ensure_record(
            run=ctx.run, demo_key=key, model_name="clinic.analytics.forecast",
            generator_key=self.key, scenario_key="SCN-ANALYTICS-01",
            create_callback=lambda: Model.create(values), update_callback=None,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1460,
            record_user=manager,
        )
        forecast = self._actor(forecast, manager, ctx)
        counts[status if status in counts else "created"] += 1
        if forecast.state in {"draft", "failed"}:
            forecast.action_run()
        if forecast.state != "done":
            raise UserError(_("Booking Analytics forecast failed: %s") % (forecast.error_message or forecast.state))
        return forecast

    def generate(self, ctx, scenario):
        counts = self._counts()
        manager = self._manager(ctx, "clinic_analytics.group_analytics_manager")
        self._preflight(ctx, manager)
        for period in ANALYTICS_PERIODS:
            self._ensure_snapshot(ctx, counts, manager, *period)
        self._ensure_forecast(ctx, counts, manager)
        return counts

    def validate(self, ctx, scenario):
        issues = []
        manager = self._resolve(ctx, "DEMO-USER-MGR", "res.users")
        snapshots = [self._resolve(ctx, f"DEMO-ANL-SNAPSHOT-{label}", "clinic.analytics.snapshot", True, manager) for label, _start, _end in ANALYTICS_PERIODS]
        for snapshot in snapshots:
            if not snapshot or snapshot.state != "done" or len(snapshot.line_ids) != 17:
                issues.append("An Analytics period is missing, incomplete, or not Ready")
                continue
            if snapshot.line_ids.filtered(lambda line: not line.source_model or not line.source_domain_json):
                issues.append(f"{snapshot.name} has KPI lines without fixed-source provenance")
        current = snapshots[-1] if snapshots else False
        if current and not current.line_ids.filtered(lambda line: line.source_count > 0):
            issues.append("Current Analytics snapshot has no populated source")
        forecast = self._resolve(ctx, "DEMO-ANL-FORECAST-BOOKING", "clinic.analytics.forecast", True, manager)
        if not forecast or forecast.state != "done" or len(forecast.point_ids.filtered(lambda point: point.point_type == "actual")) != 12 or len(forecast.point_ids.filtered(lambda point: point.point_type == "forecast")) != 3:
            issues.append("Booking forecast does not contain the deterministic 12-history/3-future series")
        return issues



