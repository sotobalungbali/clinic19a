# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment.py
#
# Integrasi holistic:
# - Basic Odoo 19 CE: product (service), mail.thread/activity, company, currency, website (opsional)
# - ClinicOne bridges: pricing bridge, booking, billing, inventory-consumables, membership, insurance, reports
#
# Desain tanpa hard dependency:
# - Semua panggilan ke model lain dijaga dengan pemeriksaan ketersediaan model/ir.model/ir.model.data.
# - Fallback ke base_price/minimum_price jika engine pricelist/bridge belum tersedia.
#
# Smart buttons & actions:
# - Buka rules harga terkait treatment.
#
# Keamanan & audit:
# - Tracking field penting via mail.thread
# - Audit event terstruktur jika modul audit tersedia.

from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

# Opsional: gunakan mixin internal modul untuk helper pricing.
try:
    from .mixin_pricing import ClinicPricingMixin
except Exception:  # pragma: no cover - aman jika mixin belum dibuat
    class ClinicPricingMixin(object):
        """Fallback stub mixin jika mixin_pricing belum tersedia."""
        def _round_price(self, price, currency):
            return currency.round(price) if currency else price

        def _minutes_from_duration(self, duration, uom):
            return int(duration * 60) if uom == "hour" else int(duration)


class ClinicTreatment(models.Model, ClinicPricingMixin):
    _name = "clinic.treatment.catalog"
    _description = "Clinic Treatment (Service Catalog)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -----------------------------
    # Identity & Basic Info
    # -----------------------------
    name = fields.Char(
        string="Treatment Name",
        required=True,
        tracking=True,
        index=True,
        help="Nama layanan/treatment non-prosedural yang dijual sebagai service."
    )
    code = fields.Char(
        string="Code",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        help="Kode unik treatment. Diisi otomatis dari sequence saat create."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Urutan tampilan di list/kanban."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True
    )

    # -----------------------------
    # Company & Currency
    # -----------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -----------------------------
    # Classification
    # -----------------------------
    category_id = fields.Many2one(
        "clinic.treatment.category",
        string="Category",
        ondelete="restrict",
        index=True
    )
    tag_ids = fields.Many2many(
        "clinic.treatment.tag",
        "clinic_treatment_tag_rel",
        "treatment_id",
        "tag_id",
        string="Tags",
        help="Penandaan bebas untuk segmentasi & promosi."
    )

    # -----------------------------
    # Attributes & Presentation
    # -----------------------------
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    description = fields.Html(string="Description", sanitize=True)
    duration_value = fields.Float(
        string="Duration",
        default=60.0,
        help="Durasi layanan dalam menit/jam sesuai satuan."
    )
    duration_uom = fields.Selection(
        selection=[("minute", "Minute(s)"), ("hour", "Hour(s)")],
        string="Duration UoM",
        default="minute",
        required=True
    )
    duration_minutes = fields.Integer(
        string="Duration (minutes)",
        compute="_compute_duration_minutes",
        store=True
    )
    allow_online_booking = fields.Boolean(
        string="Allow Online Booking",
        default=True,
        help="Jika aktif, treatment tampil untuk pemesanan melalui portal/eCommerce (bila terpasang)."
    )

    # -----------------------------
    # Product Mapping (Service)
    # -----------------------------
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Service Product",
        domain="[('type','=','service'), ('company_id','in',[False, company_id])]",
        ondelete="set null",
        tracking=True,
        help="Produk service yang digunakan saat billing/invoicing."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Service Variant",
        domain="[('product_tmpl_id','=',product_tmpl_id)]",
        ondelete="set null",
        help="Varian service (opsional). Jika tidak diisi, sistem gunakan variant utama."
    )

    # -----------------------------
    # Pricing Baseline (Fallback)
    # -----------------------------
    base_price = fields.Monetary(
        string="Base Price",
        currency_field="currency_id",
        tracking=True,
        help="Harga dasar (fallback) bila Pricelist Engine belum tersedia."
    )
    minimum_price = fields.Monetary(
        string="Minimum Price",
        currency_field="currency_id",
        tracking=True,
        help="Batas bawah harga jual final (guardrail)."
    )
    pricing_policy = fields.Selection(
        [
            ("pricelist", "Pricelist Only"),
            ("fixed", "Fixed"),
            ("formula", "Formula (via Bridge)")
        ],
        string="Pricing Policy",
        default="pricelist",
        required=True,
        help=(
            "'Pricelist Only': gunakan Odoo Pricelist via Bridge.\n"
            "'Fixed': pakai Base Price secara langsung.\n"
            "'Formula': delegasikan ke Bridge (membership/surcharge/insurance)."
        )
    )
    surcharge_applicable = fields.Boolean(
        string="Surcharge Applicable",
        default=True,
        help="Izinkan pengenaan surcharge (level terapis/room/time, dll) via engine terpisah."
    )
    insurance_applicable = fields.Boolean(
        string="Insurance Applicable",
        default=False,
        help="Jika aktif, treatment dapat ditagihkan ke asuransi (coverage/co-pay)."
    )

    # -----------------------------
    # Availability & Validity
    # -----------------------------
    valid_from = fields.Date(string="Valid From")
    valid_to = fields.Date(string="Valid To")
    is_currently_valid = fields.Boolean(
        string="Currently Valid",
        compute="_compute_is_currently_valid",
        search="_search_is_currently_valid",
        store=False,
        help="Dynamic validity based on active status and the current date.",
    )

    # -----------------------------
    # Counters / Smart Buttons
    # -----------------------------
    pricelist_item_count = fields.Integer(
        string="Pricing Rules",
        compute="_compute_pricelist_item_count"
    )
    package_item_count = fields.Integer(
        string="In Packages",
        compute="_compute_package_item_count"
    )

    # -----------------------------
    # Constraints
    # -----------------------------
    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Code must be unique per company.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("duration_value", "duration_uom")
    def _compute_duration_minutes(self):
        for rec in self:
            rec.duration_minutes = self._minutes_from_duration(rec.duration_value, rec.duration_uom)

    @api.depends("valid_from", "valid_to", "active")
    def _compute_is_currently_valid(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active:
                rec.is_currently_valid = False
                continue
            vf_ok = (not rec.valid_from) or (rec.valid_from <= today)
            vt_ok = (not rec.valid_to) or (today <= rec.valid_to)
            rec.is_currently_valid = bool(vf_ok and vt_ok)

    @api.model
    def _search_is_currently_valid(self, operator, value):
        """Search the dynamic validity flag using stored source fields.

        The flag depends on today's date, so storing it would become stale when
        the calendar day changes. Odoo 19 normalizes Boolean comparisons to
        ``in``/``not in`` with Boolean value lists; handle those operators and
        keep the query fully SQL-searchable through ``active``, ``valid_from``
        and ``valid_to``.
        """
        if operator in ("=", "!="):
            requested_values = [value]
            operator = "in" if operator == "=" else "not in"
        elif operator in ("in", "not in"):
            requested_values = list(value) if isinstance(value, (list, tuple, set)) else [value]
        else:
            return NotImplemented

        requested = {bool(item) for item in requested_values}
        if operator == "not in":
            requested = {True, False} - requested

        if requested == {True, False}:
            return []
        if not requested:
            return [("id", "=", 0)]

        today = fields.Date.context_today(self)
        currently_valid_domain = [
            ("active", "=", True),
            "|",
            ("valid_from", "=", False),
            ("valid_from", "<=", today),
            "|",
            ("valid_to", "=", False),
            ("valid_to", ">=", today),
        ]
        currently_invalid_domain = [
            "|",
            ("active", "=", False),
            "|",
            ("valid_from", ">", today),
            ("valid_to", "<", today),
        ]
        return currently_valid_domain if True in requested else currently_invalid_domain

    def _compute_pricelist_item_count(self):
        """Hitung jumlah aturan harga yang terkait treatment ini."""
        item_model = self.env.registry.get("clinic.treatment.pricelist.item")
        if not item_model:
            for rec in self:
                rec.pricelist_item_count = 0
            return
        data = self.env["clinic.treatment.pricelist.item"]._read_group(
            [("treatment_id", "in", self.ids)],
            ["treatment_id"],
            ["__count"],
        )
        mapped = {treatment.id: count for treatment, count in data if treatment}
        for rec in self:
            rec.pricelist_item_count = mapped.get(rec.id, 0)

    def _compute_package_item_count(self):
        """Hitung berapa paket (bundle) yang memuat treatment ini."""
        bundle_line_model = self.env.registry.get("clinic.treatment.bundle.line")
        if not bundle_line_model:
            for rec in self:
                rec.package_item_count = 0
            return
        data = self.env["clinic.treatment.bundle.line"]._read_group(
            [("treatment_id", "in", self.ids)],
            ["treatment_id"],
            ["__count"],
        )
        mapped = {treatment.id: count for treatment, count in data if treatment}
        for rec in self:
            rec.package_item_count = mapped.get(rec.id, 0)

    # =========================================================================
    # ONCHANGE / CONSTRAINTS
    # =========================================================================
    @api.constrains("base_price", "minimum_price")
    def _check_prices(self):
        for rec in self:
            if rec.base_price and rec.base_price < 0.0:
                raise ValidationError(_("Base Price cannot be negative."))
            if rec.minimum_price and rec.minimum_price < 0.0:
                raise ValidationError(_("Minimum Price cannot be negative."))
            if rec.base_price and rec.minimum_price and rec.minimum_price > rec.base_price and rec.pricing_policy == "fixed":
                raise ValidationError(_("Minimum Price cannot exceed Base Price under Fixed policy."))

    @api.constrains("duration_value", "duration_uom")
    def _check_duration(self):
        for rec in self:
            if rec.duration_value <= 0.0:
                raise ValidationError(_("Duration must be greater than zero."))

    @api.onchange("product_tmpl_id")
    def _onchange_product_tmpl_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.product_tmpl_id.type != "service":
                rec.product_tmpl_id = False
                return {
                    "warning": {
                        "title": _("Invalid Product Type"),
                        "message": _("Please choose a Service type product for Treatment billing.")
                    }
                }
            # reset product_id if template changed
            rec.product_id = False

    # =========================================================================
    # ORM OVERRIDES
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_code", raise_if_not_found=False)
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("code") and seq:
                # Ambil kode dari sequence; gunakan company context agar per-company
                vals["code"] = seq._next()
            # Auto-fill base product template jika belum ada (opsional)
            if not vals.get("product_tmpl_id"):
                tmpl_vals = self._prepare_product_template_vals(vals)
                if tmpl_vals:
                    product_tmpl = self.env["product.template"].create(tmpl_vals)
                    vals["product_tmpl_id"] = product_tmpl.id
        records = super().create(vals_list)
        # Audit event (opsional)
        records._audit_event("create")
        return records

    def write(self, vals):
        res = super().write(vals)
        # Audit event pada perubahan field penting
        tracked = {"name", "category_id", "base_price", "pricing_policy", "minimum_price", "product_tmpl_id", "valid_from", "valid_to", "active"}
        if set(vals).intersection(tracked):
            self._audit_event("write", changed_fields=list(set(vals).intersection(tracked)))
        return res

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("%s (copy)") % (self.name,))
        default.setdefault("code", False)  # regenerate by sequence
        return super().copy(default)

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _prepare_product_template_vals(self, incoming_vals=None):
        """Siapkan product.template tipe service sebagai default mapping.
        Tidak membuat jika name kosong (edge install demo).
        """
        vals = incoming_vals or {}
        name = vals.get("name") or self.name
        company_id = vals.get("company_id") or self.company_id.id or self.env.company.id
        currency = self.env["res.company"].browse(company_id).currency_id
        if not name:
            return {}
        # Gunakan base_price sebagai list_price awal (jika ada)
        list_price = vals.get("base_price", 0.0)
        product_vals = {
            "name": name,
            "type": "service",
            "company_id": company_id,
            "list_price": list_price,
            "uom_id": self.env.ref("uom.product_uom_unit").id,
            "sale_ok": True,
            "purchase_ok": False,
            "taxes_id": [],
        }
        # invoice_policy is supplied by the optional Sale extension in Odoo 19.
        # Preserve the original intent only when that field is available.
        if "invoice_policy" in self.env["product.template"]._fields:
            product_vals["invoice_policy"] = "delivery"
        return product_vals

    def _audit_event(self, action, changed_fields=None):
        """Log event audit jika model audit tersedia, selalu message_post sebagai fallback."""
        # Fallback chatter
        self.message_post(body=_("Treatment %s: %s") % (action, ", ".join(changed_fields or [])))
        # Optional: clinic.audit.event
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "treatment.%s" % action,
                    "model": self._name,
                    "res_id": rec.id,
                    "company_id": rec.company_id.id,
                    "payload": {
                        "changed_fields": changed_fields or [],
                        "user_id": self.env.user.id,
                    },
                })
            except Exception as e:  # pragma: no cover
                _logger.debug("Audit event skipped: %s", e)

    # =========================================================================
    # PUBLIC API — Dipakai modul lain
    # =========================================================================
    def get_service_product(self):
        """Kembalikan product.product untuk billing.
        Urutan: product_id (varian) → variant utama dari product_tmpl_id → None.
        """
        self.ensure_one()
        if self.product_id:
            return self.product_id
        if self.product_tmpl_id:
            # Ambil variant utama/pertama
            variant = self.product_tmpl_id.product_variant_id or self.product_tmpl_id.product_variant_ids[:1]
            return variant or self.env["product.product"]
        return self.env["product.product"]

    def get_default_price(self):
        """Harga default untuk tampilan awal jika Pricelist Engine belum ada."""
        self.ensure_one()
        return self.base_price or 0.0

    def get_minimum_price(self):
        self.ensure_one()
        return self.minimum_price or 0.0

    # def action_price_preview(self, partner_id=None, pricelist_id=None, quantity=1.0, booking_dt=None, context_tags=None):
    #     """Hitung preview harga final treatment ini.
    #     - Jika bridge tersedia → delegasi (membership/surcharge/insurance/promo).
    #     - Jika tidak → fallback sesuai pricing_policy.
    #     Return dict: { 'price': float, 'currency_id': id, 'explanation': str }
    #     """
    #     self.ensure_one()
    #     currency = self.currency_id
    #     expl = []
    #     # Bridge available?
    #     bridge_model = self.env.registry.get("clinic.pricelist.bridge")
    #     if bridge_model:
    #         try:
    #             res = self.env["clinic.pricelist.bridge"].sudo().compute_treatment_price(
    #                 treatment=self,
    #                 partner_id=partner_id,
    #                 pricelist_id=pricelist_id,
    #                 quantity=quantity,
    #                 booking_dt=booking_dt,
    #                 context_tags=context_tags or [],
    #             )
    #             # Guardrail minimum
    #             price = max(res.get("price", 0.0), self.get_minimum_price())
    #             res["price"] = self._round_price(price, currency)
    #             return res
    #         except Exception as e:  # pragma: no cover
    #             _logger.warning("Bridge pricing failed, fallback to local: %s", e)
    #             expl.append(_("Bridge error, local fallback applied."))

    #     # Fallback logic
    #     policy = self.pricing_policy
    #     price = 0.0
    #     if policy == "fixed":
    #         price = self.base_price or 0.0
    #         expl.append(_("Fixed policy using Base Price."))
    #     elif policy == "pricelist":
    #         # Jika ada product & pricelist → gunakan algoritma Odoo Pricelist standar
    #         price = self._pricelist_fallback(product=self.get_service_product(), pricelist_id=pricelist_id, qty=quantity) \
    #             if (pricelist_id and self.get_service_product().id) else (self.base_price or 0.0)
    #         expl.append(_("Pricelist policy using Odoo standard or Base Price fallback."))
    #     elif policy == "formula":
    #         # Tanpa bridge, formula tidak ada → pakai base_price
    #         price = self.base_price or 0.0
    #         expl.append(_("Formula policy requires Bridge; Base Price used."))

    #     price = max(price, self.get_minimum_price())
    #     return {
    #         "price": self._round_price(price, currency),
    #         "currency_id": currency.id if currency else False,
    #         "explanation": " ".join(expl)
    #     }

    def _pricelist_fallback(self, product, pricelist_id, qty=1.0):
        """Gunakan mekanisme Pricelist Odoo standar pada product jika memungkinkan."""
        if not product or not pricelist_id:
            return self.base_price or 0.0
        pl = self.env["product.pricelist"].browse(pricelist_id)
        if not pl.exists():
            return self.base_price or 0.0
        # Odoo 19 standard product.pricelist fallback
        return float(
            pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=False)
        )

    # =========================================================================
    # ACTIONS / SMART BUTTONS
    # =========================================================================
    def action_open_pricelist_items(self):
        """Smart button ke aturan harga treatment ini."""
        self.ensure_one()
        action = self.env.ref("clinic_treatment_catalog.action_treatment_pricelist_item", raise_if_not_found=False)
        if not action:
            # fallback generic action tree view
            return {
                "type": "ir.actions.act_window",
                "name": _("Pricing Rules"),
                "res_model": "clinic.treatment.pricelist.item",
                "view_mode": "list,form",
                "domain": [("treatment_id", "=", self.id)],
                "context": {"default_treatment_id": self.id},
            }
        res = action.read()[0]
        res.setdefault("domain", [])
        res["domain"] = tools.safe_eval(res["domain"]) if isinstance(res["domain"], str) else res["domain"]
        res["domain"].append(("treatment_id", "=", self.id))
        res.setdefault("context", {})
        ctx = res["context"]
        if isinstance(ctx, str):
            ctx = tools.safe_eval(ctx)
        ctx.update({"default_treatment_id": self.id})
        res["context"] = ctx
        return res

    # =========================================================================
    # NAME GET / SEARCH
    # =========================================================================
    def _clinic_display_label(self):
        self.ensure_one()
        return "[%s] %s" % (self.code, self.name) if self.code else self.name

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec._clinic_display_label()) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        criteria = ["|", ("code", operator, name), ("name", operator, name)] if name else []
        recs = self.search(criteria + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

    # =========================================================================
    # BOOKING / ENCOUNTER HOOKS (opsional, dipakai modul lain)
    # =========================================================================
    # def prepare_booking_line_vals(self, partner_id=None, pricelist_id=None, quantity=1.0, booking_dt=None, context_tags=None):
    #     """Kembalikan dictionary siap create untuk line booking (clinic_booking)
    #     dengan estimasi harga."""
    #     self.ensure_one()
    #     price_info = self.action_price_preview(
    #         partner_id=partner_id,
    #         pricelist_id=pricelist_id,
    #         quantity=quantity,
    #         booking_dt=booking_dt,
    #         context_tags=context_tags or []
    #     )
    #     product = self.get_service_product()
    #     return {
    #         "treatment_id": self.id,
    #         "name": self.name,
    #         "product_id": product.id or False,
    #         "duration_minutes": self.duration_minutes,
    #         "price_unit": price_info.get("price", 0.0),
    #         "currency_id": self.currency_id.id,
    #         "company_id": self.company_id.id,
    #     }

    def prepare_invoice_line_vals(self, partner_id=None, quantity=1.0, analytic_tags=None, taxes=None):
        """Siapkan vals invoice line untuk clinic_billing/AR.
        Harga final sebaiknya dihitung sebelumnya di stage encounter.
        """
        self.ensure_one()
        product = self.get_service_product()
        name = "%s" % (self.name,)
        return {
            "name": name,
            "product_id": product.id or False,
            "quantity": quantity,
            "price_unit": self.get_default_price(),
            "analytic_tag_ids": [(6, 0, analytic_tags or [])],
            "tax_ids": [(6, 0, taxes or [])],
        }

