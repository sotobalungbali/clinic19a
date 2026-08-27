
# -*- coding: utf-8 -*-
# File   : models/care_plan_line.py
# Addon  : clinic_care_plan (Odoo 19 CE)
# Model  : clinic.care.plan.line — Atomic executable item under a Care Plan
#
# All labels, help texts, and user-facing messages are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class CarePlanLine(models.Model):
    _name = "clinic.care.plan.line"
    _description = "Care Plan Line"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "plan_id, sequence, id"

    # --------------------------------------------------------------------------------------
    # Master / Hierarchy
    # --------------------------------------------------------------------------------------
    plan_id = fields.Many2one(
        "clinic.care.plan",
        string="Care Plan",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent Care Plan that owns this line.",
        tracking=True,
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of execution within the plan.",
        index=True,
    )

    name = fields.Char(
        string="Line Title",
        required=True,
        help="Short title of the plan line (e.g., 'Laser Session #1', 'Topical Retinoid').",
        tracking=True,
    )

    description = fields.Text(
        string="Description",
        help="Short description or operator note for this line.",
    )

    instruction_html = fields.Html(
        string="Instructions (HTML)",
        help="Operator-facing instructions, technique notes, warnings, etc.",
        sanitize=True,
    )

    # Useful relateds (denormalized for performance & quick filters)
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="plan_id.patient_id",
        store=True,
        index=True,
        readonly=True,
    )

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Responsible Doctor",
        related="plan_id.doctor_id",
        store=True,
        index=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="plan_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    # --------------------------------------------------------------------------------------
    # Execution Lifecycle
    # --------------------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("skipped", "Skipped"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        required=True,
        tracking=True,
        index=True,
        help="Execution status for this plan line.",
    )

    performer_id = fields.Many2one(
        "clinic.practitioner",
        string="Assigned Performer",
        help="Practitioner assigned to execute this line.",
        ondelete="set null",
        index=True,
        tracking=True,
    )

    start_datetime = fields.Datetime(
        string="Start",
        help="Actual start datetime (when execution starts).",
        tracking=True,
    )

    end_datetime = fields.Datetime(
        string="End",
        help="Actual end datetime (when execution ends).",
        tracking=True,
    )

    duration_minutes = fields.Integer(
        string="Estimated Duration (min)",
        help="Estimated duration for executing this line.",
        default=0,
    )

    actual_duration_minutes = fields.Integer(
        string="Actual Duration (min)",
        help="Actual duration spent; filled upon completion.",
        compute="_compute_actual_duration",
        store=True,
        readonly=True,
    )

    # --------------------------------------------------------------------------------------
    # Scheduling (relative to plan)
    # --------------------------------------------------------------------------------------
    expected_day_offset = fields.Integer(
        string="Expected Day Offset",
        help="Days after plan start when this line is intended to be executed (0 = same day).",
        default=0,
    )

    expected_date = fields.Date(
        string="Expected Date",
        help="Computed expected date = plan.start_date + expected_day_offset.",
        compute="_compute_expected_date",
        store=True,
    )

    scheduled_datetime = fields.Datetime(
        string="Scheduled Datetime",
        help="Datetime scheduled for this line execution.",
        tracking=True,
    )

    booking_id = fields.Many2one(
        "booking.booking",
        string="Linked Booking",
        help="Booking/appointment used to schedule this line.",
        ondelete="set null",
        index=True,
    )

    # --------------------------------------------------------------------------------------
    # Clinical Content / Products
    # --------------------------------------------------------------------------------------
    is_product = fields.Boolean(
        string="Is Product/Consumable",
        help="If checked, this line consumes or sells a product (retail or consumable).",
        default=False,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Product involved in this line (retail/consumable/service).",
        ondelete="set null",
        index=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        help="Unit of Measure for the product quantity.",
        ondelete="set null",
    )

    qty = fields.Float(
        string="Quantity",
        help="Required quantity of the product for this line.",
        default=1.0,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )

    price_unit = fields.Monetary(
        string="Unit Price",
        help="Estimated unit price for cost/amount estimation.",
        currency_field="currency_id",
        default=0.0,
    )

    amount_estimated = fields.Monetary(
        string="Estimated Subtotal",
        help="Estimated subtotal: qty × unit price.",
        currency_field="currency_id",
        compute="_compute_amount_estimated",
        store=True,
    )

    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_care_plan_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Applicable taxes if this line is billed individually.",
    )

    # Links to accounting (when invoiced at line level; optional pattern)
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_care_plan_line_aml_rel",
        "line_id",
        "line_move_id",
        string="Invoice Lines",
        help="Invoice lines originating from/linked to this care plan line.",
        readonly=True,
    )

    # --------------------------------------------------------------------------------------
    # Cross-Module Anchors
    # --------------------------------------------------------------------------------------
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Treatment/procedure type represented by this line.",
        ondelete="set null",
        index=True,
    )

    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        help="Linked procedure session created/scheduled for this line.",
        ondelete="set null",
        index=True,
    )

    prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="Prescription",
        help="Medication/device order generated for this line (eMAR).",
        ondelete="set null",
        index=True,
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_care_plan_line_attachment_rel",
        "line_id",
        "attachment_id",
        string="Attachments",
        help="Photos or documents supporting this line.",
    )

    # Dependencies between lines (simple DAG-like)
    dependency_ids = fields.Many2many(
        "clinic.care.plan.line",
        "clinic_care_plan_line_dep_rel",
        "line_id",
        "dependency_id",
        string="Dependencies",
        help="This line can only be executed after all dependencies are Done or Skipped.",
    )

    dependents_count = fields.Integer(
        string="Dependent Lines",
        compute="_compute_dependents_count",
        store=False,
    )

    # --------------------------------------------------------------------------------------
    # COMPUTES
    # --------------------------------------------------------------------------------------
    @api.depends("start_datetime", "end_datetime")
    def _compute_actual_duration(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                start = fields.Datetime.from_string(rec.start_datetime)
                end = fields.Datetime.from_string(rec.end_datetime)
                mins = int((end - start).total_seconds() // 60)
                rec.actual_duration_minutes = max(mins, 0)
            else:
                rec.actual_duration_minutes = 0

    @api.depends("qty", "price_unit")
    def _compute_amount_estimated(self):
        for rec in self:
            q = rec.qty or 0.0
            pu = rec.price_unit or 0.0
            rec.amount_estimated = q * pu

    @api.depends("plan_id.start_date", "expected_day_offset")
    def _compute_expected_date(self):
        for rec in self:
            if rec.plan_id and rec.plan_id.start_date is not None:
                base = fields.Date.from_string(rec.plan_id.start_date)
                rec.expected_date = base + timedelta(days=(rec.expected_day_offset or 0))
            else:
                rec.expected_date = False

    def _compute_dependents_count(self):
        # Reverse search can be expensive; keep it on-demand (no store).
        for rec in self:
            count = self.env["clinic.care.plan.line"].search_count([("dependency_ids", "in", rec.id)])
            rec.dependents_count = count

    # --------------------------------------------------------------------------------------
    # ONCHANGE & DEFAULTS
    # --------------------------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            # Default UoM and price from product
            self.uom_id = self.product_id.uom_id.id
            # Use Sales price for estimation; adjust to cost if needed
            self.price_unit = self.product_id.list_price or 0.0
            # Suggest line title from product
            if not self.name:
                self.name = self.product_id.display_name

    # --------------------------------------------------------------------------------------
    # CONSTRAINTS
    # --------------------------------------------------------------------------------------
    @api.constrains("is_product", "product_id", "qty", "uom_id")
    def _check_product_requirements(self):
        for rec in self:
            if rec.is_product:
                if not rec.product_id:
                    raise ValidationError(_("Product is required when 'Is Product/Consumable' is enabled."))
                if (rec.qty or 0.0) <= 0.0:
                    raise ValidationError(_("Quantity must be greater than zero for product lines."))
                if not rec.uom_id:
                    raise ValidationError(_("Unit of Measure is required for product lines."))
                # Validate UoM category compatibility
                if rec.product_id.uom_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                    raise ValidationError(_("Selected UoM is not compatible with the product's UoM category."))

    @api.constrains("dependency_ids")
    def _check_dependency_cycles(self):
        """Prevent simple circular dependencies (self → ... → self)."""
        def _visit(node, visited, stack):
            visited.add(node.id)
            stack.add(node.id)
            for nxt in node.dependency_ids:
                if nxt.id not in visited:
                    if _visit(nxt, visited, stack):
                        return True
                elif nxt.id in stack:
                    return True
            stack.remove(node.id)
            return False

        for rec in self:
            visited, stack = set(), set()
            if _visit(rec, visited, stack):
                raise ValidationError(_("Circular dependency detected in care plan lines."))

    @api.constrains("state")
    def _check_dependency_status(self):
        for rec in self:
            if rec.state in ("scheduled", "in_progress", "done"):
                # All dependencies must be done or skipped
                blockers = rec.dependency_ids.filtered(lambda l: l.state not in ("done", "skipped"))
                if blockers:
                    raise ValidationError(_("This line cannot proceed until all dependencies are Done or Skipped."))

    # --------------------------------------------------------------------------------------
    # CRUD OVERRIDES
    # --------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Auto-subscribe performer & doctor for chatter visibility
            partner_ids = []
            if rec.performer_id and rec.performer_id.partner_id:
                partner_ids.append(rec.performer_id.partner_id.id)
            if rec.doctor_id and rec.doctor_id.partner_id:
                partner_ids.append(rec.doctor_id.partner_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        res = super().write(vals)
        tracked = ("state", "performer_id", "scheduled_datetime", "booking_id")
        if any(k in tracked for k in vals.keys()):
            for rec in self:
                rec.message_post(
                    body=_("Care Plan Line updated (key fields changed)."),
                    subtype_xmlid="mail.mt_note",
                )
        return res

    # --------------------------------------------------------------------------------------
    # ACTIONS — State Machine
    # --------------------------------------------------------------------------------------
    def action_mark_scheduled(self):
        for rec in self:
            if not rec.scheduled_datetime:
                raise UserError(_("Please set a Scheduled Datetime before marking as Scheduled."))
            rec.state = "scheduled"
            rec.message_post(body=_("Line marked as Scheduled."), subtype_xmlid="mail.mt_note")

    def action_start(self):
        for rec in self:
            if rec.state not in ("scheduled", "pending"):
                raise UserError(_("Only Pending or Scheduled lines can be started."))
            if not rec.start_datetime:
                rec.start_datetime = fields.Datetime.now()
            rec.state = "in_progress"
            rec.message_post(body=_("Line execution started."), subtype_xmlid="mail.mt_note")

    def action_done(self):
        for rec in self:
            if rec.state not in ("in_progress", "scheduled"):
                # Allow directly from scheduled (quick executions)
                raise UserError(_("Only In Progress or Scheduled lines can be marked Done."))
            if not rec.end_datetime:
                rec.end_datetime = fields.Datetime.now()
            if rec.start_datetime and rec.end_datetime and rec.end_datetime < rec.start_datetime:
                raise UserError(_("End time cannot be earlier than start time."))
            rec.state = "done"
            rec.message_post(body=_("Line completed."), subtype_xmlid="mail.mt_note")

    def action_skip(self, reason=None):
        for rec in self:
            rec.state = "skipped"
            rec.message_post(
                body=_("Line skipped. Reason: %s") % (reason or _("No reason provided")),
                subtype_xmlid="mail.mt_note",
            )

    def action_cancel(self, reason=None):
        for rec in self:
            rec.state = "cancelled"
            rec.message_post(
                body=_("Line cancelled. Reason: %s") % (reason or _("No reason provided")),
                subtype_xmlid="mail.mt_note",
            )

    # --------------------------------------------------------------------------------------
    # ACTIONS — Cross-Module Bridges (safe defaults via context)
    # --------------------------------------------------------------------------------------
    def action_open_or_create_session(self):
        """Open Procedure Session form with defaults from this line.
        We avoid direct creation to remain compatible with session model variations across modules.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Procedure Session"),
            "res_model": "clinic.procedure.session",
            "view_mode": "form",
            "res_id": self.session_id.id if self.session_id else False,
            "target": "current",
            "context": {
                "default_care_plan_id": self.plan_id.id,
                "default_care_plan_line_id": self.id,
                "default_treatment_id": self.treatment_id.id if self.treatment_id else False,
                "default_performer_doctor_id": self.doctor_id.id if self.doctor_id else False,
                "default_planned_start": self.scheduled_datetime or False,
                "default_planned_duration": self.duration_minutes or 0,
                "default_internal_note": self.description or "",
            },
        }

    def action_open_or_create_prescription(self):
        """Open Prescription (eMAR) form with defaults from this line."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Prescription"),
            "res_model": "clinic.emar.prescription",
            "view_mode": "form",
            "res_id": self.prescription_id.id if self.prescription_id else False,
            "target": "current",
            "context": {
                "default_care_plan_id": self.plan_id.id,
                "default_care_plan_line_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_doctor_id": self.doctor_id.id if self.doctor_id else False,
                "default_notes": self.description or "",
            },
        }

    def action_request_inventory(self):
        """Create a reminder activity for inventory consumption/issue related to this line."""
        for rec in self:
            if not rec.is_product or not rec.product_id or rec.qty <= 0:
                raise UserError(_("This action requires a valid product and quantity."))
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=False,
                note=_("Issue/consume inventory for product: %(p)s (qty: %(q)s %(u)s) in Care Plan %(cp)s.",
                       p=rec.product_id.display_name,
                       q=rec.qty,
                       u=rec.uom_id.display_name if rec.uom_id else "",
                       cp=rec.plan_id.name),
            )
            rec.message_post(body=_("Inventory request scheduled."), subtype_xmlid="mail.mt_note")

    def action_open_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("line_ids", "in", self.invoice_line_ids.ids)],
            "target": "current",
        }

    # --------------------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------------------
    def action_open_plan(self):
        """Open the parent care plan from a standalone or embedded line."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plan"),
            "res_model": "clinic.care.plan",
            "view_mode": "form",
            "res_id": self.plan_id.id,
            "target": "current",
        }

    def action_view_dependents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dependent Lines"),
            "res_model": "clinic.care.plan.line",
            "view_mode": "list,form",
            "domain": [("dependency_ids", "in", self.id)],
            "target": "current",
            "context": {"search_default_group_plan": 1},
        }

    # --------------------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # --------------------------------------------------------------------------------------
    _plan_sequence_unique = models.Constraint(
        "unique(plan_id, sequence, id)",
        "Sequence must be unique within a care plan.",
    )
