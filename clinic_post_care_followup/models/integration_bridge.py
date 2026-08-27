from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicStaff(models.Model):
    """Activate the historical clinic_staff post-care workload contract."""

    _inherit = "clinic.staff"

    postcare_task_ids = fields.One2many(
        "clinic.postcare.task",
        "assignee_id",
        string="Assigned Post-Care Tasks",
    )

    # Preserve clinic_staff shared counters, then replace only the historical Post-Care placeholder value.
    def _compute_counts(self):
        super()._compute_counts()
        Task = self.env["clinic.postcare.task"].sudo()
        for record in self:
            record.postcare_task_count = Task.search_count([
                ("assignee_id", "=", record.id),
                ("state", "not in", ("completed", "cancelled")),
            ])

    def action_open_postcare_tasks(self):
        """Preserve the pre-existing clinic_staff action contract, with better defaults."""
        self.ensure_one()
        return {
            "name": _("Post-Care Tasks"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.postcare.task",
            "view_mode": "kanban,list,form",
            "domain": [("assignee_id", "=", self.id)],
            "context": {
                "default_assignee_id": self.id,
                "search_default_open_tasks": 1,
            },
        }


class ClinicPatient(models.Model):
    """Patient navigation into the post-treatment follow-up episode."""

    _inherit = "clinic.patient"

    postcare_plan_ids = fields.One2many(
        "clinic.postcare.plan",
        "patient_id",
        string="Post-Care Plans",
    )
    postcare_plan_count = fields.Integer(compute="_compute_postcare_counts")
    postcare_open_plan_count = fields.Integer(compute="_compute_postcare_counts")
    postcare_open_escalation_count = fields.Integer(compute="_compute_postcare_counts")

    # Patient counters are navigation metrics; owned Plan/Escalation records remain authoritative.
    def _compute_postcare_counts(self):
        Escalation = self.env["clinic.postcare.escalation"]
        for record in self:
            record.postcare_plan_count = len(record.postcare_plan_ids)
            record.postcare_open_plan_count = len(
                record.postcare_plan_ids.filtered(
                    lambda plan: plan.state in ("draft", "active", "escalated")
                )
            )
            record.postcare_open_escalation_count = Escalation.search_count([
                ("patient_id", "=", record.id),
                ("state", "not in", ("resolved", "cancelled")),
            ])

    def action_open_postcare_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Post-Care Plans"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }


class ClinicEncounter(models.Model):
    """Create Post-Care from a completed clinical Encounter without replacing Encounter workflow."""

    _inherit = "clinic.encounter"

    postcare_plan_ids = fields.One2many(
        "clinic.postcare.plan",
        "encounter_id",
        string="Post-Care Plans",
    )
    postcare_plan_count = fields.Integer(compute="_compute_postcare_plan_count")
    postcare_open_escalation_count = fields.Integer(compute="_compute_postcare_plan_count")

    def _compute_postcare_plan_count(self):
        for record in self:
            record.postcare_plan_count = len(record.postcare_plan_ids)
            record.postcare_open_escalation_count = sum(
                record.postcare_plan_ids.mapped("open_escalation_count")
            )

    def _postcare_staff_from_doctor(self):
        self.ensure_one()
        if self.doctor_id and self.doctor_id.partner_id:
            return self.env["clinic.staff"].search([
                ("partner_id", "=", self.doctor_id.partner_id.id),
                ("company_id", "=", self.company_id.id),
                ("is_active", "=", True),
            ], limit=1)
        return self.env["clinic.staff"]

    # Encounter protocol matching uses existing Treatment/Procedure catalogs rather than duplicate masters.
    def _resolve_postcare_protocol(self):
        self.ensure_one()
        treatment_catalog = (
            self.treatment_id.catalog_id
            if self.treatment_id and self.treatment_id.catalog_id
            else False
        )
        procedures = self.procedure_line_ids.mapped("procedure_id")
        return self.env["clinic.postcare.protocol"].resolve_protocol(
            self.company_id,
            treatment_catalog=treatment_catalog,
            procedure_catalogs=procedures,
        )

    # Idempotent Encounter helper guarantees at most one non-cancelled plan from repeated automation attempts.
    def _ensure_postcare_plan(self, activate=False):
        self.ensure_one()
        existing = self.postcare_plan_ids.filtered(
            lambda plan: plan.state != "cancelled"
        )[:1]
        if existing:
            return existing

        protocol = self._resolve_postcare_protocol()
        if not protocol:
            raise UserError(_(
                "No Active Post-Care Protocol matches this Encounter. "
                "Configure a treatment/procedure-specific or generic Protocol first."
            ))

        branch = (
            self.branch_id
            if "branch_id" in self._fields and self.branch_id
            else self.env.user.working_branch_id
            if "working_branch_id" in self.env.user._fields
            else False
        )
        staff = (
            protocol.default_assignee_id
            or self._postcare_staff_from_doctor()
            or self.company_id.clinic_postcare_default_assignee_id
        )
        start_dt = self.date_end or fields.Datetime.now()

        plan = self.env["clinic.postcare.plan"].create({
            "patient_id": self.patient_id.id,
            "company_id": self.company_id.id,
            "branch_id": branch.id or False,
            "doctor_id": self.doctor_id.id or False,
            "responsible_staff_id": staff.id or False,
            "protocol_id": protocol.id,
            "source_type": "encounter",
            "encounter_id": self.id,
            "treatment_id": self.treatment_id.id or False,
            "start_datetime": start_dt,
        })
        if activate:
            plan.action_activate()
        return plan

    # Manual creation remains available even when company auto-creation is intentionally disabled.
    def action_create_postcare_plan(self):
        self.ensure_one()
        if self.state != "done":
            raise UserError(_("Post-Care Plan can be generated after the Encounter is Done."))
        plan = self._ensure_postcare_plan(activate=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plan"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "form",
            "res_id": plan.id,
        }

    def action_open_postcare_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plans"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "list,form",
            "domain": [("encounter_id", "=", self.id)],
        }


