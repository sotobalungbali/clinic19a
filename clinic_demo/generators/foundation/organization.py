




"""ClinicOne company/branch/location foundation generated through owner APIs."""

from odoo import _
from odoo.exceptions import AccessError, UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_DEACTIVATE, RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


BRANCH_SPECS = (
    {
        "key": "DEMO-BRANCH-001",
        "name": "ClinicOne Demo Central",
        "code": "DEMO-CEN",
        "city": "Denpasar",
        "zip": "80111",
        "sequence": 10,
    },
    {
        "key": "DEMO-BRANCH-002",
        "name": "ClinicOne Demo South",
        "code": "DEMO-STH",
        "city": "Badung",
        "zip": "80361",
        "sequence": 20,
    },
    {
        "key": "DEMO-BRANCH-003",
        "name": "ClinicOne Demo East",
        "code": "DEMO-EST",
        "city": "Gianyar",
        "zip": "80511",
        "sequence": 30,
    },
)

# Full Enterprise intentionally exceeds the Prompt-04 minimum of ten locations.
LOCATION_SPECS = {
    "compact": (
        ("001", "SITE", "Clinic Site", "site", None, 5, False),
        ("001", "RECEPTION", "Reception & Check-in", "kiosk", "SITE", 2, True),
        ("001", "TREAT-A", "Treatment Room A", "room", "SITE", 1, True),
    ),
    "standard": (
        ("001", "SITE", "Clinic Site", "site", None, 5, False),
        ("001", "RECEPTION", "Reception & Check-in", "kiosk", "SITE", 2, True),
        ("001", "CONSULT", "Consultation Room", "room", "SITE", 1, True),
        ("001", "TREAT-A", "Treatment Room A", "room", "SITE", 1, True),
        ("002", "SITE", "Clinic Site", "site", None, 4, False),
        ("002", "TREAT-A", "Treatment Room A", "room", "SITE", 1, True),
    ),
    "full_enterprise": (
        ("001", "SITE", "Clinic Site", "site", None, 6, False),
        ("001", "RECEPTION", "Reception & Check-in", "kiosk", "SITE", 3, True),
        ("001", "CONSULT", "Consultation Room", "room", "SITE", 1, True),
        ("001", "TREAT-A", "Treatment Room A", "room", "SITE", 1, True),
        ("001", "STORAGE", "Clinical Storage", "storage", "SITE", 2, False),
        ("002", "SITE", "Clinic Site", "site", None, 5, False),
        ("002", "RECEPTION", "Reception & Check-in", "kiosk", "SITE", 2, True),
        ("002", "CONSULT", "Consultation Room", "room", "SITE", 1, True),
        ("002", "TREAT-A", "Treatment Room A", "room", "SITE", 1, True),
        ("003", "SITE", "Clinic Site", "site", None, 4, False),
        ("003", "RECEPTION", "Reception & Check-in", "kiosk", "SITE", 2, True),
        ("003", "TREAT-A", "Treatment Room A", "room", "SITE", 1, True),
    ),
}


