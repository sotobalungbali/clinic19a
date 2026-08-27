# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_attribute.py
#
# Models:
#  - clinic.treatment.attribute        : Master attribute (type, scope, single/multi)
#  - clinic.treatment.attribute.value  : Attribute options for 'select' type
#  - clinic.treatment.attribute.line   : Assignment of attributes to treatments
#
# Design goals:
#  - Multi-company aware & secure
#  - No hard dependency to other ClinicOne modules (safe fallbacks)
#  - Optional audit integration (clinic.audit.event), fallback to chatter
#  - Efficient counts via _read_group
#
# Typical use cases:
#  - Clinical descriptors: skin type, sensitivity level, gender suitability
#  - Operational: therapist technique, equipment mode, pre/post care
#  - Commercial: marketing flags, ecommerce facets/filters
#  - Analytics: reporting tags, segmentation
#
# Sequences referenced (declare in data/sequence.xml):
#  - clinic_treatment_catalog.seq_treatment_attribute_code
#  - clinic_treatment_catalog.seq_treatment_attribute_value_code

from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


# ============================================================================
# MASTER ATTRIBUTE
# ============================================================================
class ClinicTreatmentAttribute(models.Model):
    _name = "clinic.treatment.attribute"
    _description = "Clinic Treatment Attribute"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # Identity / Basics
    name = fields.Char(
        string="Attribute Name",
        required=True,
        tracking=True,
        index=True,
        help="Nama atribut, mis. 'Skin Type', 'Gender', 'Technique', 'Sensitivity'."
    )
    code = fields.Char(
        string="Code",
        copy=False,
        index=True,
        tracking=True,
        help="Kode unik per perusahaan (auto dari sequence jika tersedia)."
    )
    technical_name = fields.Char(
        string="Technical Name",
        help="Slug/identifier teknis (lowercase_snake) untuk integrasi lintas modul/API.",
        index=True
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Urutan tampil di list/kanban."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True
    )

    # Company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    # Typing & Scope
    value_type = fields.Selection(
        selection=[
            ("select", "Select (Options)"),
            ("number", "Number"),
            ("text", "Text"),
            ("boolean", "Boolean"),
            ("date", "Date"),
            ("datetime", "Datetime"),
            ("range", "Range (Min/Max)"),
        ],
        string="Value Type",
        required=True,
        default="select",
        tracking=True,
        help="Jenis nilai yang diperbolehkan untuk atribut ini."
    )
    selection_mode = fields.Selection(
        selection=[("single", "Single"), ("multi", "Multiple")],
        string="Selection Mode",
        default="single",
        required=True,
        help="Berlaku jika 'Value Type' adalah 'select'."
    )
    scope = fields.Selection(
        selection=[
            ("clinical", "Clinical"),
            ("operational", "Operational"),
            ("marketing", "Marketing"),
            ("ecommerce", "eCommerce/Portal"),
            ("membership", "Membership"),
            ("insurance", "Insurance"),
            ("reporting", "Reporting/Analytics"),
            ("generic", "Generic"),
        ],
        string="Scope",
        required=True,
        default="generic",
        help="Konteks utama penggunaan atribut untuk menjaga konsistensi lintas modul."
    )

    description = fields.Html(string="Description", sanitize=True)
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)

    # Relations
    value_ids = fields.One2many(
        "clinic.treatment.attribute.value",
        "attribute_id",
        string="Values"
    )
    line_ids = fields.One2many(
        "clinic.treatment.attribute.line",
        "attribute_id",
        string="Assignments"
    )

    # Counters
    value_count = fields.Integer(
        string="Values",
        compute="_compute_counts"
    )
    treatment_count = fields.Integer(
        string="Treatments Using",
        compute="_compute_counts",
        help="Jumlah treatment yang menggunakan atribut ini (langsung via lines)."
    )

    # Constraints
    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Code must be unique per company.",
    )
    _technical_company_uniq = models.Constraint(
        "unique(technical_name, company_id)",
        "Technical Name must be unique per company.",
    )

    # -----------------------------
    # Computes
    # -----------------------------
    def _compute_counts(self):
        if self.ids:
            # Values
            groups_val = self.env["clinic.treatment.attribute.value"]._read_group(
                [("attribute_id", "in", self.ids)],
                ["attribute_id"],
                ["__count"],
            )
            val_map = {attribute.id: count for attribute, count in groups_val if attribute}
            # Lines (treatment usage)
            groups_line = self.env["clinic.treatment.attribute.line"]._read_group(
                [("attribute_id", "in", self.ids)],
                ["attribute_id"],
                ["__count"],
            )
            line_map = {attribute.id: count for attribute, count in groups_line if attribute}
        else:
            val_map, line_map = {}, {}
        for rec in self:
            rec.value_count = val_map.get(rec.id, 0)
            rec.treatment_count = line_map.get(rec.id, 0)

    # -----------------------------
    # Onchange / Constrains
    # -----------------------------
    @api.constrains("value_type", "selection_mode")
    def _check_selection_mode(self):
        for rec in self:
            if rec.value_type != "select" and rec.selection_mode != "single":
                # selection_mode irrelevant for non-select, normalize to single
                rec.selection_mode = "single"

    @api.constrains("technical_name")
    def _check_technical_name_format(self):
        for rec in self:
            if rec.technical_name and not tools.config["admin_password"]:  # no-op to avoid expensive regex import
                # Lightweight check to encourage snake_case (skip strict regex to keep performance)
                if " " in rec.technical_name:
                    raise ValidationError(_("Technical Name should not contain spaces. Use snake_case."))

    # -----------------------------
    # ORM overrides
    # -----------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_attribute_code", raise_if_not_found=False)
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("code") and seq:
                vals["code"] = seq._next()
        recs = super().create(vals_list)
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        tracked = {"name", "code", "technical_name", "value_type", "selection_mode", "scope", "active", "sequence"}
        if set(vals).intersection(tracked):
            self._audit_event("write", changed_fields=list(set(vals).intersection(tracked)))
        return res

    def unlink(self):
        """Cegah hapus jika masih dipakai oleh treatment (ada line)."""
        Line = self.env["clinic.treatment.attribute.line"]
        for rec in self:
            if Line.search_count([("attribute_id", "=", rec.id)]) > 0:
                raise UserError(_("You cannot delete an attribute that is assigned to treatments. Archive it instead."))
        return super().unlink()

    # -----------------------------
    # Helpers / Audit
    # -----------------------------
    def _audit_event(self, action, changed_fields=None):
        self.message_post(body=_("Attribute %s: %s") % (action, ", ".join(changed_fields or [])))
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "attribute.%s" % action,
                    "model": rec._name,
                    "res_id": rec.id,
                    "company_id": rec.company_id.id,
                    "payload": {"changed_fields": changed_fields or [], "user_id": self.env.user.id},
                })
            except Exception as e:  # pragma: no cover
                _logger.debug("Audit event skipped: %s", e)

    # -----------------------------
    # Actions / Smart Buttons
    # -----------------------------
    def action_open_treatments(self):
        """Buka daftar treatment yang memakai atribut ini (via lines)."""
        self.ensure_one()
        action = self.env.ref("clinic_treatment_catalog.action_treatment_tree", raise_if_not_found=False)
        domain = [("id", "in", self.line_ids.mapped("treatment_id").ids)]
        name = _("Treatments using attribute: %s") % (self.name,)
        if action:
            res = action.read()[0]
            res["name"] = name
            res["domain"] = domain
            return res
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "clinic.treatment.catalog",
            "view_mode": "list,form",
            "domain": domain,
        }

    # -----------------------------
    # Name get / search
    # -----------------------------
    def _clinic_display_label(self):
        self.ensure_one()
        return "[%s] %s" % (self.code, self.name) if self.code else self.name

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        return [(rec.id, rec._clinic_display_label()) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        criteria = ["|", "|", ("code", operator, name), ("name", operator, name), ("technical_name", operator, name)] if name else []
        recs = self.search(criteria + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# ============================================================================
# ATTRIBUTE VALUE (for select type)
# ============================================================================
class ClinicTreatmentAttributeValue(models.Model):
    _name = "clinic.treatment.attribute.value"
    _description = "Clinic Treatment Attribute Value"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "attribute_id, sequence, name"
    _check_company_auto = True

    # Basics
    name = fields.Char(
        string="Value",
        required=True,
        tracking=True,
        index=True,
        help="Nama nilai/opsi, mis. 'Oily', 'Dry', 'Sensitive', 'Male', 'Female'."
    )
    code = fields.Char(
        string="Code",
        copy=False,
        index=True,
        tracking=True,
        help="Kode unik per attribute & company (auto dari sequence jika tersedia)."
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    color = fields.Integer(string="Color Index")

    # Link to Attribute / Company
    attribute_id = fields.Many2one(
        "clinic.treatment.attribute",
        string="Attribute",
        required=True,
        ondelete="cascade",
        index=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="attribute_id.company_id",
        store=True,
        readonly=True
    )

    # Optional commercial/operational deltas (used by pricing/variant engines)
    delta_price = fields.Monetary(
        string="Delta Price",
        currency_field="currency_id",
        help="Penyesuaian harga (+/-) ketika nilai ini digunakan (opsional, dipakai engine lain)."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )
    delta_duration_minutes = fields.Integer(
        string="Delta Duration (min)",
        help="Penyesuaian durasi layanan (+/- menit) bila nilai ini digunakan (opsional)."
    )

    # Counters
    treatment_count = fields.Integer(
        string="Treatments Using",
        compute="_compute_counts"
    )

    # Constraints
    _code_attr_company_uniq = models.Constraint(
        "unique(code, attribute_id, company_id)",
        "Value code must be unique per attribute and company.",
    )

    # -----------------------------
    # Computes
    # -----------------------------
    def _compute_counts(self):
        Line = self.env["clinic.treatment.attribute.line"]
        if self.ids:
            groups = Line._read_group(
                [("value_id", "in", self.ids)],
                ["value_id"],
                ["__count"],
            )
            m = {value.id: count for value, count in groups if value}
        else:
            m = {}
        for rec in self:
            rec.treatment_count = m.get(rec.id, 0)

    # -----------------------------
    # ORM overrides
    # -----------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_attribute_value_code", raise_if_not_found=False)
        for vals in vals_list:
            if not vals.get("attribute_id"):
                raise ValidationError(_("Attribute Value must be linked to an Attribute."))
            if not vals.get("code") and seq:
                vals["code"] = seq._next()
        recs = super().create(vals_list)
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        tracked = {"name", "code", "active", "sequence", "delta_price", "delta_duration_minutes", "color"}
        if set(vals).intersection(tracked):
            self._audit_event("write", changed_fields=list(set(vals).intersection(tracked)))
        return res

    def unlink(self):
        Line = self.env["clinic.treatment.attribute.line"]
        for rec in self:
            if Line.search_count([("value_id", "=", rec.id)]) > 0:
                raise UserError(_("You cannot delete a value that is used by treatments. Archive it instead."))
        return super().unlink()

    # -----------------------------
    # Helpers / Audit
    # -----------------------------
    def _audit_event(self, action, changed_fields=None):
        self.message_post(body=_("Attribute Value %s: %s") % (action, ", ".join(changed_fields or [])))
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "attribute_value.%s" % action,
                    "model": rec._name,
                    "res_id": rec.id,
                    "company_id": rec.company_id.id,
                    "payload": {"changed_fields": changed_fields or [], "user_id": self.env.user.id},
                })
            except Exception as e:  # pragma: no cover
                _logger.debug("Audit event skipped: %s", e)

    # -----------------------------
    # Actions / Smart buttons
    # -----------------------------
    def action_open_treatments(self):
        """Buka treatments yang memakai value ini."""
        self.ensure_one()
        action = self.env.ref("clinic_treatment_catalog.action_treatment_tree", raise_if_not_found=False)
        domain = [("id", "in", self.env["clinic.treatment.attribute.line"].search([("value_id", "=", self.id)]).mapped("treatment_id").ids)]
        name = _("Treatments with value: %s (%s)") % (self.name, self.attribute_id.name)
        if action:
            res = action.read()[0]
            res["name"] = name
            res["domain"] = domain
            return res
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "clinic.treatment.catalog",
            "view_mode": "list,form",
            "domain": domain,
        }

    # -----------------------------
    # Name get / search
    # -----------------------------
    def _clinic_display_label(self):
        self.ensure_one()
        label = "[%s] %s" % (self.code, self.name) if self.code else self.name
        return "%s — %s" % (self.attribute_id.name, label)

    @api.depends("code", "name", "attribute_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        return [(rec.id, rec._clinic_display_label()) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = domain or []
        criteria = ["|", ("code", operator, name), ("name", operator, name)] if name else []
        recs = self.search(criteria + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# ============================================================================
# ATTRIBUTE LINE (assignment on treatment)
# ============================================================================
class ClinicTreatmentAttributeLine(models.Model):
    _name = "clinic.treatment.attribute.line"
    _description = "Clinic Treatment Attribute Line"
    _order = "treatment_id, attribute_id, id"
    _check_company_auto = True

    # Link
    treatment_id = fields.Many2one(
        "clinic.treatment.catalog",
        string="Treatment",
        required=True,
        ondelete="cascade",
        index=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="treatment_id.company_id",
        store=True,
        readonly=True
    )

    attribute_id = fields.Many2one(
        "clinic.treatment.attribute",
        string="Attribute",
        required=True,
        ondelete="restrict",
        domain="[('company_id','in',[False, company_id])]",
        index=True
    )
    value_id = fields.Many2one(
        "clinic.treatment.attribute.value",
        string="Value",
        ondelete="restrict",
        help="Wajib diisi bila attribute bertipe 'select'."
    )

    # Free-form value fields (use based on attribute.value_type)
    value_text = fields.Char(string="Text")
    value_number = fields.Float(string="Number")
    value_boolean = fields.Boolean(string="Boolean")
    value_date = fields.Date(string="Date")
    value_datetime = fields.Datetime(string="Datetime")
    value_range_min = fields.Float(string="Range Min")
    value_range_max = fields.Float(string="Range Max")

    display_value = fields.Char(
        string="Display Value",
        compute="_compute_display_value",
        store=False
    )

    # Indexing for analytics/search
    attribute_technical = fields.Char(
        string="Attribute Technical Name",
        related="attribute_id.technical_name",
        store=True
    )

    # Constraints
    # Hindari duplikasi nilai yang sama untuk attribute SELECT mode single.
    _uniq_treatment_attr_value = models.Constraint(
        "unique(treatment_id, attribute_id, value_id)",
        "Duplicate attribute value for the same treatment is not allowed.",
    )

    # -----------------------------
    # Computes
    # -----------------------------
    @api.depends(
        "attribute_id.value_type", "value_id", "value_text", "value_number",
        "value_boolean", "value_date", "value_datetime", "value_range_min", "value_range_max"
    )
    def _compute_display_value(self):
        for rec in self:
            vt = rec.attribute_id.value_type
            if vt == "select":
                rec.display_value = rec.value_id.name if rec.value_id else ""
            elif vt == "text":
                rec.display_value = rec.value_text or ""
            elif vt == "number":
                rec.display_value = tools.format_amount(self.env, rec.value_number or 0.0, currency_id=False)
            elif vt == "boolean":
                rec.display_value = _("Yes") if rec.value_boolean else _("No")
            elif vt == "date":
                rec.display_value = tools.format_date(self.env, rec.value_date) if rec.value_date else ""
            elif vt == "datetime":
                rec.display_value = tools.format_datetime(self.env, rec.value_datetime) if rec.value_datetime else ""
            elif vt == "range":
                if rec.value_range_min or rec.value_range_max:
                    rec.display_value = "%s – %s" % (
                        tools.format_amount(self.env, rec.value_range_min or 0.0, currency_id=False),
                        tools.format_amount(self.env, rec.value_range_max or 0.0, currency_id=False),
                    )
                else:
                    rec.display_value = ""
            else:
                rec.display_value = ""

    # -----------------------------
    # Onchange / Constrains
    # -----------------------------
    @api.onchange("attribute_id")
    def _onchange_attribute_id_reset_values(self):
        for rec in self:
            rec.value_id = False
            rec.value_text = False
            rec.value_number = 0.0
            rec.value_boolean = False
            rec.value_date = False
            rec.value_datetime = False
            rec.value_range_min = 0.0
            rec.value_range_max = 0.0

    @api.constrains("attribute_id", "value_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.value_id and rec.value_id.attribute_id != rec.attribute_id:
                raise ValidationError(_("Selected Value does not belong to the chosen Attribute."))
            if rec.attribute_id.company_id and rec.attribute_id.company_id != rec.company_id:
                raise ValidationError(_("Attribute company mismatch with Treatment company."))

    @api.constrains(
        "attribute_id", "value_id", "value_text", "value_number",
        "value_boolean", "value_date", "value_datetime", "value_range_min", "value_range_max"
    )
    def _check_value_fields(self):
        for rec in self:
            vt = rec.attribute_id.value_type
            if vt == "select":
                if not rec.value_id:
                    raise ValidationError(_("Value is required for 'select' attribute type."))
            elif vt == "text":
                if not rec.value_text:
                    raise ValidationError(_("Text value is required for this attribute."))
            elif vt == "number":
                # Allow 0.0, but make sure field is not None (ORM ensures float defaults)
                pass
            elif vt == "boolean":
                # boolean can be True/False (no constraint)
                pass
            elif vt == "date":
                if not rec.value_date:
                    raise ValidationError(_("Date value is required for this attribute."))
            elif vt == "datetime":
                if not rec.value_datetime:
                    raise ValidationError(_("Datetime value is required for this attribute."))
            elif vt == "range":
                # if one bound set, require both and min <= max
                has_min = rec.value_range_min not in (None, False)
                has_max = rec.value_range_max not in (None, False)
                if has_min != has_max:
                    raise ValidationError(_("Both Range Min and Range Max must be set."))
                if has_min and rec.value_range_min > rec.value_range_max:
                    raise ValidationError(_("Range Min cannot be greater than Range Max."))

    # -----------------------------
    # Public API Helpers (for other modules)
    # -----------------------------
    def as_kv(self):
        """Return simple key/value representation for API/bridges."""
        self.ensure_one()
        key = self.attribute_id.technical_name or self.attribute_id.code or self.attribute_id.name
        return key, self.display_value or ""

    # -----------------------------
    # Name get
    # -----------------------------
    def _clinic_display_label(self):
        self.ensure_one()
        return "%s: %s" % (self.attribute_id.name, self.display_value or "-")

    @api.depends("attribute_id.name", "display_value")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        return [(rec.id, rec._clinic_display_label()) for rec in self]

