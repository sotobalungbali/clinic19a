
# -*- coding: utf-8 -*-
# File   : models/care_protocol.py
# Addon  : clinic_care_plan (Odoo 19 CE)
# Models : clinic.care.protocol — Reusable protocol templates (authoring, versioning, publish lifecycle)
#
# All labels, help texts, and user-facing messages are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


class CareProtocol(models.Model):
    _name = "clinic.care.protocol"
    _description = "Care Protocol Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "version desc, create_date desc, id desc"

    # ------------------------------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------------------------------
    name = fields.Char(
        string="Protocol Code",
        help="Internal unique protocol code generated from a sequence.",
        required=True,
        copy=False,
        index=True,
        tracking=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("clinic.care.protocol") or _("New"),
    )

    display_name = fields.Char(
        string="Title",
        help="Human-friendly title for the protocol (e.g., 'Acne Program - Mild to Moderate').",
        required=True,
        tracking=True,
    )

    description = fields.Text(
        string="Short Description",
        help="A short summary describing this protocol and its intended clinical outcomes.",
    )

    # ------------------------------------------------------------------------------------------
    # Ownership & Company
    # ------------------------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    owner_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Clinical Owner",
        help="Primary clinical owner responsible for this protocol.",
        ondelete="set null",
        index=True,
        tracking=True,
    )

    reviewer_ids = fields.Many2many(
        "clinic.doctor",
        "clinic_care_protocol_reviewer_rel",
        "protocol_id",
        "doctor_id",
        string="Clinical Reviewers",
        help="Doctors who review and validate clinical content of this protocol.",
    )

    # ------------------------------------------------------------------------------------------
    # Versioning & Lifecycle
    # ------------------------------------------------------------------------------------------
    version = fields.Char(
        string="Version",
        help="Free-form version string (e.g., '1.0', '2025.11').",
        required=True,
        default="1.0",
        tracking=True,
    )

    version_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("review", "In Review"),
            ("published", "Published"),
            ("deprecated", "Deprecated"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    effective_date = fields.Date(
        string="Effective Date",
        help="Date when the protocol becomes valid for clinical use.",
        tracking=True,
    )

    retire_date = fields.Date(
        string="Retire Date",
        help="Date when the protocol is retired and should not be used in new care plans.",
        tracking=True,
    )

    change_log = fields.Html(
        string="Change Log",
        help="Changelog and clinical rationale for updates across versions.",
        sanitize=True,
    )

    # ------------------------------------------------------------------------------------------
    # Classification & Risk
    # ------------------------------------------------------------------------------------------
    category = fields.Selection(
        [
            ("aesthetic", "Aesthetic/Dermatology"),
            ("laser", "Laser/Device"),
            ("injectable", "Injectable/Pharmacology"),
            ("hair", "Hair/Scalp"),
            ("wellness", "Wellness/Body"),
            ("dental", "Dental"),
            ("post_op", "Post-Operative Care"),
            ("other", "Other"),
        ],
        string="Category",
        help="Primary clinical category for grouping and filtering protocols.",
        default="aesthetic",
        tracking=True,
        index=True,
    )

    risk_level = fields.Selection(
        [("low", "Low"), ("moderate", "Moderate"), ("high", "High")],
        string="Risk Level",
        help="Overall clinical risk level to help determine consent and monitoring requirements.",
        default="low",
        tracking=True,
    )

    contraindications = fields.Html(
        string="Contraindications",
        help="Conditions under which this protocol should not be used.",
        sanitize=True,
    )

    preconditions = fields.Html(
        string="Preconditions",
        help="Requirements that must be met prior to starting this protocol (e.g., lab values, photos, signed consent).",
        sanitize=True,
    )

    patient_education = fields.Html(
        string="Patient Education",
        help="Patient-facing education, preparation, and post-care instructions.",
        sanitize=True,
    )

    # ------------------------------------------------------------------------------------------
    # Protocol Composition
    # ------------------------------------------------------------------------------------------
    step_ids = fields.One2many(
        "clinic.care.protocol.step",
        "protocol_id",
        string="Protocol Steps",
        help="Ordered steps that define the protocol.",
    )

    treatment_ids = fields.Many2many(
        "clinic.treatment",
        "clinic_care_protocol_treatment_rel",
        "protocol_id",
        "treatment_id",
        string="Related Treatments",
        help="Treatments typically referenced by this protocol.",
    )

    product_ids = fields.Many2many(
        "product.product",
        "clinic_care_protocol_product_rel",
        "protocol_id",
        "product_id",
        string="Recommended Products",
        help="Retail/consumable products recommended in the protocol.",
    )

    # ------------------------------------------------------------------------------------------
    # Estimates & Aggregates
    # ------------------------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    total_steps = fields.Integer(
        string="Total Steps",
        help="Number of steps in this protocol.",
        compute="_compute_aggregates",
        store=True,
    )

    estimated_total_minutes = fields.Integer(
        string="Estimated Total Minutes",
        help="Sum of duration estimates from all protocol steps.",
        compute="_compute_aggregates",
        store=True,
    )

    consumable_estimated_amount = fields.Monetary(
        string="Estimated Consumable Cost",
        help="Estimated cost based on step products and quantities (retail price by default).",
        currency_field="currency_id",
        compute="_compute_cost_estimate",
        store=True,
        readonly=True,
    )

    day_span = fields.Integer(
        string="Estimated Day Span",
        help="Estimated day span from step scheduling offsets (max expected_day_offset + 1).",
        compute="_compute_day_span",
        store=True,
    )

    plan_count = fields.Integer(
        string="Care Plans",
        compute="_compute_plan_count",
        store=False,
        help="Number of care plans currently using this protocol template.",
    )

    # ------------------------------------------------------------------------------------------
    # Attachments & Flags
    # ------------------------------------------------------------------------------------------
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_care_protocol_attachment_rel",
        "protocol_id",
        "attachment_id",
        string="Attachments",
        help="Supporting documents (e.g., PDFs, consent templates, references).",
    )

    active = fields.Boolean(default=True, tracking=True)

    # ------------------------------------------------------------------------------------------
    # COMPUTES
    # ------------------------------------------------------------------------------------------
    @api.depends("step_ids.duration_minutes")
    def _compute_aggregates(self):
        for rec in self:
            rec.total_steps = len(rec.step_ids)
            rec.estimated_total_minutes = sum(s.duration_minutes for s in rec.step_ids if s.duration_minutes)

    @api.depends("step_ids.product_id", "step_ids.product_id.list_price", "step_ids.qty")
    def _compute_cost_estimate(self):
        """Heuristic: multiply step qty by product list price.
        Adjust this logic in your project if you maintain clinical cost prices.
        """
        for rec in self:
            amount = 0.0
            for s in rec.step_ids:
                if s.product_id and s.qty:
                    # Use list_price; replace with standard_price if you estimate internal costs
                    amount += (s.product_id.list_price or 0.0) * s.qty
            rec.consumable_estimated_amount = amount

    @api.depends("step_ids.expected_day_offset")
    def _compute_day_span(self):
        for rec in self:
            if not rec.step_ids:
                rec.day_span = 0
            else:
                max_offset = max(s.expected_day_offset or 0 for s in rec.step_ids)
                rec.day_span = int(max_offset) + 1 if max_offset >= 0 else 0

    def _compute_plan_count(self):
        CarePlan = self.env["clinic.care.plan"]
        for rec in self:
            rec.plan_count = CarePlan.search_count(
                [("protocol_template_id", "=", rec.id)]
            )

    # ------------------------------------------------------------------------------------------
    # CONSTRAINTS & ONCHANGES
    # ------------------------------------------------------------------------------------------
    @api.constrains("effective_date", "retire_date")
    def _check_dates(self):
        for rec in self:
            if rec.effective_date and rec.retire_date and rec.retire_date < rec.effective_date:
                raise ValidationError(_("Retire Date cannot be earlier than Effective Date."))

    @api.constrains("version_state", "effective_date", "step_ids")
    def _check_publish_requirements(self):
        for rec in self:
            if rec.version_state == "published":
                if not rec.effective_date:
                    raise ValidationError(_("Effective Date is required for Published protocols."))
                if not rec.step_ids:
                    raise ValidationError(_("At least one Protocol Step is required before publishing."))

    @api.onchange("owner_doctor_id")
    def _onchange_owner_doctor(self):
        if self.owner_doctor_id and self.owner_doctor_id.partner_id:
            # Helpful hint in chatter/note-like field
            self.description = (self.description or "") or _(
                "Clinical owner is set. Ensure protocol adheres to clinic policy and regulatory guidance."
            )

    # ------------------------------------------------------------------------------------------
    # CRUD OVERRIDES
    # ------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Auto-subscribe owner and reviewers to changes
            partner_ids = []
            if rec.owner_doctor_id and rec.owner_doctor_id.partner_id:
                partner_ids.append(rec.owner_doctor_id.partner_id.id)
            if rec.reviewer_ids:
                partner_ids += rec.reviewer_ids.mapped("partner_id").ids
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        res = super().write(vals)
        tracked = {"version_state", "version", "owner_doctor_id", "effective_date", "retire_date"}
        if any(k in tracked for k in vals.keys()):
            for rec in self:
                rec.message_post(
                    body=_("Protocol updated (key fields changed)."),
                    subtype_xmlid="mail.mt_note",
                )
        return res

    # ------------------------------------------------------------------------------------------
    # ACTIONS — Version Lifecycle
    # ------------------------------------------------------------------------------------------
    def _suggest_next_version(self):
        """Simple version bump helper: '1.0' -> '1.1', '2' -> '3' etc."""
        self.ensure_one()
        v = (self.version or "1.0").strip()
        # Try float-like bump, else numeric bump, else append '-new'
        try:
            fv = float(v)
            return f"{fv + 0.1:.1f}"
        except Exception:
            if v.isdigit():
                return str(int(v) + 1)
            return f"{v}-new"

    def action_submit_review(self):
        self.write({"version_state": "review"})
        for rec in self:
            rec.message_post(body=_("Protocol submitted for clinical review."), subtype_xmlid="mail.mt_comment")

    def action_publish(self):
        for rec in self:
            if not rec.step_ids:
                raise UserError(_("Cannot publish a protocol without steps."))
            if not rec.effective_date:
                rec.effective_date = date.today()
            rec.version_state = "published"
            rec.message_post(body=_("Protocol has been published."), subtype_xmlid="mail.mt_note")

    def action_deprecate(self):
        for rec in self:
            rec.version_state = "deprecated"
            if not rec.retire_date:
                rec.retire_date = date.today()
            rec.message_post(body=_("Protocol has been deprecated."), subtype_xmlid="mail.mt_note")

    def action_clone_new_draft(self):
        """Clone to a new draft with suggested version bump; steps & relations are duplicated."""
        self.ensure_one()
        new_vals = self.copy_data()[0]
        new_vals.update({
            "version_state": "draft",
            "version": self._suggest_next_version(),
            "effective_date": False,
            "retire_date": False,
            "name": self.env["ir.sequence"].next_by_code("clinic.care.protocol") or _("New"),
        })
        new_protocol = self.create(new_vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("New Draft Protocol"),
            "res_model": "clinic.care.protocol",
            "view_mode": "form",
            "res_id": new_protocol.id,
            "target": "current",
        }

    # ------------------------------------------------------------------------------------------
    # ACTIONS — Apply to Care Plan (Bridge to clinic.care.plan)
    # ------------------------------------------------------------------------------------------
    def action_create_plan(self):
        """Open Care Plan form pre-filled with this protocol."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Care Plan"),
            "res_model": "clinic.care.plan",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_protocol_template_id": self.id,
                "default_display_name": "%s — %s" % (self.display_name or self.name or _("Protocol"), _("Care Plan")),
                "default_plan_type": "aesthetic",
            },
        }

    def action_generate_plan_for_patient(self):
        """Create a Care Plan for a given patient (expects 'default_patient_id' in context)."""
        self.ensure_one()
        patient = self.env.context.get("default_patient_id")
        if not patient:
            raise UserError(_("Please provide a patient (context key: default_patient_id)."))
        plan = self.env["clinic.care.plan"].create({
            "display_name": "%s — %s" % (self.display_name or self.name or _("Protocol"), _("Care Plan")),
            "plan_type": "aesthetic",
            "patient_id": patient,
            "protocol_template_id": self.id,
            "start_date": fields.Date.context_today(self),
            "company_id": self.env.company.id,
        })
        # Optionally generate lines now (depends on care_plan_line model)
        plan.action_generate_lines_from_protocol()
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plan"),
            "res_model": "clinic.care.plan",
            "view_mode": "form",
            "res_id": plan.id,
            "target": "current",
        }

    def action_view_plans(self):
        """Open care plans that use this protocol template."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plans"),
            "res_model": "clinic.care.plan",
            "view_mode": "list,form",
            "domain": [("protocol_template_id", "=", self.id)],
            "context": {
                "default_protocol_template_id": self.id,
                "default_company_id": self.company_id.id,
            },
            "target": "current",
        }

    def action_view_steps(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Protocol Steps"),
            "res_model": "clinic.care.protocol.step",
            "view_mode": "list,form",
            "domain": [("protocol_id", "=", self.id)],
            "target": "current",
        }

    # ------------------------------------------------------------------------------------------
    # RECORD LABEL COMPATIBILITY
    # ``display_name`` is a stored business title in this model, so the
    # legacy helper remains callable without replacing that field.
    # ------------------------------------------------------------------------------------------
    def name_get(self):
        result = []
        for rec in self:
            label = "[%s] %s (v%s)" % (rec.name or _("New"), rec.display_name or "", rec.version or "1.0")
            result.append((rec.id, label))
        return result

    # ------------------------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # ------------------------------------------------------------------------------------------
    _name_unique = models.Constraint(
        "unique(name)",
        "Protocol Code must be unique.",
    )
