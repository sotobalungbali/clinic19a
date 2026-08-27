
# -*- coding: utf-8 -*-
# File   : models/care_protocol_step.py
# Addon  : clinic_care_plan (Odoo 19 CE)
# Model  : clinic.care.protocol.step — Atomic protocol step (authored inside a protocol)
#
# All labels, help texts, and user-facing messages are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CareProtocolStep(models.Model):
    _name = "clinic.care.protocol.step"
    _description = "Care Protocol Step"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "protocol_id, sequence, id"

    # --------------------------------------------------------------------------------------
    # Master / Ownership
    # --------------------------------------------------------------------------------------
    protocol_id = fields.Many2one(
        "clinic.care.protocol",
        string="Protocol",
        help="Parent protocol template that owns this step.",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        help="Owning company (inherits from protocol).",
        related="protocol_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    sequence = fields.Integer(
        string="Sequence",
        help="Order of execution inside the protocol.",
        default=10,
        index=True,
    )

    name = fields.Char(
        string="Step Title",
        help="Short, operator-friendly title (e.g., 'Cleansing & Prep', 'Laser Pass 1', 'Topical Retinoid').",
        required=True,
        tracking=True,
    )

    description = fields.Text(
        string="Short Description",
        help="Short description or operator note for this protocol step.",
    )

    # --------------------------------------------------------------------------------------
    # Clinical Content
    # --------------------------------------------------------------------------------------
    instruction = fields.Text(
        string="Instructions",
        help="Plain-text instructions for this step.",
    )

    instruction_html = fields.Html(
        string="Instructions (HTML)",
        help="Rich-text instructions, technique notes, and warnings for this step.",
        sanitize=True,
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Treatment/procedure type associated with this step, if applicable.",
        ondelete="set null",
        index=True,
    )

    risk_level = fields.Selection(
        [("low", "Low"), ("moderate", "Moderate"), ("high", "High")],
        string="Risk Level",
        help="Clinical risk level of this step; may affect consent and monitoring.",
        default="low",
        tracking=True,
        index=True,
    )

    require_consent = fields.Boolean(
        string="Requires Consent",
        help="If enabled, consent is required before this step can be executed in a care plan.",
        default=False,
        tracking=True,
    )

    # --------------------------------------------------------------------------------------
    # Products / Consumables
    # --------------------------------------------------------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Retail/consumable/service product associated with this step (optional).",
        ondelete="set null",
        index=True,
    )

    is_product = fields.Boolean(
        string="Is Product/Consumable",
        help="True if this step consumes or sells a product.",
        compute="_compute_is_product",
        store=True,
    )

    qty = fields.Float(
        string="Quantity",
        help="Default quantity to be used when generating plan lines.",
        default=1.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        help="Unit of Measure for product quantity.",
        ondelete="set null",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        help="Currency for cost estimation.",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    estimated_subtotal = fields.Monetary(
        string="Estimated Subtotal",
        help="Heuristic estimation: qty × product list price (for this step).",
        currency_field="currency_id",
        compute="_compute_estimated_subtotal",
        store=True,
        readonly=True,
    )

    # --------------------------------------------------------------------------------------
    # Time & Scheduling Hints
    # --------------------------------------------------------------------------------------
    duration_minutes = fields.Integer(
        string="Estimated Duration (min)",
        help="Estimated duration to execute this step.",
        default=0,
    )

    expected_day_offset = fields.Integer(
        string="Expected Day Offset",
        help="Days after protocol start when this step is expected to occur (0 = same day).",
        default=0,
        index=True,
    )

    recommended_min_interval_days = fields.Integer(
        string="Recommended Min Interval (days)",
        help="Recommended minimum interval to next dependent step (for authoring guidance).",
        default=0,
    )

    # --------------------------------------------------------------------------------------
    # Dependencies (DAG-like within a protocol)
    # --------------------------------------------------------------------------------------
    dependency_step_ids = fields.Many2many(
        "clinic.care.protocol.step",
        "clinic_care_protocol_step_dep_rel",
        "step_id",
        "depends_on_step_id",
        string="Dependencies",
        help="This step should be performed after all dependency steps.",
        domain="[('protocol_id', '=', protocol_id)]",
    )

    dependents_count = fields.Integer(
        string="Dependent Steps",
        compute="_compute_dependents_count",
        store=False,
    )

    # --------------------------------------------------------------------------------------
    # Attachments & Flags
    # --------------------------------------------------------------------------------------
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_care_protocol_step_attach_rel",
        "step_id",
        "attachment_id",
        string="Attachments",
        help="Supporting documents, technique sheets, references, or photos.",
    )

    active = fields.Boolean(default=True, tracking=True)

    # --------------------------------------------------------------------------------------
    # COMPUTES
    # --------------------------------------------------------------------------------------
    @api.depends("product_id")
    def _compute_is_product(self):
        for rec in self:
            rec.is_product = bool(rec.product_id)

    @api.depends("product_id", "product_id.list_price", "qty")
    def _compute_estimated_subtotal(self):
        for rec in self:
            if rec.product_id and rec.qty:
                rec.estimated_subtotal = (rec.product_id.list_price or 0.0) * rec.qty
            else:
                rec.estimated_subtotal = 0.0

    def _compute_dependents_count(self):
        for rec in self:
            count = self.env["clinic.care.protocol.step"].search_count(
                [("dependency_step_ids", "in", rec.id), ("protocol_id", "=", rec.protocol_id.id)]
            )
            rec.dependents_count = count

    # --------------------------------------------------------------------------------------
    # ONCHANGE
    # --------------------------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            # Suggest UoM from product
            self.uom_id = self.product_id.uom_id.id
            # Suggest title from product if empty
            if not self.name:
                self.name = self.product_id.display_name

    # --------------------------------------------------------------------------------------
    # CONSTRAINTS
    # --------------------------------------------------------------------------------------
    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id:
                if rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                    raise ValidationError(_("Selected UoM is not compatible with the product's UoM category."))

    @api.constrains("is_product", "product_id", "qty")
    def _check_product_requirements(self):
        for rec in self:
            if rec.is_product:
                if not rec.product_id:
                    raise ValidationError(_("Product is required when 'Is Product/Consumable' is enabled."))
                if (rec.qty or 0.0) <= 0.0:
                    raise ValidationError(_("Quantity must be greater than zero for product steps."))

    @api.constrains("dependency_step_ids", "protocol_id")
    def _check_dependency_cycles(self):
        """Prevent cycles in dependencies (within the same protocol)."""
        def _visit(node, visited, stack):
            visited.add(node.id)
            stack.add(node.id)
            for nxt in node.dependency_step_ids:
                # Only consider steps within the same protocol
                if nxt.protocol_id.id != node.protocol_id.id:
                    continue
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
                raise ValidationError(_("Circular dependency detected between protocol steps."))

    # --------------------------------------------------------------------------------------
    # HELPERS / ACTIONS
    # --------------------------------------------------------------------------------------
    def action_view_protocol(self):
        """Open parent protocol form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Protocol"),
            "res_model": "clinic.care.protocol",
            "view_mode": "form",
            "res_id": self.protocol_id.id,
            "target": "current",
        }

    def action_view_dependents(self):
        """Open list of steps that depend on this step."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dependent Steps"),
            "res_model": "clinic.care.protocol.step",
            "view_mode": "list,form",
            "domain": [("dependency_step_ids", "in", self.id), ("protocol_id", "=", self.protocol_id.id)],
            "target": "current",
        }

    # --------------------------------------------------------------------------------------
    # RECORD LABEL
    # --------------------------------------------------------------------------------------
    @api.depends("sequence", "name")
    def _compute_display_name(self):
        """Preserve the historic ``[sequence] title`` label in Odoo 19."""
        for rec in self:
            rec.display_name = "[%s] %s" % (
                rec.sequence or 0,
                rec.name or _("Step"),
            )

    def name_get(self):
        result = []
        for rec in self:
            label = "[%s] %s" % (rec.sequence or 0, rec.name or _("Step"))
            result.append((rec.id, label))
        return result

    # --------------------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # --------------------------------------------------------------------------------------
    # Preserve the baseline SQL semantics exactly. ``id`` is intentionally
    # retained because changing it would tighten business behavior for existing
    # protocols whose authoring sequence values may repeat.
    _protocol_sequence_unique = models.Constraint(
        "unique(protocol_id, sequence, id)",
        "Sequence must be unique within a protocol.",
    )