class BookingBooking(models.Model):
    """Allow a completed Booking to start post-care when no Encounter is used."""

    _inherit = "booking.booking"

    postcare_plan_ids = fields.One2many(
        "clinic.postcare.plan",
        "booking_id",
        string="Post-Care Plans",
    )
    postcare_plan_count = fields.Integer(compute="_compute_postcare_plan_count")

    def _compute_postcare_plan_count(self):
        for record in self:
            record.postcare_plan_count = len(record.postcare_plan_ids)

    def _postcare_patient_card(self):
        self.ensure_one()
        patient = self.env["clinic.patient"].search([
            ("partner_id", "=", self.patient_id.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not patient:
            raise UserError(_("The Booking contact has no Clinic Patient Card in this company."))
        return patient

    def action_create_postcare_plan(self):
        self.ensure_one()
        if self.state != "done":
            raise UserError(_("Post-Care Plan can be generated after the Booking is Done."))

        existing = self.postcare_plan_ids.filtered(lambda plan: plan.state != "cancelled")[:1]
        if existing:
            plan = existing
        else:
            patient = self._postcare_patient_card()
            treatment_catalog = (
                self.treatment_id.catalog_id
                if self.treatment_id and self.treatment_id.catalog_id
                else False
            )
            protocol = self.env["clinic.postcare.protocol"].resolve_protocol(
                self.company_id,
                treatment_catalog=treatment_catalog,
            )
            if not protocol:
                raise UserError(_("No Active Post-Care Protocol matches this Booking."))

            branch = (
                self.branch_id
                if "branch_id" in self._fields and self.branch_id
                else self.env.user.working_branch_id
                if "working_branch_id" in self.env.user._fields
                else False
            )
            plan = self.env["clinic.postcare.plan"].create({
                "patient_id": patient.id,
                "company_id": self.company_id.id,
                "branch_id": branch.id or False,
                "protocol_id": protocol.id,
                "source_type": "booking",
                "booking_id": self.id,
                "treatment_id": self.treatment_id.id or False,
                "start_datetime": self.end_datetime or fields.Datetime.now(),
            })

        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plan"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "form",
            "res_id": plan.id,
        }

    def action_open_postcare_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plans"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "list,form",
            "domain": [("booking_id", "=", self.id)],
        }


class CarePlan(models.Model):
    """Connect the longitudinal Care Plan with post-treatment instructions/follow-up."""

    _inherit = "clinic.care.plan"

    postcare_plan_ids = fields.One2many(
        "clinic.postcare.plan",
        "care_plan_id",
        string="Post-Care Plans",
    )
    postcare_plan_count = fields.Integer(compute="_compute_postcare_plan_count")

    def _compute_postcare_plan_count(self):
        for record in self:
            record.postcare_plan_count = len(record.postcare_plan_ids)

    def action_create_postcare_plan(self):
        self.ensure_one()
        existing = self.postcare_plan_ids.filtered(lambda plan: plan.state != "cancelled")[:1]
        if existing:
            plan = existing
        else:
            protocol = self.env["clinic.postcare.protocol"].resolve_protocol(
                self.company_id,
                care_protocol=self.protocol_template_id,
            )
            if not protocol:
                raise UserError(_("No Active Post-Care Protocol matches this Care Plan."))

            branch = (
                self.branch_id
                if "branch_id" in self._fields and self.branch_id
                else self.env.user.working_branch_id
                if "working_branch_id" in self.env.user._fields
                else False
            )
            staff = protocol.default_assignee_id or self.company_id.clinic_postcare_default_assignee_id

            plan = self.env["clinic.postcare.plan"].create({
                "patient_id": self.patient_id.id,
                "company_id": self.company_id.id,
                "branch_id": branch.id or False,
                "doctor_id": self.doctor_id.id or False,
                "responsible_staff_id": staff.id or False,
                "protocol_id": protocol.id,
                "source_type": "care_plan",
                "care_plan_id": self.id,
                "encounter_id": self.encounter_id.id or False,
                "booking_id": self.booking_id.id or False,
                "start_datetime": fields.Datetime.now(),
            })
            if self.instruction_note and not plan.instruction_html:
                plan.instruction_html = self.instruction_note

        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plan"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "form",
            "res_id": plan.id,
        }