@GENERATOR_REGISTRY.register
class ClinicOrganizationFoundationGenerator(BaseDemoGenerator):
    key = "foundation.organization"
    phase = "08_foundation"
    sequence = 110
    depends_on = ("foundation.native",)
    scenario_keys = ("SCN-FOUNDATION-01",)
    owned_models = ("clinic.branch", "clinic.branch.location")
    required_groups = ("clinic_branch.group_branch_manager",)

    @staticmethod
    def _profile_branch_count(profile):
        return {
            "compact": 1,
            "standard": 2,
            "full_enterprise": 3,
        }[profile]

    def _country_and_state(self, ctx):
        country = ctx.env["res.country"].search([("code", "=", "ID")], limit=1)
        state = ctx.env["res.country.state"].search([
            ("country_id", "=", country.id),
            ("name", "ilike", "Bali"),
        ], limit=1) if country else ctx.env["res.country.state"]
        return country, state

    @staticmethod
    def _warehouse_from_branch(branch):
        """Return owner-selected warehouse without bypassing native stock security."""
        try:
            warehouse = branch.default_warehouse_id
            if warehouse:
                # Accessing a normal field proves the current user may read the
                # native record; no sudo or guessed stock-manager privilege.
                warehouse.company_id.id
            return warehouse
        except AccessError:
            return branch.env["stock.warehouse"]

    @staticmethod
    def _warehouse_stock_location(warehouse):
        if not warehouse:
            return warehouse.env["stock.location"] if warehouse else False
        try:
            if "lot_stock_id" in warehouse._fields:
                return warehouse.lot_stock_id
        except AccessError:
            return warehouse.env["stock.location"]
        return warehouse.env["stock.location"]

    def _branch_values(self, ctx, spec, country, state, shared_warehouse=False):
        values = {
            "name": spec["name"],
            "code": spec["code"],
            "company_id": ctx.run.company_id.id,
            "sequence": spec["sequence"],
            "active": True,
            "tz": ctx.run.timezone or "UTC",
            "email": f"{spec['code'].lower()}@clinicone-demo.invalid",
            "street": "Synthetic Demo Clinic Avenue",
            "city": spec["city"],
            "zip": spec["zip"],
            "report_header": "ClinicOne Enterprise Demo",
        }
        if country:
            values["country_id"] = country.id
        if state:
            values["state_id"] = state.id
        if shared_warehouse:
            values["default_warehouse_id"] = shared_warehouse.id
        return values

    def _ensure_branch(self, ctx, spec, country, state, shared_warehouse=False):
        values = self._branch_values(
            ctx,
            spec,
            country,
            state,
            shared_warehouse=shared_warehouse,
        )

        def creator():
            return ctx.env["clinic.branch"].create(values)

        def updater(branch):
            # Only demo-owned branch presentation fields are refreshed.
            branch.write({
                "name": values["name"],
                "sequence": values["sequence"],
                "active": True,
                "tz": values["tz"],
                "email": values["email"],
                "street": values["street"],
                "city": values["city"],
                "zip": values["zip"],
                **({"country_id": country.id} if country else {}),
                **({"state_id": state.id} if state else {}),
            })

        return ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=spec["key"],
            model_name="clinic.branch",
            generator_key=self.key,
            create_callback=creator,
            scenario_key=ctx.scenario.key,
            reset_policy=RESET_DEACTIVATE,
            update_callback=updater,
            reset_sequence=200,
        )

    def _location_values(
        self,
        ctx,
        branch,
        code,
        name,
        location_type,
        capacity,
        allow_booking,
        parent=False,
        country=False,
        state=False,
        calendar=False,
        warehouse=False,
        stock_location=False,
    ):
        values = {
            "name": name,
            "code": code,
            "company_id": ctx.run.company_id.id,
            "branch_id": branch.id,
            "type": location_type,
            "active": True,
            "allow_booking": allow_booking,
            "capacity": capacity,
            "booking_strategy": "capacity",
            "tz": branch.tz or ctx.run.timezone or "UTC",
            "city": branch.city,
        }
        if parent:
            values["parent_id"] = parent.id
        if country:
            values["country_id"] = country.id
        if state:
            values["state_id"] = state.id
        if calendar:
            values["resource_calendar_id"] = calendar.id
        if warehouse:
            values["warehouse_id"] = warehouse.id
        if stock_location:
            values["stock_location_id"] = stock_location.id
        return values

    def _ensure_location(
        self,
        ctx,
        branch,
        branch_token,
        local_token,
        name,
        location_type,
        capacity,
        allow_booking,
        parent=False,
        country=False,
        state=False,
        calendar=False,
        warehouse=False,
        stock_location=False,
    ):
        demo_key = f"DEMO-LOC-B{branch_token}-{local_token}"
        code = f"B{branch_token}-{local_token}"
        values = self._location_values(
            ctx,
            branch,
            code,
            name,
            location_type,
            capacity,
            allow_booking,
            parent=parent,
            country=country,
            state=state,
            calendar=calendar,
            warehouse=warehouse,
            stock_location=stock_location,
        )

        def creator():
            return ctx.env["clinic.branch.location"].create(values)

        def updater(location):
            safe_values = {
                "name": values["name"],
                "active": True,
                "type": values["type"],
                "allow_booking": values["allow_booking"],
                "capacity": values["capacity"],
                "booking_strategy": values["booking_strategy"],
                "tz": values["tz"],
                "parent_id": values.get("parent_id", False),
            }
            location.write(safe_values)

        depth_sequence = 330 if parent else 320
        return ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=demo_key,
            model_name="clinic.branch.location",
            generator_key=self.key,
            create_callback=creator,
            scenario_key=ctx.scenario.key,
            reset_policy=RESET_DEACTIVATE,
            update_callback=updater,
            reset_sequence=depth_sequence,
        )

    def generate(self, ctx, scenario):
        company = ctx.run.company_id
        country, state = self._country_and_state(ctx)

        calendar = ctx.reference_service.resolve(
            ctx.run,
            "DEMO-CALENDAR-COMPANY",
            expected_model="resource.calendar",
            missing_ok=True,
        )

        counters = {
            "created": 0,
            "reused": 0,
            "updated": 0,
            "skipped": 0,
            "warning": 0,
            "error": 0,
        }

        branch_count = self._profile_branch_count(ctx.profile)
        branch_records = {}
        shared_warehouse = False

        for index, spec in enumerate(BRANCH_SPECS[:branch_count], start=1):
            branch, _reference, status = self._ensure_branch(
                ctx,
                spec,
                country,
                state,
                shared_warehouse=shared_warehouse,
            )
            counters[status] += 1
            branch_records[f"{index:03d}"] = branch

            if branch.sequence_id:
                try:
                    sequence_key = f"{spec['key']}-SEQUENCE"
                    existing_sequence_ref = ctx.reference_service._reference(
                        ctx.run, sequence_key
                    )
                    ctx.reference_service.bind(
                        run=ctx.run,
                        demo_key=sequence_key,
                        record=branch.sequence_id,
                        generator_key=self.key,
                        scenario_key=scenario.key,
                        ownership_kind="created",
                        reset_policy=RESET_FRESH_DB_ONLY,
                        reset_sequence=120,
                    )
                    if not existing_sequence_ref:
                        counters["created"] += 1
                    else:
                        counters["reused"] += 1
                except AccessError:
                    counters["warning"] += 1
                    ctx.logging_service.log(
                        run=ctx.run,
                        level="warning",
                        phase_key=self.phase,
                        generator_key=self.key,
                        scenario_key=scenario.key,
                        operation="organization_foundation",
                        model_name="ir.sequence",
                        message=(
                            f"{branch.display_name} has an owner-generated branch sequence, "
                            "but the current user cannot read ir.sequence. The business "
                            "branch remains valid and no security bypass was used."
                        ),
                    )

            if not shared_warehouse:
                shared_warehouse = self._warehouse_from_branch(branch)
                if shared_warehouse:
                    try:
                        ctx.reference_service.bind_reused(
                            run=ctx.run,
                            demo_key="DEMO-WAREHOUSE-PRIMARY",
                            record=shared_warehouse,
                            generator_key=self.key,
                            scenario_key=scenario.key,
                            reset_policy=RESET_FRESH_DB_ONLY,
                            reset_sequence=100,
                        )
                        counters["reused"] += 1
                    except AccessError:
                        counters["warning"] += 1
                        shared_warehouse = False
                        ctx.logging_service.log(
                            run=ctx.run,
                            level="warning",
                            phase_key=self.phase,
                            generator_key=self.key,
                            scenario_key=scenario.key,
                            operation="organization_foundation",
                            model_name="stock.warehouse",
                            message=(
                                "Clinic Branch found a default warehouse through its owner "
                                "workflow, but the current demo operator cannot read native "
                                "warehouse records. Stock mapping is deferred without sudo."
                            ),
                        )

        # Respect an existing non-demo default branch. Set the demo default only
        # when the selected company has none.
        if not company.default_branch_id and branch_records:
            branch_records["001"].action_set_company_default()
            counters["updated"] += 1
        elif (
            company.default_branch_id
            and company.default_branch_id.id not in [branch.id for branch in branch_records.values()]
        ):
            counters["warning"] += 1
            ctx.logging_service.log(
                run=ctx.run,
                level="warning",
                phase_key=self.phase,
                generator_key=self.key,
                scenario_key=scenario.key,
                operation="organization_foundation",
                model_name="res.company",
                message=(
                    "The selected company already has a non-demo default branch. "
                    "ClinicOne Demo preserved it instead of overwriting reused configuration."
                ),
            )

        # Locations are created parent-first inside each branch.
        sites = {}
        for (
            branch_token,
            local_token,
            name,
            location_type,
            parent_token,
            capacity,
            allow_booking,
        ) in LOCATION_SPECS[ctx.profile]:
            branch = branch_records[branch_token]
            parent = sites.get(branch_token) if parent_token else False
            warehouse = self._warehouse_from_branch(branch)
            stock_location = self._warehouse_stock_location(warehouse) if warehouse else False

            location, _reference, status = self._ensure_location(
                ctx,
                branch,
                branch_token,
                local_token,
                name,
                location_type,
                capacity,
                allow_booking,
                parent=parent,
                country=country,
                state=state,
                calendar=calendar,
                warehouse=warehouse,
                stock_location=stock_location,
            )
            counters[status] += 1

            if location.resource_id:
                resource_key = f"DEMO-RESOURCE-B{branch_token}-{local_token}"
                existing_resource_ref = ctx.reference_service._reference(
                    ctx.run, resource_key
                )
                ctx.reference_service.bind(
                    run=ctx.run,
                    demo_key=resource_key,
                    record=location.resource_id,
                    generator_key=self.key,
                    scenario_key=scenario.key,
                    ownership_kind="created",
                    reset_policy=RESET_DEACTIVATE,
                    reset_sequence=340,
                )
                if not existing_resource_ref:
                    counters["created"] += 1
                else:
                    counters["reused"] += 1
            elif allow_booking:
                counters["warning"] += 1
                ctx.logging_service.log(
                    run=ctx.run,
                    level="warning",
                    phase_key=self.phase,
                    generator_key=self.key,
                    scenario_key=scenario.key,
                    operation="organization_foundation",
                    model_name="resource.resource",
                    demo_key=f"DEMO-RESOURCE-B{branch_token}-{local_token}",
                    message=(
                        f"{location.display_name} allows booking but the owner addon "
                        "could not create its optional resource.resource. Prompt 12 "
                        "will validate detailed scheduling resources."
                    ),
                )

            if local_token == "SITE":
                sites[branch_token] = location

        return counters

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def validate(self, ctx, scenario):
        expected_branches = self._profile_branch_count(ctx.profile)
        expected_locations = len(LOCATION_SPECS[ctx.profile])

        branch_refs = ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id),
            ("generator_key", "=", self.key),
            ("model_name", "=", "clinic.branch"),
            ("record_status", "=", "bound"),
        ])
        location_refs = ctx.env["clinic.demo.reference"].search([
            ("run_id", "=", ctx.run.id),
            ("generator_key", "=", self.key),
            ("model_name", "=", "clinic.branch.location"),
            ("record_status", "=", "bound"),
        ])

        branches = ctx.env["clinic.branch"].browse(branch_refs.mapped("res_id")).exists()
        locations = ctx.env["clinic.branch.location"].browse(
            location_refs.mapped("res_id")
        ).exists()

        errors = []
        if len(branches) != expected_branches:
            errors.append(
                f"Expected {expected_branches} demo branches, found {len(branches)}."
            )
        if len(locations) != expected_locations:
            errors.append(
                f"Expected {expected_locations} demo branch locations, found {len(locations)}."
            )
        if branches.filtered(lambda branch: branch.company_id != ctx.run.company_id):
            errors.append("One or more demo branches belong to the wrong company.")
        if locations.filtered(
            lambda location: (
                location.company_id != ctx.run.company_id
                or location.branch_id.company_id != ctx.run.company_id
            )
        ):
            errors.append("One or more demo locations have inconsistent branch/company scope.")
        if locations.filtered(lambda location: location.capacity <= 0):
            errors.append("One or more demo locations have non-positive capacity.")

        if errors:
            raise UserError(_("Organization foundation validation failed: %s") % "; ".join(errors))

        warnings = []
        if not any(branch.default_warehouse_id for branch in branches):
            warnings.append(
                "No demo branch has a default stock warehouse. Clinical organization "
                "is valid, but inventory readiness must be resolved before stock-consuming journeys."
            )
        return warnings


# Prompt-08 generators are deliberately idempotent; missing-record repair reuses
# the same source-valid generation contract rather than a second code path.
























