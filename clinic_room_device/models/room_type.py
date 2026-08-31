
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicRoomType(models.Model):
    _name = "clinic.room.type"
    _description = "Clinic Room Type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _rec_name = "display_name"

    # Identity
    name = fields.Char(string="Room Type Name", required=True, index=True, tracking=True)
    code = fields.Char(string="Code", index=True, tracking=True)
    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company, index=True)
    color = fields.Integer(string="Color Index")
    description = fields.Html(string="Description/Notes")
    image_1920 = fields.Image(max_width=1920, max_height=1920)
    image_512 = fields.Image(related="image_1920", store=True, max_width=512, max_height=512)

    # Classification
    usage_kind = fields.Selection(
        [
            ("consultation", "Consultation/Polyclinic"),
            ("treatment", "Treatment/Procedure"),
            ("surgery", "Operating Theatre / Minor OR"),
            ("lab", "Laboratory"),
            ("imaging", "Imaging (X-Ray/USG/MRI/CT)"),
            ("ward", "Ward/Bed"),
            ("other", "Other"),
        ],
        string="Usage Kind",
        default="consultation",
        tracking=True,
    )

    # Booking / Queue Policy (diturunkan ke clinic.room)
    booking_policy = fields.Selection(
        [
            ("exclusive", "Exclusive (1 session at a time)"),
            ("shared", "Shared (parallel up to capacity)"),
            ("queue_based", "Queue Based"),
        ],
        string="Default Booking Policy",
        default="exclusive",
        tracking=True,
    )
    require_queue = fields.Boolean(string="Require Queue Channel", compute="_compute_require_queue", store=True)

    default_capacity = fields.Integer(string="Default Capacity", default=1, tracking=True)
    default_is_bookable = fields.Boolean(string="Default Bookable", default=True, tracking=True)

    # Device & Products (editable; NO compute, NO depends)
    device_category_ids = fields.Many2many(
        "clinic.device.category",
        "clinic_room_type_device_category_rel",
        "room_type_id",
        "device_category_id",
        string="Relevant Device Categories",
    )
    # feature_product_ids = fields.Many2many(
    #     "product.product",
    #     "clinic_room_type_feature_product_rel",
    #     "room_type_id",
    #     "product_id",
    #     string="Featured Products / Consumables (Editable)",
    #     # HANYA domain aman; TANPA @depends & TANPA compute
    #     domain=[("product_tmpl_id.detailed_type", "in", ["service", "consu", "product"])],
    #     help="Daftar produk/consumables rekomendasi; bisa diedit manual.",
    # )

    feature_product_ids = fields.Many2many(
        "product.product",
        "clinic_room_type_feature_product_rel",
        "room_type_id",
        "product_id",
        string="Featured Products / Consumables (Editable)",
        help="Recommended products/consumables commonly used in this room type.",
    )

    maintenance_team_id = fields.Many2one("maintenance.team", string="Default Maintenance Team")

    # Backlinks / Metrics
    room_ids = fields.One2many("clinic.room", "room_type_id", string="Rooms of this Type")
    room_count = fields.Integer(string="Rooms", compute="_compute_room_count", store=False)
    
    doctor_ids = fields.Many2many(
        "hr.employee",
        relation="clinic_doctor_room_type_rel",
        column1="room_type_id",   # mirror
        column2="employee_id",    # mirror
        string="Doctors",
    )

    # Constraints
        # Odoo 19 table constraints
    _code_company_uniq = models.Constraint(
        'unique(company_id, code)',
        'Type Code must be unique per company.',
    )
    _capacity_nonneg = models.Constraint(
        'CHECK (default_capacity >= 0)',
        'Default Capacity cannot be negative.',
    )

    
    @api.constrains("feature_product_ids")
    def _check_feature_products_type(self):
        """
        Pastikan produk yang dipilih bertipe valid.
        Mengingat environment Anda hanya punya field 'type', maka valid: service/consu/product.
        """
        # Odoo 19 product.template.type uses `consu` for Goods and `service`
        # for services; legacy selection value `product` no longer exists.
        allowed = {"service", "consu"}
        for rec in self:
            wrong = rec.feature_product_ids.filtered(lambda p: (p.type or "") not in allowed)
            if wrong:
                raise ValidationError(_("Featured products must be Goods or Service products."))

    # Computes
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "[%s] %s" % (rec.code, rec.name) if rec.code else (rec.name or "")

    @api.depends("booking_policy")
    def _compute_require_queue(self):
        for rec in self:
            rec.require_queue = (rec.booking_policy == "queue_based")

    @api.depends("room_ids")
    def _compute_room_count(self):
        for rec in self:
            rec.room_count = len(rec.room_ids)

    # ORM
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = (vals["code"] or "").strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals and vals["code"]:
            vals["code"] = (vals["code"] or "").strip().upper()
        if "default_capacity" in vals and (vals["default_capacity"] or 0) < 0:
            raise ValidationError(_("Default Capacity cannot be negative."))
        return super().write(vals)

    # Onchange (optional suggestion; no depends)
    # @api.onchange("usage_kind", "device_category_ids")
    # def _onchange_suggest_feature_products(self):
    #     if self.feature_product_ids:
    #         return
    #     domain = [("product_tmpl_id.detailed_type", "in", ["consu"])]
    #     suggested = self.env["product.product"].search(domain, limit=10)
    #     if suggested:
    #         self.feature_product_ids = [(6, 0, suggested.ids)]

    @api.onchange("usage_kind", "device_category_ids")
    def _onchange_suggest_feature_products(self):
        """
        Saran ringan (tidak wajib): jika belum ada daftar fitur, sarankan 10 produk
        dengan tipe konsultan/produk/consumable. Gunakan fallback aman:
        - product.product.type
        - product_tmpl_id.type (jika tersedia)
        """
        if self.feature_product_ids:
            return
        Product = self.env["product.product"]
        # Domain aman: tipe di product.product OR tipe di template
        domain = ["|", "|",
                  ("type", "in", ["consu", "service"]),
                  ("product_tmpl_id.type", "=", "service"),
                  ("product_tmpl_id.type", "in", ["consu"])]
        suggested = Product.search(domain, limit=10)
        if suggested:
            self.feature_product_ids = [(6, 0, suggested.ids)]


    # Name helpers
    def name_get(self):
        return [(r.id, r.display_name or r.name or "") for r in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        search_domain = ["|", ("code", operator, name), ("name", operator, name)] if name else []
        return self.search(search_domain + domain, limit=limit).name_get()

    # Actions
    def action_view_rooms(self):
        self.ensure_one()
        return {
            "name": _("Rooms"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "list,form",
            "domain": [("room_type_id", "=", self.id)],
            "context": {"default_room_type_id": self.id},
        }

    # def action_view_feature_products(self):
    #     self.ensure_one()
    #     return {
    #         "name": _("Featured Products"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "product.product",
    #         "view_mode": "list,form",
    #         "domain": [("id", "in", self.feature_product_ids.ids or [])],
    #     }
