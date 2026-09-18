"""MASTER PROMPT 23 - bounded, read-only enterprise acceptance gates."""

from datetime import date, datetime

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.generator_registry import GENERATOR_REGISTRY
from ...services.fingerprint_service import SourceFingerprintService
from ...services.reset_service import DemoResetService


# Temporal semantics are owned by each business model.  Equality is valid for
# instantaneous workflow transitions (for example Triage start/complete in the
# same ORM transaction), while reservable intervals must have positive length.
DATETIME_INTERVAL_CONTRACTS = {
    "booking.booking": ("start_datetime", "end_datetime", "strict"),
    "booking.room.blackout": ("start_datetime", "end_datetime", "strict"),
    "booking.resource.blackout": ("start_datetime", "end_datetime", "strict"),
    "booking.doctor.blackout": ("start_datetime", "end_datetime", "strict"),
    "clinic.room.session": ("start_datetime", "end_datetime", "strict"),
    "clinic.treatment.session": ("start_datetime", "end_datetime", "strict"),
    "clinic.triage.session": ("start_datetime", "end_datetime", "non_decreasing"),
    "clinic.care.plan.line": ("start_datetime", "end_datetime", "non_decreasing"),
    "clinical.imaging.device.downtime": (
        "start_datetime", "end_datetime", "non_decreasing",
    ),
}


def _counts(checked):
    return {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "skipped": int(checked),
        "warning": 0,
        "error": 0,
    }


class AcceptanceGate(BaseDemoGenerator):
    """A checkpoint that proves existing source data; it never creates business rows."""

    owned_models = ()
    required_groups = ()

    def _references(self, ctx):
        return ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id),
            ("record_status", "=", "bound"),
        ], order="demo_key, id")

    @staticmethod
    def _record(ctx, reference):
        try:
            # Bounded read-only provenance lookup: this never creates, writes,
            # unlinks, transitions, or exposes the business record to RPC.
            return ctx.env[reference.model_name].sudo().browse(reference.res_id).exists()
        except KeyError:
            return False

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return _counts(0)

    def validate(self, ctx, scenario):
        self.generate(ctx, scenario)
        return []

    @staticmethod
    def _fail(label, issues):
        if issues:
            raise UserError(_("MASTER PROMPT 23 %(label)s gate failed: %(issues)s") % {
                "label": label,
                "issues": "; ".join(issues[:25]),
            })


@GENERATOR_REGISTRY.register
class StructuralAcceptanceGenerator(AcceptanceGate):
    key = "validation.structural"
    phase = "23_validation"
    sequence = 1200
    depends_on = ("management.analytics",)
    scenario_keys = ("SCN-ANALYTICS-01",)

    def generate(self, ctx, scenario):
        issues = []
        references = self._references(ctx)
        seen = set()
        for reference in references:
            if reference.demo_key in seen:
                issues.append(f"duplicate reference {reference.demo_key}")
            seen.add(reference.demo_key)
            record = self._record(ctx, reference)
            if not record:
                issues.append(f"missing {reference.demo_key}")
                continue
            if "company_id" in record._fields and record.company_id and record.company_id != ctx.run.company_id:
                issues.append(f"{reference.demo_key} belongs to another company")
            if "branch_id" in record._fields and record.branch_id and "company_id" in record.branch_id._fields:
                if record.branch_id.company_id != ctx.run.company_id:
                    issues.append(f"{reference.demo_key} has a cross-company branch")
        if not references:
            issues.append("no bound demo references exist")
        self._fail("structural", issues)
        return _counts(len(references))


@GENERATOR_REGISTRY.register
class TemporalAcceptanceGenerator(AcceptanceGate):
    key = "validation.temporal"
    phase = "23_validation"
    sequence = 1210
    depends_on = ("validation.structural",)
    scenario_keys = ("SCN-PIPELINE-01",)

    def generate(self, ctx, scenario):
        issues = []
        checked = 0
        future_seen = historical_seen = False
        for reference in self._references(ctx):
            record = self._record(ctx, reference)
            if not record:
                continue
            values = []
            for field_name in ("date", "event_date", "appointment_date", "start_datetime", "scheduled_at", "date_from", "date_to"):
                if field_name not in record._fields:
                    continue
                value = record[field_name]
                if isinstance(value, datetime):
                    value = value.date()
                if isinstance(value, date):
                    values.append((field_name, value))
            for field_name, value in values:
                checked += 1
                future_seen = future_seen or value > ctx.run.anchor_date
                historical_seen = historical_seen or value < ctx.run.anchor_date
            if {"date_from", "date_to"} <= set(record._fields):
                start, end = record.date_from, record.date_to
                if start and end and start > end:
                    issues.append(f"{reference.demo_key} has date_from after date_to")
            interval = DATETIME_INTERVAL_CONTRACTS.get(record._name)
            if interval:
                start_field, end_field, rule = interval
                start, end = record[start_field], record[end_field]
                invalid = bool(
                    start and end and (
                        end < start or (rule == "strict" and end == start)
                    )
                )
                if invalid:
                    issues.append(
                        f"{reference.demo_key} violates {record._name} "
                        f"{rule} {start_field}/{end_field} contract"
                    )
        if checked and not historical_seen:
            issues.append("no historical evidence was found")
        if checked and not future_seen:
            issues.append("no future evidence was found")
        self._fail("temporal", issues)
        return _counts(checked)