class ClinicTreatment(models.Model):
    """Provide Treatment-level post-care traceability without taking Treatment ownership."""

    _inherit = "clinic.treatment"

    postcare_plan_ids = fields.One2many(
        "clinic.postcare.plan",
        "treatment_id",
        string="Post-Care Plans",
    )
    postcare_plan_count = fields.Integer(compute="_compute_postcare_plan_count")

    def _compute_postcare_plan_count(self):
        for record in self:
            record.postcare_plan_count = len(record.postcare_plan_ids)

    def action_open_postcare_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Post-Care Plans"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "list,form",
            "domain": [("treatment_id", "=", self.id)],
        }


class ClinicPostcarePlanAutomation(models.Model):
    """Automation helpers live on the owned Plan model, not inside Encounter workflow."""

    _inherit = "clinic.postcare.plan"

    @api.model
    # Automation is opt-in and lookback-bounded to avoid unexpectedly backfilling historical encounters.
    def _cron_auto_create_from_completed_encounters(self):
        companies = self.env["res.company"].sudo().search([
            ("clinic_postcare_auto_create_from_encounter", "=", True),
        ])
        now = fields.Datetime.now()

        for company in companies:
            lookback_days = max(company.clinic_postcare_auto_create_lookback_days or 2, 1)
            threshold = now - timedelta(days=lookback_days)
            encounters = self.env["clinic.encounter"].sudo().search([
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("date_end", "!=", False),
                ("date_end", ">=", threshold),
            ])

            for encounter in encounters:
                if encounter.postcare_plan_ids.filtered(lambda plan: plan.state != "cancelled"):
                    continue
                try:
                    plan = encounter._ensure_postcare_plan(activate=True)
                    plan.message_post(body=_("Post-Care Plan created automatically from completed Encounter."))
                except UserError as exc:
                    encounter.message_post(
                        body=_("Automatic Post-Care creation skipped: %s") % str(exc)
                    )
