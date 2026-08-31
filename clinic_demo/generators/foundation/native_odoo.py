
"""Source-required native Odoo foundation for ClinicOne demo generation.

Prompt 08 deliberately reuses the selected Demo Run company and native masters.
It does not create speculative accounting/localization masters that belong to
Prompt 18, and it never mutates a configured non-demo company merely to make a
demo look complete.
"""

from odoo import _
from odoo.exceptions import AccessError, UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


@GENERATOR_REGISTRY.register
class NativeOdooFoundationGenerator(BaseDemoGenerator):
    key = "foundation.native"
    phase = "08_foundation"
    sequence = 100
    depends_on = ()
    scenario_keys = ("SCN-FOUNDATION-01",)
    owned_models = ()
    required_groups = ()

    def _bind_reused(self, ctx, demo_key, record, business_reference=None):
        if not record:
            return 0
        ctx.reference_service.bind_reused(
            run=ctx.run,
            demo_key=demo_key,
            record=record,
            generator_key=self.key,
            scenario_key=ctx.scenario.key,
            reset_policy=RESET_FRESH_DB_ONLY,
        )
        return 1

    def generate(self, ctx, scenario):
        run = ctx.run
        company = run.company_id.exists()
        if not company:
            raise UserError(_("The Demo Run company no longer exists."))

        if not company.currency_id:
            raise UserError(
                _("The Demo Run company must have a base currency before ClinicOne demo generation.")
            )

        counters = {
            "created": 0,
            "reused": 0,
            "updated": 0,
            "skipped": 0,
            "warning": 0,
            "error": 0,
        }

        counters["reused"] += self._bind_reused(
            ctx,
            "DEMO-COMPANY-001",
            company,
        )
        counters["reused"] += self._bind_reused(
            ctx,
            "DEMO-CURRENCY-BASE",
            company.currency_id,
        )

        indonesia = ctx.env["res.country"].search([("code", "=", "ID")], limit=1)
        if not indonesia:
            raise UserError(
                _("Indonesia (country code ID) is required by ClinicOne localization but is missing.")
            )
        counters["reused"] += self._bind_reused(
            ctx,
            "DEMO-COUNTRY-ID",
            indonesia,
        )

        # Company country is intentionally not overwritten if already configured.
        if not company.country_id:
            counters["warning"] += 1
            ctx.logging_service.log(
                run=run,
                level="warning",
                generator_key=self.key,
                scenario_key=scenario.key,
                phase_key=self.phase,
                operation="native_foundation",
                model_name="res.company",
                demo_key="DEMO-COMPANY-001",
                message=(
                    "The selected Demo Run company has no country. Prompt 08 will "
                    "not silently mutate reused company configuration; Indonesian "
                    "localization readiness is enforced again in Prompt 18."
                ),
            )
        elif company.country_id.code != "ID":
            counters["warning"] += 1
            ctx.logging_service.log(
                run=run,
                level="warning",
                generator_key=self.key,
                scenario_key=scenario.key,
                phase_key=self.phase,
                operation="native_foundation",
                model_name="res.company",
                demo_key="DEMO-COMPANY-001",
                message=(
                    f"The selected company country is {company.country_id.code or '-'}, "
                    "not Indonesia. Clinical foundation can proceed, but Indonesia "
                    "localization/financial generation must resolve this in Prompt 18."
                ),
            )

        # resource.calendar is source-required by clinic.branch.location, but
        # the relation is optional. Reuse the company's native calendar when
        # the installed Odoo resource stack exposes one.
        calendar = False
        if "resource_calendar_id" in company._fields:
            calendar = company.resource_calendar_id
        if calendar:
            try:
                counters["reused"] += self._bind_reused(
                    ctx,
                    "DEMO-CALENDAR-COMPANY",
                    calendar,
                )
            except AccessError:
                counters["warning"] += 1
                ctx.logging_service.log(
                    run=run,
                    level="warning",
                    generator_key=self.key,
                    scenario_key=scenario.key,
                    phase_key=self.phase,
                    operation="native_foundation",
                    model_name="resource.calendar",
                    message=(
                        "A company working-hours calendar exists but the current "
                        "demo operator cannot read it. Prompt 12 will validate "
                        "resource scheduling without using sudo."
                    ),
                )
        else:
            counters["warning"] += 1
            ctx.logging_service.log(
                run=run,
                level="warning",
                generator_key=self.key,
                scenario_key=scenario.key,
                phase_key=self.phase,
                operation="native_foundation",
                model_name="resource.calendar",
                message=(
                    "No company working-hours calendar is linked. Branch locations "
                    "remain valid because that source field is optional; detailed "
                    "resource scheduling is completed in Prompt 12."
                ),
            )

        # Journal/tax/payment/ledger masters are intentionally not invented here.
        # Prompt 08 only records their source dependency boundary; Prompt 18
        # handles financial prerequisites after the clinical masters exist.
        return counters

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def validate(self, ctx, scenario):
        run = ctx.run
        failures = []
        warnings = []

        if not run.company_id.exists():
            failures.append("Demo Run company is missing.")
        if run.company_id and not run.company_id.currency_id:
            failures.append("Demo Run company has no currency.")

        indonesia = ctx.env["res.country"].search([("code", "=", "ID")], limit=1)
        if not indonesia:
            failures.append("Indonesia country master (code ID) is missing.")

        if run.company_id and run.company_id.country_id and run.company_id.country_id.code != "ID":
            warnings.append(
                "Demo Run company is not configured for Indonesia; Prompt 18 localization "
                "readiness will remain blocked until the owning company is configured."
            )

        if failures:
            raise UserError(_("Native foundation validation failed: %s") % "; ".join(failures))

        return warnings


# Prompt-08 generators are deliberately idempotent; missing-record repair reuses
# the same source-valid generation contract rather than a second code path.



