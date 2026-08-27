# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_bundle.py
#
# Models:
#   - clinic.treatment.bundle        : master paket/bundle treatment (produk layanan paket)
#   - clinic.treatment.bundle.line   : item treatment di dalam bundle
#
# Integrations (soft-coupled):
#   - product.template/product.product    (penjualan paket sebagai service)
#   - product.pricelist                   (preview harga via mekanisme Odoo)
#   - clinic.pricelist.bridge             (engine harga final: membership/surcharge/insurance/promo)
#   - booking.booking / clinic.encounter   (estimasi/real cost, redeem kuota - di modul lain)
#   - clinic.billing                      (penagihan paket, co-pay/insurer - di modul lain)
#   - clinic.audit.event                  (audit event terstruktur - opsional)
#
# Guardrails:
#   - Tanpa bridge, fallback ke base/fixed/sum.
#   - Constraint durasi & kuota.
#   - Arahkan delete → archive jika sudah dipakai (opsional).
#
from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

# Opsional: gunakan mixin internal untuk helper pricing/rounding.
try:
    from .mixin_pricing import ClinicPricingMixin
except Exception:  # pragma: no cover (fallback aman)
    class ClinicPricingMixin(object):
        def _round_price(self, price, currency):
            return currency.round(price) if currency else price


