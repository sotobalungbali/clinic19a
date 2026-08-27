
# -*- coding: utf-8 -*-
# File: models/care_plan.py
# Addon: clinic_care_plan (Odoo 19 CE)
# Model: clinic.care.plan  —  Core entity for ClinicOne Care Plan & Protocol Library
#
# Notes:
# - All labels, help texts, and user messages are in English (per product requirement).
# - This model anchors integrations across multiple ClinicOne modules:
#   clinic_patient, clinic_doctor, clinic_booking, clinic_treatment, clinic_emar (prescriptions),
#   clinic_inventory (products/consumables), clinic_accounting/billing (invoices), clinic_triage_vitals, clinic_consent,
#   clinic_encounter, clinic_reports/dashboard, etc.
# - Sequence code expected: "clinic.care.plan" (declared in data/sequence_data.xml).
# - Views, actions, reports, and wizards are defined in the XML files within this module.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class CarePlan(models.Model):
    _name = "clinic.care.plan"
    _description = "Care Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "priority desc, start_date desc, id desc"

    # --------------------------------------------------------------------------------------------------
    # Identity & Basic
    # --------------------------------------------------------------------------------------------------
    name = fields.Char(
        string="Care Plan Number",
        help="Internal unique code generated from a sequence.",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("clinic.care.plan") or _("New"),
        index=True,
        tracking=True,
    )

    display_name = fields.Char(
        string="Title",
        help="Human-friendly title for the care plan (e.g., 'Acne Program – Q4').",
        required=True,
        tracking=True,
    )

    plan_type = fields.Selection(
        [
            ("acute", "Acute"),
            ("chronic", "Chronic"),
            ("preventive", "Preventive"),
            ("maintenance", "Maintenance"),
            ("post_op", "Post-Operative"),
            ("aesthetic", "Aesthetic Program"),
        ],
        string="Plan Type",
        help="General category of the care plan purpose.",
        required=True,
        default="aesthetic",
        tracking=True,
    )

    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Normal"),
            ("2", "High"),
            ("3", "Critical"),
        ],
        string="Priority",
        help="Operational priority of the care plan.",
        default="1",
        tracking=True,
        index=True,
    )

    # --------------------------------------------------------------------------------------------------
    # Company
    # --------------------------------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    # --------------------------------------------------------------------------------------------------
    # Parties & Ownership (Integration anchors across ClinicOne modules)
    # --------------------------------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        help="Patient who receives this care plan.",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Responsible Doctor",
        help="Primary clinician responsible for supervising and approving this plan.",
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    practitioner_ids = fields.Many2many(
        "clinic.practitioner",
        "clinic_care_plan_practitioner_rel",
        "plan_id",
        "practitioner_id",
        string="Assigned Practitioners",
        help="Therapists/Nurses assigned to execute steps within this plan.",
        tracking=True,
    )

    referrer_id = fields.Many2one(
        "res.partner",
        string="Referrer",
        help="Referring person or organization (if any).",
        ondelete="set null",
        index=True,
    )

    # --------------------------------------------------------------------------------------------------
    # Clinical Context (links to other modules)
    # --------------------------------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Origin Encounter",
        help="Clinical encounter that originates this care plan.",
        ondelete="set null",
        index=True,
    )

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent Record",
        help="Signed consent associated to this plan.",
        ondelete="set null",
        index=True,
    )

    triage_id = fields.Many2one(
        "clinic.vitals.intake",
        string="Latest Vitals Intake",
        help="Reference vitals/triage record used as baseline.",
        ondelete="set null",
        index=True,
    )

    booking_id = fields.Many2one(
        "booking.booking",
        string="Initial Booking",
        help="Booking that initiated this plan (if any).",
        ondelete="set null",
        index=True,
    )

    # membership_id = fields.Many2one(
    #     "clinic.membership",
    #     string="Membership",
    #     help="Membership program if the plan leverages member benefits or discounts.",
    #     ondelete="set null",
    #     index=True,
    # )

    diagnosis_summary = fields.Text(
        string="Diagnosis Summary",
        help="Free-text summary of the working diagnosis supporting this plan.",
    )

    # --------------------------------------------------------------------------------------------------
    # Timeframe & Lifecycle
    # --------------------------------------------------------------------------------------------------
    start_date = fields.Date(
        string="Start Date",
        help="Planned start date of this care plan.",
        required=True,
        tracking=True,
    )

    end_date = fields.Date(
        string="End Date",
        help="Planned end date of this care plan.",
        tracking=True,
    )

    duration_days = fields.Integer(
        string="Planned Duration (days)",
        help="Planned number of days (computed from Start/End dates).",
        compute="_compute_duration",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("on_hold", "On Hold"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    stage_note = fields.Text(
        string="Stage Notes",
        help="Notes related to the current lifecycle stage.",
        tracking=True,
    )

    # --------------------------------------------------------------------------------------------------
    # Protocol & Execution (relations to models in this module)
    # --------------------------------------------------------------------------------------------------
    protocol_template_id = fields.Many2one(
        "clinic.care.protocol",
        string="Protocol Template",
        help="Protocol template used to generate plan lines.",
        ondelete="set null",
        index=True,
    )

    line_ids = fields.One2many(
        "clinic.care.plan.line",
        "plan_id",
        string="Plan Lines",
        help="Detailed actions/steps derived from protocol or manual design.",
    )

    # Computed execution metrics
    step_count = fields.Integer(
        string="Step Count",
        help="Total number of steps within this care plan.",
        compute="_compute_counts",
        store=True,
    )

    step_completed_count = fields.Integer(
        string="Completed Steps",
        help="Number of steps marked as done.",
        compute="_compute_counts",
        store=True,
    )

    progress = fields.Float(
        string="Progress (%)",
        help="Percentage of completed steps.",
        compute="_compute_progress",
        store=True,
        aggregator="avg",
    )

    adherence_score = fields.Float(
        string="Adherence (%)",
        help="Patient adherence ratio (attendance/compliance) estimated by plan lines & sessions.",
        compute="_compute_adherence",
        store=True,
        aggregator="avg",
    )

    # --------------------------------------------------------------------------------------------------
    # Products / Treatments / Sessions / Prescriptions (cross-module anchors)
    # --------------------------------------------------------------------------------------------------
    treatment_ids = fields.Many2many(
        "clinic.treatment",
        "clinic_care_plan_treatment_rel",
        "plan_id",
        "treatment_id",
        string="Treatments",
        help="Treatments that are part of this care plan.",
    )

    procedure_session_ids = fields.One2many(
        "clinic.procedure.session",
        "care_plan_id",
        string="Procedure Sessions",
        help="Sessions scheduled/executed under this care plan.",
    )

    prescription_ids = fields.One2many(
        "clinic.emar.prescription",
        "care_plan_id",
        string="Prescriptions",
        help="Medication/device orders (eMAR) associated with this plan.",
    )

    product_line_count = fields.Integer(
        string="Product Items",
        help="Number of distinct product items required by the plan.",
        compute="_compute_counts",
        store=True,
    )

    session_count = fields.Integer(
        string="Procedure Sessions",
        compute="_compute_counts",
        store=True,
        help="Number of procedure sessions linked to this care plan.",
    )

    prescription_count = fields.Integer(
        string="Prescriptions",
        compute="_compute_counts",
        store=True,
        help="Number of eMAR prescriptions linked to this care plan.",
    )

    invoice_count = fields.Integer(
        string="Invoices",
        compute="_compute_counts",
        store=True,
        help="Number of invoices linked to this care plan.",
    )

    # --------------------------------------------------------------------------------------------------
    # Billing & Financial (integration anchors; documents managed in Billing/Accounting modules)
    # --------------------------------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )

    amount_estimated = fields.Monetary(
        string="Estimated Amount",
        help="Estimated total amount for the entire plan (sum of steps, products, procedures).",
        currency_field="currency_id",
        tracking=True,
    )

    invoice_ids = fields.Many2many(
        "account.move",
        "clinic_care_plan_invoice_rel",
        "plan_id",
        "move_id",
        string="Invoices",
        domain=[("move_type", "in", ("out_invoice", "out_refund"))],
        help="Customer invoices related to this care plan.",
        readonly=True,
    )

    amount_invoiced = fields.Monetary(
        string="Invoiced Amount",
        help="Sum of posted invoices linked to this care plan.",
        currency_field="currency_id",
        compute="_compute_financials",
        store=True,
        readonly=True,
    )

    amount_remaining = fields.Monetary(
        string="Remaining Amount",
        help="Estimated amount minus invoiced amount.",
        currency_field="currency_id",
        compute="_compute_financials",
        store=True,
        readonly=True,
    )

    # --------------------------------------------------------------------------------------------------
    # Compliance & Attachments
    # --------------------------------------------------------------------------------------------------
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_care_plan_attachment_rel",
        "plan_id",
        "attachment_id",
        string="Attachments",
        help="Supporting files (e.g., consent scans, protocol PDFs, imaging summaries).",
    )

    is_confidential = fields.Boolean(
        string="Confidential",
        help="If enabled, access to this plan may be restricted by additional record rules.",
        default=True,
        tracking=True,
    )

    # --------------------------------------------------------------------------------------------------
    # Notes & Communication
    # --------------------------------------------------------------------------------------------------
    instruction_note = fields.Html(
        string="Patient Instructions",
        help="Patient-facing instructions compiled from protocol steps.",
        sanitize=True,
    )

    internal_note = fields.Text(
        string="Internal Clinical Notes",
        help="Internal notes for clinicians and staff; not shown to patient.",
    )

    # --------------------------------------------------------------------------------------------------
    # Audit
    # --------------------------------------------------------------------------------------------------
    active = fields.Boolean(default=True, tracking=True)
    create_uid = fields.Many2one("res.users", string="Created by", readonly=True)
    write_uid = fields.Many2one("res.users", string="Last Updated by", readonly=True)
    create_date = fields.Datetime(string="Created on", readonly=True, index=True)
    write_date = fields.Datetime(string="Last Updated on", readonly=True, index=True)

    # --------------------------------------------------------------------------------------------------
    # COMPUTE METHODS
    # --------------------------------------------------------------------------------------------------
    @api.depends("start_date", "end_date")
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                start = fields.Date.from_string(rec.start_date)
                end = fields.Date.from_string(rec.end_date)
                rec.duration_days = (end - start).days + 1
            else:
                rec.duration_days = 0

    @api.depends(
        "line_ids.state",
        "line_ids.is_product",
        "line_ids.qty",
        "line_ids.product_id",
        "procedure_session_ids",
        "prescription_ids",
        "invoice_ids",
    )
    def _compute_counts(self):
        for rec in self:
            steps = len(rec.line_ids)
            done = len(rec.line_ids.filtered(lambda line: line.state == "done"))
            product_items = len(
                set(
                    rec.line_ids.filtered(
                        lambda line: line.is_product and line.product_id
                    ).mapped("product_id").ids
                )
            )
            rec.step_count = steps
            rec.step_completed_count = done
            rec.product_line_count = product_items
            rec.session_count = len(rec.procedure_session_ids)
            rec.prescription_count = len(rec.prescription_ids)
            rec.invoice_count = len(rec.invoice_ids)

    @api.depends("step_count", "step_completed_count")
    def _compute_progress(self):
        for rec in self:
            rec.progress = (rec.step_completed_count / rec.step_count) * 100.0 if rec.step_count else 0.0

    @api.depends("procedure_session_ids.state", "line_ids.state")
    def _compute_adherence(self):
        """Heuristic:
        - If there are sessions: adherence = completed sessions / total sessions
        - Else fallback to plan lines: adherence = completed lines / total lines
        """
        for rec in self:
            sessions = rec.procedure_session_ids
            if sessions:
                total = len(sessions)
                done = len(sessions.filtered(lambda s: s.state in ("done", "completed")))
                rec.adherence_score = (done / total) * 100.0 if total else 0.0
            else:
                total = rec.step_count
                done = rec.step_completed_count
                rec.adherence_score = (done / total) * 100.0 if total else 0.0

    @api.depends("invoice_ids.amount_total", "invoice_ids.state", "amount_estimated")
    def _compute_financials(self):
        for rec in self:
            posted = rec.invoice_ids.filtered(lambda m: m.state == "posted")
            invoiced = sum(posted.mapped("amount_total"))
            rec.amount_invoiced = invoiced
            rec.amount_remaining = max((rec.amount_estimated or 0.0) - invoiced, 0.0)

    # --------------------------------------------------------------------------------------------------
    # CONSTRAINTS & ONCHANGES
    # --------------------------------------------------------------------------------------------------
    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.end_date and rec.start_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End Date cannot be earlier than Start Date."))

    @api.constrains("patient_id", "doctor_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.patient_id and rec.patient_id.company_id and rec.patient_id.company_id != rec.company_id:
                raise ValidationError(_("Patient company must match the Care Plan company."))
            if rec.doctor_id and rec.doctor_id.company_id and rec.doctor_id.company_id != rec.company_id:
                raise ValidationError(_("Doctor company must match the Care Plan company."))

    @api.onchange("protocol_template_id")
    def _onchange_protocol_template_id(self):
        if self.protocol_template_id:
            self.stage_note = _(
                "Protocol template selected: %(protocol)s. You can generate plan lines from this template.",
                protocol=self.protocol_template_id.display_name or self.protocol_template_id.name,
            )

    # --------------------------------------------------------------------------------------------------
    # CRUD OVERRIDES
    # --------------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Auto-subscribe responsible doctor & practitioners
            partner_ids = []
            if rec.doctor_id and rec.doctor_id.partner_id:
                partner_ids.append(rec.doctor_id.partner_id.id)
            if rec.practitioner_ids:
                partner_ids += rec.practitioner_ids.mapped("partner_id").ids
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        res = super().write(vals)
        # Example: notify when critical changes happen
        tracked = ("state", "doctor_id", "protocol_template_id", "start_date", "end_date")
        if any(k in tracked for k in vals.keys()):
            for rec in self:
                rec.message_post(
                    body=_("Care Plan updated (key fields changed)."),
                    subtype_xmlid="mail.mt_note",
                )
        return res

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled", "archived"):
                raise UserError(_("Only Draft, Cancelled, or Archived plans can be deleted."))
        return super().unlink()

    # --------------------------------------------------------------------------------------------------
    # ACTIONS (State Machine)
    # --------------------------------------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if not rec.patient_id:
                raise UserError(_("A patient is required before activating the care plan."))
            if not rec.start_date:
                raise UserError(_("Start Date is required before activating the care plan."))
            # Optional validation: consent presence
            if rec.is_confidential and not rec.consent_id:
                # Policy-dependent: enforce consent for confidential plans
                raise UserError(_("A valid consent record is required for confidential care plans."))
            rec.state = "active"
            rec.message_post(body=_("Care Plan has been activated."), subtype_xmlid="mail.mt_note")
            # Schedule kick-off activity for practitioners
            if rec.practitioner_ids:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=False,
                    note=_("Kick-off tasks for assigned practitioners."),
                )

    def action_hold(self, reason=None):
        self.write({"state": "on_hold"})
        for rec in self:
            rec.message_post(
                body=_("Care Plan has been put On Hold. Reason: %s") % (reason or _("No reason provided")),
                subtype_xmlid="mail.mt_note",
            )

    def action_complete(self):
        for rec in self:
            if rec.step_count and rec.step_completed_count < rec.step_count:
                # Strict policy: require all steps done
                raise UserError(_("All steps must be completed before marking the plan as Completed."))
            rec.state = "completed"
            rec.message_post(body=_("Care Plan has been marked as Completed."), subtype_xmlid="mail.mt_note")

    def action_cancel(self, reason=None):
        for rec in self:
            rec.state = "cancelled"
            rec.message_post(
                body=_("Care Plan has been cancelled. Reason: %s") % (reason or _("No reason provided")),
                subtype_xmlid="mail.mt_note",
            )

    def action_archive(self):
        for rec in self:
            if rec.state not in ("completed", "cancelled"):
                raise UserError(_("Only Completed or Cancelled plans can be archived."))
            rec.state = "archived"
            rec.active = False
            rec.message_post(body=_("Care Plan archived."), subtype_xmlid="mail.mt_note")

    # --------------------------------------------------------------------------------------------------
    # PROTOCOL OPERATIONS (implemented when protocol & line models are ready)
    # --------------------------------------------------------------------------------------------------
    def action_generate_lines_from_protocol(self):
        """Generate care plan lines from the selected protocol template."""
        self.ensure_one()
        if not self.protocol_template_id:
            raise UserError(_("Please select a Protocol Template first."))

        # Policy: clear existing lines before generate (can be adjusted to append)
        if self.line_ids:
            self.line_ids.unlink()

        # Expecting: clinic.care.protocol has one2many step_ids to clinic.care.protocol.step
        steps = self.protocol_template_id.step_ids
        PlanLine = self.env["clinic.care.plan.line"]
        created = self.env["clinic.care.plan.line"]
        for step in steps.sorted(key=lambda s: (s.sequence, s.id)):
            vals = {
                "plan_id": self.id,
                "name": step.name or _("Protocol Step"),
                "description": step.instruction_html or step.instruction or "",
                "is_product": bool(step.product_id),
                "product_id": step.product_id.id if step.product_id else False,
                "qty": step.qty or 1.0,
                "uom_id": step.uom_id.id if step.uom_id else False,
                "duration_minutes": step.duration_minutes or 0,
                "expected_day_offset": step.expected_day_offset or 0,
                "state": "pending",
            }
            created |= PlanLine.create(vals)

        self.message_post(
            body=_("Plan lines generated from protocol template (%s).") % (self.protocol_template_id.display_name or self.protocol_template_id.name),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Plan Lines"),
            "res_model": "clinic.care.plan.line",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "target": "current",
        }

    # --------------------------------------------------------------------------------------------------
    # ACTION HELPERS (open related records)
    # --------------------------------------------------------------------------------------------------
    def action_open_lines(self):
        """Open the executable lines that belong to this care plan."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plan Lines"),
            "res_model": "clinic.care.plan.line",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
            "target": "current",
        }

    def action_print_summary(self):
        """Render the enterprise care-plan summary report."""
        self.ensure_one()
        report = self.env.ref(
            "clinic_care_plan.action_report_care_plan_summary",
            raise_if_not_found=False,
        )
        if not report:
            raise UserError(_("The Care Plan Summary report is not available."))
        return report.report_action(self)

    def action_open_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Procedure Sessions"),
            "res_model": "clinic.procedure.session",
            "view_mode": "list,form,calendar",
            "domain": [("care_plan_id", "=", self.id)],
            "target": "current",
        }

    def action_open_prescriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Prescriptions"),
            "res_model": "clinic.emar.prescription",
            "view_mode": "list,form",
            "domain": [("care_plan_id", "=", self.id)],
            "target": "current",
        }

    def action_open_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "target": "current",
        }

    # --------------------------------------------------------------------------------------------------
    # RECORD LABEL COMPATIBILITY
    # ``display_name`` is intentionally a stored business title in this model.
    # Keep the legacy helper callable for downstream custom code; Odoo 19 UI
    # labels are already provided by the stored ``display_name`` field.
    # --------------------------------------------------------------------------------------------------
    def name_get(self):
        result = []
        for rec in self:
            title = "[%s] %s" % (rec.name or _("New"), rec.display_name or "")
            if rec.patient_id:
                title = "%s - %s" % (title, rec.patient_id.display_name)
            result.append((rec.id, title))
        return result

    # --------------------------------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # --------------------------------------------------------------------------------------------------
    _name_unique = models.Constraint(
        "unique(name)",
        "Care Plan Number must be unique.",
    )
