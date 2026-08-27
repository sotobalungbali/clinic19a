
# -*- coding: utf-8 -*-
# File: models/triage_tag.py
#
# ClinicOne - Triage & Vitals Intake
# Model: clinic.triage.tag
#
# Purpose:
# - Flexible tagging system for Triage Sessions to categorize presentations
#   (e.g., Trauma, Allergy, Pediatric, Dermatology/Aesthetic).
# - Plays nicely with queue/room recommendation, default activities, and (optional) billing hooks.
# - English UI strings per product requirement.
#
# IMPORTANT: This model expects the triage session M2M in clinic_triage_vitals/models/triage_session.py
# to use the same relation table and comodel:
#   triage_tag_ids = fields.Many2many(
#       "clinic.triage.tag",
#       "clinic_triage_session_tag_rel",
#       "session_id", "tag_id", ...
#   )
# If your triage_session still uses the old 'clinicone.*' naming, update it accordingly.

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


HEX_COLOR_RE = re.compile(r"^#([0-9A-Fa-f]{6})$")


class ClinicTriageTag(models.Model):
    _name = "clinic.triage.tag"
    _description = "Clinic Triage Tag"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "sequence, name, id"

    # -------------------------------------------------------------------------
    # Identity & Display
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        tracking=True,
        help="Display name of the triage tag (e.g., 'Trauma', 'Allergy', 'Pediatric', 'Cosmetic')."
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        tracking=True,
        help="Short unique code for quick reference (e.g., TRM, ALG, PED, CST)."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Ordering helper; lower values appear first."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to hide this tag without deleting it."
    )
    color = fields.Integer(
        string="Kanban Color",
        default=0,
        help="Optional color index used by Kanban views."
    )
    color_hex = fields.Char(
        string="Hex Color",
        help="Optional hex color code for this tag (e.g., #FF5722)."
    )
    image_128 = fields.Image(
        string="Icon",
        max_width=128,
        max_height=128,
        help="Optional icon for visual identification in Kanban or form views."
    )
    description = fields.Text(
        string="Description",
        help="Short description of what this tag represents."
    )
    guidelines_html = fields.Html(
        string="Guidelines",
        sanitize=False,
        help="Internal guidelines for staff when handling cases that match this tag."
    )

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
    tag_type = fields.Selection(
        selection=[
            ("clinical", "Clinical"),
            ("symptom", "Symptom"),
            ("condition", "Condition"),
            ("procedure", "Procedure"),
            ("safety", "Safety"),
            ("allergy", "Allergy"),
            ("pediatric", "Pediatric"),
            ("obstetric", "Obstetric"),
            ("dermatology", "Dermatology"),
            ("aesthetic", "Aesthetic/Cosmetic"),
            ("administrative", "Administrative"),
            ("other", "Other"),
        ],
        string="Tag Type",
        default="clinical",
        required=True,
        help="Functional classification for this tag to support filtering and automation."
    )

    parent_id = fields.Many2one(
        "clinic.triage.tag",
        string="Parent Tag",
        help="Optional parent tag to build a simple hierarchy."
    )
    child_ids = fields.One2many(
        "clinic.triage.tag",
        "parent_id",
        string="Child Tags"
    )

    # -------------------------------------------------------------------------
    # Company & Currency
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Owning company for this tag."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # Routing / Activities / Billing (optional hooks)
    # -------------------------------------------------------------------------
    recommended_room_type_id = fields.Many2one(
        "clinic.room.type",
        string="Recommended Room Type",
        help="Recommended room type when this tag is present."
    )
    default_queue_stage_id = fields.Many2one(
        "clinic.queue.stage",
        string="Default Queue Stage",
        help="Default queue stage to apply on check-in when this tag is present (if queue module is installed)."
    )
    default_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Default Activity Type",
        help="Suggested activity type to create for follow-up tasks when this tag is applied."
    )
    billable = fields.Boolean(
        string="Billable",
        help="Enable if the presence of this tag typically requires billing an additional service/product."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Service/Product",
        help="Default service or product to add to the bill if this tag is billable."
    )
    default_fee = fields.Monetary(
        string="Default Fee",
        help="Default fee suggested when billing is triggered by this tag."
    )

    # -------------------------------------------------------------------------
    # Automation Hints
    # -------------------------------------------------------------------------
    rule_domain = fields.Char(
        string="Suggested Rule Domain",
        help="Optional Odoo domain that describes when this tag should be suggested automatically."
    )

    # -------------------------------------------------------------------------
    # Relations to Triage Sessions
    # -------------------------------------------------------------------------
    session_ids = fields.Many2many(
        "clinic.triage.session",
        "clinic_triage_session_tag_rel",  # relation table
        "tag_id",                         # this model's column
        "session_id",                     # other model's column
        string="Triage Sessions",
        help="Triage sessions that include this tag."
    )
    session_count = fields.Integer(
        string="Triage Sessions Count",
        compute="_compute_usage_metrics",
        help="Number of triage sessions currently associated with this tag."
    )
    last_used_on = fields.Datetime(
        string="Last Used On",
        compute="_compute_usage_metrics",
        help="The most recent triage end time or update time among sessions that use this tag."
    )

    # -------------------------------------------------------------------------
    # Constraints (SQL)
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "The tag code must be unique per company.",
    )
    _name_company_uniq = models.Constraint(
        "UNIQUE(name, company_id)",
        "The tag name must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # Onchange & ORM overrides
    # -------------------------------------------------------------------------
    @api.onchange("code")
    def _onchange_code_upper(self):
        """Normalize the code when edited."""
        if self.code:
            self.code = self.code.strip().upper()

    @api.onchange("color_hex")
    def _onchange_color_hex(self):
        """Early UX validation for hex color format."""
        if self.color_hex and not HEX_COLOR_RE.match(self.color_hex):
            return {
                "warning": {
                    "title": _("Invalid Hex Color"),
                    "message": _("Please provide a valid 6-digit hex color in the form '#RRGGBB'."),
                }
            }

    @api.constrains("color_hex", "code", "company_id", "product_id", "billable")
    def _check_constraints(self):
        for rec in self:
            if rec.color_hex and not HEX_COLOR_RE.match(rec.color_hex):
                raise ValidationError(_("Hex Color must be a valid 6-digit value in the form '#RRGGBB'."))
            if rec.product_id and not rec.billable:
                # If a product is set, it makes sense that the tag is billable.
                raise ValidationError(_("Enable 'Billable' when a Service/Product is set for this tag."))
            # Company consistency for product (multi-company safety)
            if rec.product_id and rec.product_id.company_id and rec.product_id.company_id != rec.company_id:
                raise ValidationError(_("The Service/Product must belong to the same company as the tag."))

    @api.model_create_multi
    def create(self, vals_list):
        # Normalize codes and ensure company default.
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
        records = super().create(vals_list)
        for rec in records:
            rec.message_post(
                body=_("Triage tag created: <b>%(name)s</b> [%(code)s].") % {"name": rec.name, "code": rec.code},
                subtype_xmlid="mail.mt_note",
            )
        return records

    def write(self, vals):
        if "code" in vals and vals["code"]:
            vals["code"] = vals["code"].strip().upper()
        res = super().write(vals)
        tracked = {"tag_type", "billable", "product_id", "default_queue_stage_id", "recommended_room_type_id"}
        if tracked.intersection(vals.keys()):
            for rec in self:
                parts = []
                if "tag_type" in vals:
                    parts.append(_("Tag Type: %s") % dict(self._fields["tag_type"].selection).get(rec.tag_type))
                if "billable" in vals:
                    parts.append(_("Billable: %s") % (_("Yes") if rec.billable else _("No")))
                if "product_id" in vals and rec.product_id:
                    parts.append(_("Service/Product: %s") % rec.product_id.display_name)
                if "default_queue_stage_id" in vals and rec.default_queue_stage_id:
                    parts.append(_("Default Queue Stage: %s") % rec.default_queue_stage_id.display_name)
                if "recommended_room_type_id" in vals and rec.recommended_room_type_id:
                    parts.append(_("Recommended Room Type: %s") % rec.recommended_room_type_id.display_name)
                if parts:
                    rec.message_post(body="<br/>".join(parts), subtype_xmlid="mail.mt_note")
        return res

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    @api.depends("session_ids", "session_ids.end_datetime", "session_ids.write_date")
    def _compute_usage_metrics(self):
        """Compute the number of linked sessions and the latest usage time.

        Note:
        - Depends includes 'session_ids.end_datetime' and 'session_ids.write_date'
          so it refreshes when sessions change. This may perform individual
          searches per record; optimize with SQL/read_group if needed later.
        """
        Session = self.env["clinic.triage.session"]
        for rec in self:
            # Count sessions efficiently
            count = Session.search_count([("triage_tag_ids", "in", rec.id)])
            rec.session_count = count

            # Find most recent usage (prefer end_datetime, fallback to write_date)
            last_dt = False
            if count:
                last = Session.search(
                    [("triage_tag_ids", "in", rec.id)],
                    order="end_datetime desc, write_date desc",
                    limit=1,
                )
                if last:
                    last_dt = last.end_datetime or last.write_date
            rec.last_used_on = last_dt

    # -------------------------------------------------------------------------
    # Actions / UI helpers
    # -------------------------------------------------------------------------
    def action_view_sessions(self):
        """Open triage sessions filtered by this tag (single) or these tags (multi)."""
        self.ensure_one()
        action = self.env.ref("clinic_triage_vitals.action_clinic_triage_session").read()[0]
        action["domain"] = [("triage_tag_ids", "in", self.id)]
        action["context"] = dict(self.env.context or {}, default_company_id=self.company_id.id)
        return action

    @api.depends("name", "code")
    def _compute_display_name(self):
        """Build the Odoo 19 display name used by relational widgets."""
        for rec in self:
            parts = [rec.name or _("Triage Tag")]
            if rec.code:
                parts.append("[%s]" % rec.code)
            rec.display_name = " ".join(parts)

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