@GENERATOR_REGISTRY.register
class WorkflowAcceptanceGenerator(AcceptanceGate):
    key = "validation.workflow"
    phase = "23_validation"
    sequence = 1220
    depends_on = ("validation.temporal",)
    scenario_keys = ("SCN-ENCOUNTER-01",)

    EXPECTED = {
        "DEMO-BILL-001": {"confirmed", "posted", "paid"},
        "DEMO-AR-001": {"posted", "partial", "overdue", "paid"},
        "DEMO-AP-001": {"approved", "posted", "partial", "paid"},
        "DEMO-INC-001": {"investigation"},
    }

    def generate(self, ctx, scenario):
        issues = []
        checked = 0
        Reference = ctx.env["clinic.demo.reference"]
        for key, expected in self.EXPECTED.items():
            reference = Reference.search([("run_id", "=", ctx.run.id), ("demo_key", "=", key)], limit=1)
            if not reference:
                issues.append(f"required workflow reference {key} is absent")
                continue
            record = self._record(ctx, reference)
            if not record or "state" not in record._fields:
                issues.append(f"{key} has no readable workflow state")
                continue
            checked += 1
            if record.state not in expected:
                issues.append(f"{key} state {record.state!r} is outside {sorted(expected)}")
        self._fail("workflow", issues)
        return _counts(checked)


@GENERATOR_REGISTRY.register
class JourneyAcceptanceGenerator(AcceptanceGate):
    key = "validation.journey_exception"
    phase = "23_validation"
    sequence = 1230
    depends_on = ("validation.workflow",)
    scenario_keys = ("SCN-INCIDENT-01",)

    REQUIRED_PREFIXES = (
        "DEMO-PAT-", "DEMO-BOOK-", "DEMO-QUEUE-", "DEMO-TRIAGE-",
        "DEMO-ENC-", "DEMO-SESSION-", "DEMO-IMG-", "DEMO-EMAR-",
        "DEMO-BILL-", "DEMO-AR-", "DEMO-AP-", "DEMO-FB-",
        "DEMO-QUAL-", "DEMO-INC-", "DEMO-API-",
    )

    def generate(self, ctx, scenario):
        keys = set(self._references(ctx).mapped("demo_key"))
        issues = [f"no bound evidence for {prefix}" for prefix in self.REQUIRED_PREFIXES if not any(key.startswith(prefix) for key in keys)]
        self._fail("golden journey/exception", issues)
        return _counts(len(self.REQUIRED_PREFIXES))


@GENERATOR_REGISTRY.register
class AnalyticsAcceptanceGenerator(AcceptanceGate):
    key = "validation.analytics_evidence"
    phase = "23_validation"
    sequence = 1240
    depends_on = ("validation.journey_exception",)
    scenario_keys = ("SCN-DASH-01",)

    REQUIRED_PREFIXES = ("DEMO-REPORT-", "DEMO-DASH-SNAPSHOT-", "DEMO-ANL-SNAPSHOT-", "DEMO-ANL-FORECAST-")

    def generate(self, ctx, scenario):
        keys = set(self._references(ctx).mapped("demo_key"))
        issues = [f"no source-backed evidence for {prefix}" for prefix in self.REQUIRED_PREFIXES if not any(key.startswith(prefix) for key in keys)]
        self._fail("analytics", issues)
        return _counts(len(self.REQUIRED_PREFIXES))


@GENERATOR_REGISTRY.register
class IntegrityAcceptanceGenerator(AcceptanceGate):
    key = "validation.integrity_reset_regeneration"
    phase = "23_validation"
    sequence = 1250
    depends_on = ("validation.analytics_evidence",)
    scenario_keys = ("SCN-PATIENT-RET-01",)

    def generate(self, ctx, scenario):
        issues = []
        references = self._references(ctx)
        reset = DemoResetService(ctx.env)
        for reference in references:
            try:
                inspection = reset.inspect(reference, technical=True)
            except Exception as error:
                issues.append(f"{reference.demo_key} reset contract is unresolved: {error}")
                continue
            if inspection.get("action") not in {
                "delete_safe", "cancel_then_delete", "deactivate", "retain",
                "retain_immutable", "fresh_db_reset_only", "reverse_then_retain",
            }:
                issues.append(f"{reference.demo_key} has unsupported reset action {inspection.get('action')!r}")
        missing = ctx.env["clinic.demo.reference"].search_count([
            ("run_id", "=", ctx.run.id), ("record_status", "=", "missing"),
        ])
        if missing:
            issues.append(f"{missing} missing references require Regenerate Missing")
        generators = {generator.key: generator for generator in GENERATOR_REGISTRY.all()}
        if len(generators) != 35:
            issues.append(f"fresh-database registry expected 35 generators, found {len(generators)}")
        compatibility = SourceFingerprintService(ctx.env).check_compatibility(run=ctx.run)
        if not compatibility["compatible"]:
            issues.append(f"source/database compatibility failed: {compatibility['message']}")
        done = set(ctx.run.checkpoint_ids.filtered(
            lambda checkpoint: checkpoint.state == "done"
        ).mapped("generator_key"))
        required = set(generators) - {self.key}
        incomplete = sorted(required - done)
        if incomplete:
            issues.append(f"pre-final checkpoint closure incomplete: {', '.join(incomplete)}")
        self._fail("integrity/reset/regeneration", issues)
        return _counts(len(references))

