# =============================================================================
# BUNDLE HEADER
# =============================================================================
class ClinicTreatmentBundle(models.Model, ClinicPricingMixin):
    _name = "clinic.treatment.bundle"
    _description = "Clinic Treatment Bundle"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -----------------------------
    # Identity
    # -----------------------------
    name = fields.Char(
        string="Bundle Name",
        required=True,
        tracking=True,
        index=True,
        help="Nama paket/bundel treatment."
    )
    code = fields.Char(
        string="Code",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        help="Kode unik paket. Diisi otomatis dari sequence saat create."
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True, tracking=True)

    # -----------------------------
    # Company & Currency
    # -----------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
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
    # Presentation
    # -----------------------------
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    description = fields.Html(string="Description", sanitize=True)
    allow_online_sale = fields.Boolean(
        string="Allow Online Sale",
        default=True,
        help="Jika aktif, paket dapat ditampilkan/dibeli via portal/eCommerce (bila terpasang)."
    )

    # -----------------------------
    # Product Mapping (Service Package)
    # -----------------------------
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Service Product",
        domain="[('type','=','service'), ('company_id','in',[False, company_id])]",
        ondelete="set null",
        tracking=True,
        help="Produk service untuk menjual paket ini."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Service Variant",
        domain="[('product_tmpl_id','=',product_tmpl_id)]",
        ondelete="set null",
        help="Varian service (opsional). Jika kosong, gunakan varian utama."
    )

    # -----------------------------
    # Validity
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
    # Pricing
    # -----------------------------
    pricing_policy = fields.Selection(
        [
            ("fixed", "Fixed"),
            ("sum", "Sum of Lines"),
            ("formula", "Formula (via Bridge)"),
        ],
        string="Pricing Policy",
        default="fixed",
        required=True,
        help=(
            "'Fixed': gunakan Base Price.\n"
            "'Sum of Lines': jumlah dari line price (override/treatment base) x qty.\n"
            "'Formula': delegasi ke Bridge (membership/surcharge/insurance/promo)."
        )
    )
    base_price = fields.Monetary(
        string="Base Price",
        currency_field="currency_id",
        tracking=True,
        help="Harga paket (Fixed) atau fallback bila Bridge tidak tersedia."
    )
    minimum_price = fields.Monetary(
        string="Minimum Price",
        currency_field="currency_id",
        tracking=True,
        help="Batas bawah harga jual final paket."
    )
    computed_sum_price = fields.Monetary(
        string="Computed (Sum of Lines)",
        currency_field="currency_id",
        compute="_compute_computed_sum_price",
        store=False,
        help="Nilai kalkulasi berdasarkan isi line ketika kebijakan 'Sum of Lines'."
    )

    # -----------------------------
    # Lines & Counters
    # -----------------------------
    line_ids = fields.One2many(
        "clinic.treatment.bundle.line",
        "bundle_id",
        string="Bundle Items"
    )
    line_count = fields.Integer(string="Lines", compute="_compute_counters")
    treatment_count = fields.Integer(string="Treatments", compute="_compute_counters")
    total_sessions = fields.Integer(
        string="Total Sessions",
        compute="_compute_counters",
        help="Total kuota sesi/entitlement seluruh item bundle."
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

    def _compute_counters(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.treatment_count = len(rec.line_ids.mapped("treatment_id"))
            rec.total_sessions = int(sum(rec.line_ids.mapped("quantity") or [0]))

    def _compute_computed_sum_price(self):
        for rec in self:
            total = 0.0
            for line in rec.line_ids:
                total += line._effective_unit_price() * (line.quantity or 0.0)
            rec.computed_sum_price = self._round_price(total, rec.currency_id)

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
            if rec.pricing_policy == "fixed" and rec.base_price and rec.minimum_price and rec.minimum_price > rec.base_price:
                raise ValidationError(_("Minimum Price cannot exceed Base Price under Fixed policy."))

    @api.constrains("valid_from", "valid_to")
    def _check_validity_range(self):
        for rec in self:
            if rec.valid_from and rec.valid_to and rec.valid_from > rec.valid_to:
                raise ValidationError(_("Valid From cannot be greater than Valid To."))

    @api.onchange("product_tmpl_id")
    def _onchange_product_tmpl_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.product_tmpl_id.type != "service":
                rec.product_tmpl_id = False
                return {
                    "warning": {
                        "title": _("Invalid Product Type"),
                        "message": _("Please choose a Service type product for selling this Bundle.")
                    }
                }
            rec.product_id = False

    # =========================================================================
    # ORM OVERRIDES
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_bundle_code", raise_if_not_found=False)
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("code") and seq:
                vals["code"] = seq._next()
            # Auto product template jika tidak diisi
            if not vals.get("product_tmpl_id"):
                tmpl_vals = self._prepare_product_template_vals(vals)
                if tmpl_vals:
                    product_tmpl = self.env["product.template"].create(tmpl_vals)
                    vals["product_tmpl_id"] = product_tmpl.id
        recs = super().create(vals_list)
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        tracked = {"name", "base_price", "minimum_price", "pricing_policy", "valid_from", "valid_to", "product_tmpl_id", "active"}
        if set(vals).intersection(tracked):
            self._audit_event("write", changed_fields=list(set(vals).intersection(tracked)))
        return res

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("%s (copy)") % (self.name,))
        default.setdefault("code", False)
        return super().copy(default)

    # =========================================================================
    # HELPERS / PUBLIC API
    # =========================================================================
    def _prepare_product_template_vals(self, incoming_vals=None):
        """Siapkan product.template tipe service untuk paket."""
        vals = incoming_vals or {}
        name = vals.get("name") or self.name
        company_id = vals.get("company_id") or self.company_id.id or self.env.company.id
        if not name:
            return {}
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
        if "invoice_policy" in self.env["product.template"]._fields:
            product_vals["invoice_policy"] = "order"
        return product_vals

    def _audit_event(self, action, changed_fields=None):
        """Audit ke clinic.audit.event bila ada; fallback message_post."""
        self.message_post(body=_("Bundle %s: %s") % (action, ", ".join(changed_fields or [])))
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "bundle.%s" % action,
                    "model": rec._name,
                    "res_id": rec.id,
                    "company_id": rec.company_id.id,
                    "payload": {
                        "changed_fields": changed_fields or [],
                        "user_id": self.env.user.id,
                    },
                })
            except Exception as e:  # pragma: no cover
                _logger.debug("Audit event skipped: %s", e)

    def get_service_product(self):
        """Kembalikan product.product untuk penjualan paket."""
        self.ensure_one()
        if self.product_id:
            return self.product_id
        if self.product_tmpl_id:
            return self.product_tmpl_id.product_variant_id or self.product_tmpl_id.product_variant_ids[:1]
        return self.env["product.product"]

    def action_price_preview(self, partner_id=None, pricelist_id=None, quantity=1.0, sale_dt=None, context_tags=None):
        """Preview harga jual paket.
        - Bridge tersedia → delegasi ke compute_bundle_price
        - Tanpa bridge → Fixed / Sum fallback
        """
        self.ensure_one()
        currency = self.currency_id
        expl = []
        # Bridge
        bridge_model = self.env.registry.get("clinic.pricelist.bridge")
        if bridge_model:
            try:
                res = self.env["clinic.pricelist.bridge"].sudo().compute_bundle_price(
                    bundle=self,
                    partner_id=partner_id,
                    pricelist_id=pricelist_id,
                    quantity=quantity,
                    sale_dt=sale_dt,
                    context_tags=context_tags or [],
                )
                price = max(res.get("price", 0.0), float(self.minimum_price or 0.0))
                res["price"] = self._round_price(price, currency)
                return res
            except Exception as e:  # pragma: no cover
                _logger.warning("Bridge bundle pricing failed, fallback to local: %s", e)
                expl.append(_("Bridge error, local fallback applied."))

        # Fallback
        policy = self.pricing_policy
        price = 0.0
        if policy == "fixed":
            price = float(self.base_price or 0.0)
            expl.append(_("Fixed policy using Base Price."))
        elif policy == "sum":
            price = float(self.computed_sum_price or 0.0)
            expl.append(_("Sum of Lines policy (override/base × qty)."))
        elif policy == "formula":
            price = float(self.base_price or 0.0)
            expl.append(_("Formula policy requires Bridge; Base Price used."))

        # Pricelist standar Odoo kalau ada product + pricelist
        if pricelist_id and self.get_service_product().id:
            try:
                pl = self.env["product.pricelist"].browse(pricelist_id)
                service_product = self.get_service_product()
                price = float(
                    pl._get_product_price(
                        service_product, quantity or 1.0, uom=service_product.uom_id, date=False
                    )
                )
                expl.append(_("Odoo Pricelist applied."))
            except Exception as e:  # pragma: no cover
                _logger.debug("Pricelist fallback skipped: %s", e)

        price = max(price, float(self.minimum_price or 0.0))
        return {
            "price": self._round_price(price, currency),
            "currency_id": currency.id if currency else False,
            "explanation": " ".join(expl),
        }

    def prepare_sale_line_vals(self, partner_id=None, quantity=1.0, analytic_tags=None, taxes=None):
        """Siapkan vals untuk penjualan paket (SO/invoice) secara standar."""
        self.ensure_one()
        product = self.get_service_product()
        return {
            "name": self.name,
            "product_id": product.id or False,
            "product_uom_qty": quantity,
            "price_unit": self.base_price or 0.0,
            "analytic_tag_ids": [(6, 0, analytic_tags or [])],
            "tax_id": [(6, 0, taxes or [])],
        }

    # =========================================================================
    # ACTIONS (Smart Buttons)
    # =========================================================================
    def action_open_treatments(self):
        """Buka daftar treatment yang menjadi anggota bundle ini."""
        self.ensure_one()
        action = self.env.ref("clinic_treatment_catalog.action_treatment_tree", raise_if_not_found=False)
        domain = [("id", "in", self.line_ids.mapped("treatment_id").ids)]
        name = _("Treatments in Bundle: %s") % self.name
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
        return [(rec.id, rec._clinic_display_label()) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        criteria = ["|", ("code", operator, name), ("name", operator, name)] if name else []
        recs = self.search(criteria + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# =============================================================================
# BUNDLE LINE
# =============================================================================
class ClinicTreatmentBundleLine(models.Model, ClinicPricingMixin):
    _name = "clinic.treatment.bundle.line"
    _description = "Clinic Treatment Bundle Line"
    _order = "bundle_id, sequence, id"
    _check_company_auto = True

    # -----------------------------
    # Linkage
    # -----------------------------
    bundle_id = fields.Many2one(
        "clinic.treatment.bundle",
        string="Bundle",
        required=True,
        ondelete="cascade",
        index=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="bundle_id.company_id",
        store=True,
        readonly=True
    )

    # -----------------------------
    # Item (Specific or Category-based)
    # -----------------------------
    line_type = fields.Selection(
        selection=[("treatment", "Specific Treatment"), ("category", "Category Scope")],
        string="Line Type",
        default="treatment",
        required=True,
        help="Specific Treatment: pilih treatment tertentu.\nCategory Scope: izinkan substitusi treatment dalam kategori/tag tertentu."
    )
    treatment_id = fields.Many2one(
        "clinic.treatment.catalog",
        string="Treatment",
        ondelete="restrict",
        domain="[('company_id','in',[False, company_id])]",
        help="Diisi jika Line Type = Specific Treatment."
    )
    category_id = fields.Many2one(
        "clinic.treatment.category",
        string="Category",
        ondelete="restrict",
        help="Diisi jika Line Type = Category Scope (opsional)."
    )
    tag_ids = fields.Many2many(
        "clinic.treatment.tag",
        "clinic_bundle_line_tag_rel",
        "line_id",
        "tag_id",
        string="Allowed Tags",
        help="Bila diisi, hanya treatment dengan tag ini yang dapat disubstitusi saat redeem."
    )

    sequence = fields.Integer(string="Sequence", default=10)
    notes = fields.Char(string="Notes")

    # -----------------------------
    # Quota / Sessions / Limits
    # -----------------------------
    quantity = fields.Integer(
        string="Included Sessions",
        default=1,
        required=True,
        help="Jumlah sesi/kuota yang termasuk dalam bundle untuk item ini."
    )
    per_visit_limit = fields.Integer(
        string="Max Redeem per Visit",
        default=0,
        help="Batas maksimum redeem per kunjungan (0 = tidak dibatasi)."
    )
    allow_overage = fields.Boolean(
        string="Allow Overage (Add-on Price)",
        default=True,
        help="Jika kuota habis, boleh redeem dengan harga add-on per unit."
    )
    overage_unit_price = fields.Monetary(
        string="Overage Unit Price",
        currency_field="currency_id",
        help="Harga per unit jika redeem melebihi kuota (add-on)."
    )

    # -----------------------------
    # Pricing per Line (for Sum Policy)
    # -----------------------------
    price_policy = fields.Selection(
        selection=[
            ("treatment_base", "Use Treatment Base Price"),
            ("override", "Override Unit Price"),
            ("zero", "Included (0)"),
        ],
        string="Line Price Policy",
        default="zero",
        required=True,
        help="Harga yang dipakai saat kebijakan bundle = 'Sum of Lines'."
    )
    unit_price = fields.Monetary(
        string="Override Unit Price",
        currency_field="currency_id",
        help="Wajib diisi bila Price Policy = Override."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="bundle_id.currency_id",
        store=True,
        readonly=True
    )

    # -----------------------------
    # Derived / Info
    # -----------------------------
    effective_unit_price = fields.Monetary(
        string="Effective Unit Price",
        currency_field="currency_id",
        compute="_compute_effective_unit_price",
        store=False,
        help="Harga unit efektif menurut kebijakan line."
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_subtotal",
        store=False
    )

    # -----------------------------
    # Constraints
    # -----------------------------
    @api.constrains("quantity")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_("Included Sessions must be greater than zero."))

    @api.constrains("price_policy", "unit_price")
    def _check_price_policy(self):
        for rec in self:
            if rec.price_policy == "override" and (rec.unit_price is None or rec.unit_price < 0.0):
                raise ValidationError(_("Override Unit Price must be set and non-negative."))

    @api.constrains("line_type", "treatment_id", "category_id")
    def _check_line_type_fields(self):
        for rec in self:
            if rec.line_type == "treatment" and not rec.treatment_id:
                raise ValidationError(_("Treatment must be set for 'Specific Treatment' line."))
            if rec.line_type == "category" and not (rec.category_id or rec.tag_ids):
                # minimal salah satu disediakan untuk scoping
                raise ValidationError(_("For 'Category Scope' line, set at least Category or Allowed Tags."))

    # =========================================================================
    # COMPUTES
    # =========================================================================
    def _compute_effective_unit_price(self):
        for rec in self:
            rec.effective_unit_price = rec._effective_unit_price()

    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec._effective_unit_price() * (rec.quantity or 0.0)

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _effective_unit_price(self):
        """Hitung harga unit efektif untuk kebijakan Sum of Lines."""
        self.ensure_one()
        policy = self.price_policy
        if policy == "zero":
            return 0.0
        if policy == "override":
            return float(self.unit_price or 0.0)
        # treatment_base
        if self.treatment_id:
            try:
                return float(self.treatment_id.get_default_price())
            except Exception:  # pragma: no cover
                return 0.0
        # Untuk line category (tanpa treatment spesifik), anggap 0 di kalkulasi Sum
        return 0.0

    # =========================================================================
    # NAME GET
    # =========================================================================
    def _clinic_display_label(self):
        self.ensure_one()
        if self.line_type == "treatment" and self.treatment_id:
            return "%s × %s" % (self.treatment_id.name, self.quantity)
        parts = []
        if self.category_id:
            parts.append(_("Category: %s") % self.category_id.complete_name)
        if self.tag_ids:
            parts.append(_("Tags: %s") % ", ".join(self.tag_ids.mapped("name")))
        return "%s × %s" % ("; ".join(parts) if parts else _("Scoped"), self.quantity)

    @api.depends("line_type", "treatment_id.name", "category_id.complete_name", "tag_ids.name", "quantity")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        return [(rec.id, rec._clinic_display_label()) for rec in self]

