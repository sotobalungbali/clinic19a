# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_pricelist_item.py
#
# Model: clinic.treatment.pricelist.item
# - Price rule untuk treatment: scope per treatment / category / tag / global.
# - Filter kontekstual: channel, kuantitas, tanggal, time-window, partner category, include/exclude tags.
# - Metode harga: fixed, percent, amount_off, surcharge, markup, formula (delegasi bridge).
# - Basis harga: treatment base price / Odoo product.pricelist (via header).
#
# Integrasi (soft-coupled):
# - clinic.treatment.pricelist   (header)
# - clinic.treatment.catalog     (target)
# - clinic.treatment.category    (scoping)
# - clinic.treatment.tag         (scoping)
# - product.pricelist            (via header untuk fallback)
# - clinic.pricelist.bridge      (opsional; engine pusat)
# - clinic.audit.event           (opsional; audit log)
#
from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, time

_logger = logging.getLogger(__name__)


# Helper kecil untuk rounding konsisten
def _round_price(price, currency, policy="currency"):
    """Pembulatan harga sesuai kebijakan.
    policy: currency | half_up | down | up
    """
    if not currency:
        return price
    if policy == "currency":
        return currency.round(price)
    # manual rounding
    if policy == "half_up":
        # 0.5 ke atas dibulatkan naik
        return float(int(price + (0.5 if price >= 0 else -0.5)))
    if policy == "down":
        return float(int(price)) if price >= 0 else float(int(price) - (1 if price != int(price) else 0))
    if policy == "up":
        return float(int(price) + (0 if price == int(price) else 1)) if price >= 0 else float(int(price))
    return currency.round(price)


class ClinicTreatmentPricelistItem(models.Model):
    _name = "clinic.treatment.pricelist.item"
    _description = "Clinic Treatment Pricelist Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, specificity DESC, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Base
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Rule Name",
        required=True,
        tracking=True,
        help="Nama aturan harga untuk memudahkan identifikasi."
    )
    code = fields.Char(
        string="Code",
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help="Kode unik rule (otomatis dari sequence bila tersedia)."
    )
    active = fields.Boolean(string="Active", default=True, tracking=True)
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Urutan eksekusi rule (lebih kecil = lebih dulu)."
    )

    pricelist_id = fields.Many2one(
        "clinic.treatment.pricelist",
        string="Clinic Pricelist",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="pricelist_id.company_id",
        store=True,
        readonly=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # Target Scope
    # -------------------------------------------------------------------------
    scope = fields.Selection(
        selection=[
            ("treatment", "Specific Treatment"),
            ("category", "Category (child_of)"),
            ("tag", "Tag (any match)"),
            ("all", "All Treatments"),
        ],
        string="Target Scope",
        default="all",
        required=True
    )
    treatment_id = fields.Many2one(
        "clinic.treatment.catalog",
        string="Treatment",
        ondelete="cascade",
        domain="[('company_id','in',[False, company_id])]",
        help="Wajib jika Scope = Specific Treatment."
    )
    category_id = fields.Many2one(
        "clinic.treatment.category",
        string="Category",
        ondelete="restrict",
        help="Wajib jika Scope = Category; berlaku termasuk sub-kategori (child_of)."
    )
    tag_ids = fields.Many2many(
        "clinic.treatment.tag",
        "clinic_price_item_tag_rel",
        "item_id",
        "tag_id",
        string="Include Tags",
        help="Jika Scope = Tag, rule berlaku jika treatment punya salah satu tag ini."
    )
    exclude_tag_ids = fields.Many2many(
        "clinic.treatment.tag",
        "clinic_price_item_tag_excl_rel",
        "item_id",
        "tag_id",
        string="Exclude Tags",
        help="Jika diisi, rule tidak berlaku untuk treatment yang memiliki tag-tag ini."
    )

    # Specificity score untuk sorting (treatment > category > tag > all)
    specificity = fields.Integer(
        string="Specificity",
        compute="_compute_specificity",
        store=True
    )

    # -------------------------------------------------------------------------
    # Context Filters
    # -------------------------------------------------------------------------
    channel = fields.Selection(
        selection=[
            ("inherit", "Inherit from Header"),
            ("all", "All Channels"),
            ("backoffice", "Back-office"),
            ("booking", "Booking/Frontdesk"),
            ("ecommerce", "eCommerce/Portal"),
            ("api", "API/3rd party"),
        ],
        string="Channel",
        default="inherit",
        required=True,
        help="Filter channel; jika 'Inherit', gunakan channel dari header pricelist."
    )
    min_qty = fields.Float(
        string="Min Quantity",
        default=0.0,
        help="Kuantitas minimum agar rule berlaku (0 = tanpa batas)."
    )
    max_qty = fields.Float(
        string="Max Quantity",
        default=0.0,
        help="Kuantitas maksimum agar rule berlaku (0 = tanpa batas)."
    )
    min_amount = fields.Monetary(
        string="Min Amount",
        currency_field="currency_id",
        help="Nilai minimum subtotal agar rule berlaku (opsional)."
    )
    partner_category_ids = fields.Many2many(
        "res.partner.category",
        "clinic_price_item_partner_cat_rel",
        "item_id",
        "category_id",
        string="Partner Categories",
        help="Jika diisi, rule hanya berlaku untuk pelanggan dengan kategori ini."
    )

    valid_from = fields.Date(string="Valid From")
    valid_to = fields.Date(string="Valid To")
    time_from = fields.Float(
        string="Time Window From",
        help="Jam mulai (0–24) untuk menerapkan rule (opsional)."
    )
    time_to = fields.Float(
        string="Time Window To",
        help="Jam akhir (0–24) untuk menerapkan rule (opsional)."
    )
    weekdays_only = fields.Boolean(string="Weekdays Only")
    weekend_only = fields.Boolean(string="Weekend Only")

    # -------------------------------------------------------------------------
    # Pricing Method
    # -------------------------------------------------------------------------
    base = fields.Selection(
        selection=[
            ("treatment_base", "Treatment Base Price"),
            ("pricelist", "Odoo Pricelist (Header Link)"),
        ],
        string="Base Price Source",
        default="pricelist",
        required=True,
        help="Sumber harga awal sebelum metode rule diterapkan."
    )
    method = fields.Selection(
        selection=[
            ("fixed", "Fixed Price"),
            ("percent", "Percent Discount"),
            ("amount_off", "Amount Off"),
            ("surcharge", "Surcharge"),
            ("markup", "Markup (%)"),
            ("formula", "Formula (via Bridge)"),
        ],
        string="Method",
        default="percent",
        required=True
    )
    fixed_price = fields.Monetary(string="Fixed Price", currency_field="currency_id")
    percent = fields.Float(
        string="Percent (%)",
        help="Diskon dalam persen; 10 berarti 10% lebih murah (price * (1 - 0.10))."
    )
    amount_off = fields.Monetary(
        string="Amount Off",
        currency_field="currency_id",
        help="Kurangi harga dengan nominal tertentu."
    )
    surcharge = fields.Monetary(
        string="Surcharge",
        currency_field="currency_id",
        help="Tambahan biaya nominal."
    )
    markup_percent = fields.Float(
        string="Markup (%)",
        help="Tambah harga sebesar persentase dari base (e.g. 20 = +20%)."
    )

    rounding_policy = fields.Selection(
        selection=[
            ("inherit", "Inherit from Header"),
            ("currency", "Currency Rounding"),
            ("half_up", "Half Up (0.5→1)"),
            ("down", "Round Down"),
            ("up", "Round Up"),
        ],
        string="Rounding Policy",
        default="inherit",
        required=True
    )
    enforce_minimum_price = fields.Boolean(
        string="Enforce Treatment Minimum Price",
        default=True
    )

    # -------------------------------------------------------------------------
    # Convenience / Counters
    # -------------------------------------------------------------------------
    treatment_count = fields.Integer(
        string="Approx. Treatment Coverage",
        compute="_compute_treatment_count",
        help="Perkiraan jumlah treatment yang tercakup oleh rule (untuk Scope ≠ Treatment)."
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS / COMPUTES
    # -------------------------------------------------------------------------
    @api.constrains("scope", "treatment_id", "category_id", "tag_ids")
    def _check_scope_required_fields(self):
        for rec in self:
            if rec.scope == "treatment" and not rec.treatment_id:
                raise ValidationError(_("Treatment is required when Scope is 'Specific Treatment'."))
            if rec.scope == "category" and not rec.category_id:
                raise ValidationError(_("Category is required when Scope is 'Category'."))
            if rec.scope == "tag" and not rec.tag_ids:
                raise ValidationError(_("At least one Tag is required when Scope is 'Tag'."))

    @api.constrains("time_from", "time_to", "weekdays_only", "weekend_only")
    def _check_time_window(self):
        for rec in self:
            if rec.time_from and (rec.time_from < 0 or rec.time_from > 24):
                raise ValidationError(_("Time From must be between 0 and 24."))
            if rec.time_to and (rec.time_to < 0 or rec.time_to > 24):
                raise ValidationError(_("Time To must be between 0 and 24."))
            if rec.time_from and rec.time_to and rec.time_from >= rec.time_to:
                raise ValidationError(_("Time From must be strictly less than Time To."))
            if rec.weekdays_only and rec.weekend_only:
                raise ValidationError(_("Weekdays Only and Weekend Only cannot both be enabled."))

    @api.depends("scope", "treatment_id", "category_id", "tag_ids")
    def _compute_specificity(self):
        # Lebih spesifik = skor lebih tinggi
        for rec in self:
            if rec.scope == "treatment":
                rec.specificity = 100
            elif rec.scope == "category":
                rec.specificity = 70
            elif rec.scope == "tag":
                rec.specificity = 40
            else:
                rec.specificity = 10

    def _compute_treatment_count(self):
        Treatment = self.env["clinic.treatment.catalog"]
        for rec in self:
            if rec.scope == "treatment" and rec.treatment_id:
                rec.treatment_count = 1
            elif rec.scope == "category" and rec.category_id:
                rec.treatment_count = Treatment.search_count([("category_id", "child_of", rec.category_id.id)])
            elif rec.scope == "tag" and rec.tag_ids:
                rec.treatment_count = Treatment.search_count([("tag_ids", "in", rec.tag_ids.ids)])
            else:
                rec.treatment_count = Treatment.search_count([])

    # -------------------------------------------------------------------------
    # ORM OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_pricelist_item_code", raise_if_not_found=False)
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = _("Unnamed Rule")
            if seq and not vals.get("code"):
                vals["code"] = seq._next()
        recs = super().create(vals_list)
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        tracked = set(vals.keys())
        if tracked:
            self._audit_event("write", changed_fields=list(tracked))
        return res

    # -------------------------------------------------------------------------
    # AUDIT
    # -------------------------------------------------------------------------
    def _audit_event(self, action, **kwargs):
        """Catat event ke clinic.audit.event (jika ada), fallback ke log."""
        Audit = self.env.registry.get("clinic.audit.event") and self.env["clinic.audit.event"] or None
        payload = {
            "model": self._name,
            "res_ids": self.ids,
            "action": action,
            "details": kwargs or {},
        }
        if Audit:
            try:
                for rec in self:
                    Audit.create({
                        "name": "%s %s" % (rec._name, action),
                        "model": rec._name,
                        "res_id": rec.id,
                        "payload_json": tools.json.dumps(payload, ensure_ascii=False),
                    })
            except Exception as e:
                _logger.debug("Audit log failed: %s", e)
        else:
            _logger.info("AUDIT[%s]: %s", action, payload)

    # -------------------------------------------------------------------------
    # PUBLIC API — EVALUATION
    # -------------------------------------------------------------------------
    def evaluate_rule(
        self, treatment, partner_id=None, header=None, quantity=1.0,
        at_date=None, context_tags=None, channel=None
    ):
        """Evaluasi rule terhadap treatment & konteks. Kembalikan dict:
        {
          'applies': bool,
          'reason': str or None,
          'base_price': float,
          'price': float,            # harga setelah rule
          'delta': float,            # price - base_price
          'label': str,              # label komponen harga
          'kind': 'promo'|'surcharge'|'misc',
          'priority': int,           # rekomendasi prioritas komponen (3xx untuk promo, 4xx surcharge)
          'meta': {...},             # info audit
        }
        """
        self.ensure_one()
        if not self.active:
            return {"applies": False, "reason": "inactive"}

        qty = float(quantity or 1.0)
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        ctx_tags = context_tags or []

        # Channel final (rule → header → default 'all')
        pl_channel = header.channel if header and "channel" in header._fields and header.channel else "all"
        rule_channel = self.channel if self.channel != "inherit" else pl_channel
        channel = channel or pl_channel or "all"

        # Scope & filter kecocokan
        ok, reason = self._match_scope_and_filters(
            treatment=treatment,
            partner_id=partner_id,
            quantity=qty,
            at_dt=at_dt,
            context_tags=ctx_tags,
            channel=channel,
            rule_channel=rule_channel,
        )
        if not ok:
            return {"applies": False, "reason": reason}

        # Dapatkan base price sesuai pilihan rule
        base_price = self._compute_base_price(treatment, header, qty, at_dt)
        currency = self.currency_id or (header.currency_id if header else None)

        # Terapkan metode penetapan harga
        price_after, kind, reason2 = self._apply_method_to_base(base_price, currency)
        if reason2 == "delegated":
            # 'formula' diserahkan ke Bridge → di tingkat Bridge, komponen lain akan dihitung.
            return {
                "applies": True,
                "reason": "delegated",
                "base_price": base_price,
                "price": base_price,
                "delta": 0.0,
                "label": self.name,
                "kind": "misc",
                "priority": 350,
                "meta": self._meta_block(header, treatment, qty, at_dt, rule_channel, channel, base_price, 0.0, delegated=True),
            }

        delta = float(price_after - base_price)
        # Penjagaan minimum price bila diminta
        if self.enforce_minimum_price and hasattr(treatment, "get_minimum_price"):
            minp = float(treatment.get_minimum_price() or 0.0)
            if price_after < minp:
                delta = float(minp - base_price)
                price_after = minp

        # Compose hasil
        label = self.name or _("Rule")
        priority = 310 if kind == "promo" else (410 if kind == "surcharge" else 360)
        return {
            "applies": True,
            "reason": None,
            "base_price": float(base_price),
            "price": float(price_after),
            "delta": float(delta),
            "label": label,
            "kind": kind,
            "priority": priority,
            "meta": self._meta_block(header, treatment, qty, at_dt, rule_channel, channel, base_price, delta),
        }

    # -------------------------------------------------------------------------
    # INTERNAL — MATCH & FILTERS
    # -------------------------------------------------------------------------
    def _match_scope_and_filters(self, treatment, partner_id, quantity, at_dt, context_tags, channel, rule_channel):
        # 1) Channel cocok?
        if not self._channel_ok(rule_channel, channel):
            return (False, "channel")

        # 2) Tanggal berlaku?
        if not self._date_ok(at_dt):
            return (False, "date")

        # 3) Time window / weekday-weekend?
        if not self._time_window_ok(at_dt):
            return (False, "time")

        # 4) Kuantitas
        if self.min_qty and quantity < self.min_qty:
            return (False, "min_qty")
        if self.max_qty and self.max_qty > 0 and quantity > self.max_qty:
            return (False, "max_qty")

        # 5) Scope (treatment/category/tag/all)
        if self.scope == "treatment":
            if not self.treatment_id or self.treatment_id.id != treatment.id:
                return (False, "scope:treatment")
        elif self.scope == "category":
            cat = getattr(treatment, "category_id", False)
            if not (cat and self.category_id):
                return (False, "scope:category")
            # gunakan parent_path untuk child_of
            ok = (cat.id == self.category_id.id) or (self.category_id.id and str(self.category_id.id) in (cat.parent_path or ""))
            if not ok:
                return (False, "scope:category_child_of")
        elif self.scope == "tag":
            ttags = set(getattr(treatment, "tag_ids", self.env[treatment._name]).ids or [])
            if not ttags.intersection(set(self.tag_ids.ids)):
                return (False, "scope:tag")

        # 6) Excluded tags
        if self.exclude_tag_ids and hasattr(treatment, "tag_ids"):
            if set(treatment.tag_ids.ids).intersection(set(self.exclude_tag_ids.ids)):
                return (False, "exclude_tags")

        # 7) Partner category filter (opsional)
        if self.partner_category_ids and partner_id:
            partner = self.env["res.partner"].browse(partner_id)
            pcats = set(getattr(partner, "category_id", self.env["res.partner.category"]).ids or [])
            if not pcats.intersection(set(self.partner_category_ids.ids)):
                return (False, "partner_category")

        return (True, "ok")

    def _channel_ok(self, rule_channel, ctx_channel):
        if not rule_channel or rule_channel in ("inherit",):
            return True
        if rule_channel == "all":
            return True
        return str(rule_channel) == str(ctx_channel)

    def _date_ok(self, at_dt):
        d = fields.Datetime.to_datetime(at_dt) if at_dt else fields.Datetime.now()
        if self.valid_from and d.date() < self.valid_from:
            return False
        if self.valid_to and d.date() > self.valid_to:
            return False
        return True

    def _time_window_ok(self, at_dt):
        """Cek jam & weekday/weekend. Jam pakai zona waktu server (aman, deterministik)."""
        d = fields.Datetime.to_datetime(at_dt) if at_dt else fields.Datetime.now()
        hourf = d.hour + (d.minute / 60.0)
        if self.time_from and self.time_to:
            if not (self.time_from <= hourf < self.time_to):
                return False
        if self.weekdays_only:
            if d.weekday() >= 5:
                return False
        if self.weekend_only:
            if d.weekday() < 5:
                return False
        return True

    # -------------------------------------------------------------------------
    # INTERNAL — BASE PRICE & APPLICATION
    # -------------------------------------------------------------------------
    def _compute_base_price(self, treatment, header, qty, at_dt):
        """Ambil base price berdasar setting rule."""
        # Ambil product layanan dari treatment
        product = None
        getp = getattr(treatment, "get_service_product", None)
        try:
            product = getp() if callable(getp) else None
            if product and not product.exists():
                product = None
        except Exception:
            product = None

        if self.base == "pricelist":
            # Pricelist Odoo dari header
            pl = header.product_pricelist_id if (header and "product_pricelist_id" in header._fields) else None
            if pl and product:
                try:
                    return float(
                        pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_dt)
                    )
                except Exception as e:
                    _logger.debug("Pricelist price failed: %s", e)
        # Fallback Treatment base
        get_def = getattr(treatment, "get_default_price", None)
        try:
            return float(get_def() if callable(get_def) else (getattr(treatment, "list_price", 0.0) or 0.0))
        except Exception:
            return float(getattr(treatment, "list_price", 0.0) or 0.0)

    def _apply_method_to_base(self, base_price, currency):
        """Hitung harga setelah rule. Kembalikan (price_after, kind, reason)."""
        bp = float(base_price or 0.0)
        kind = "promo"
        if self.method == "fixed":
            price = float(self.fixed_price or 0.0)
        elif self.method == "percent":
            pct = float(self.percent or 0.0)
            price = bp * (1.0 - (pct / 100.0))
        elif self.method == "amount_off":
            price = bp - float(self.amount_off or 0.0)
        elif self.method == "surcharge":
            kind = "surcharge"
            price = bp + float(self.surcharge or 0.0)
        elif self.method == "markup":
            kind = "surcharge"
            pct = float(self.markup_percent or 0.0)
            price = bp * (1.0 + (pct / 100.0))
        elif self.method == "formula":
            # Didelegasikan ke Bridge (agar urutan engine terjaga). Di level item sendiri tidak mengubah.
            return (bp, "misc", "delegated")
        else:
            price = bp

        # Rounding policy
        policy = self.rounding_policy
        if policy == "inherit":
            # ambil di header bila ada; default ke currency
            policy = "currency"
        price = _round_price(price, currency, policy)
        return (price, kind, "ok")

    # -------------------------------------------------------------------------
    # INTERNAL — META BLOCK
    # -------------------------------------------------------------------------
    def _meta_block(self, header, treatment, qty, at_dt, rule_channel, ctx_channel, base_price, delta, delegated=False):
        m = {
            "rule_id": self.id,
            "rule_code": self.code,
            "rule_name": self.name,
            "scope": self.scope,
            "pricelist_id": header.id if header else False,
            "rule_channel": rule_channel,
            "ctx_channel": ctx_channel,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "time_from": self.time_from,
            "time_to": self.time_to,
            "weekdays_only": self.weekdays_only,
            "weekend_only": self.weekend_only,
            "min_qty": self.min_qty,
            "max_qty": self.max_qty,
            "min_amount": float(self.min_amount or 0.0),
            "method": self.method,
            "base": self.base,
            "enforce_minimum_price": self.enforce_minimum_price,
            "base_price_eval": float(base_price or 0.0),
            "delta_eval": float(delta or 0.0),
            "qty": float(qty or 1.0),
            "at": at_dt,
            "treatment_id": treatment.id if treatment else False,
            "company_id": self.company_id.id if self.company_id else False,
            "delegated": bool(delegated),
        }
        # Tambahkan id referensi scope (jika ada)
        if self.scope == "treatment" and self.treatment_id:
            m["scope_treatment_id"] = self.treatment_id.id
        if self.scope == "category" and self.category_id:
            m["scope_category_id"] = self.category_id.id
        if self.scope == "tag" and self.tag_ids:
            m["scope_tag_ids"] = self.tag_ids.ids
        if self.exclude_tag_ids:
            m["exclude_tag_ids"] = self.exclude_tag_ids.ids
        return m

    # -------------------------------------------------------------------------
    # PUBLIC HELPER — KONVERSI KE KOMPONEN (UNTUK BRIDGE)
    # -------------------------------------------------------------------------
    def to_price_component(self, eval_result):
        """Ubah hasil evaluate_rule menjadi struktur komponen standar bridge."""
        if not eval_result or not eval_result.get("applies"):
            return None
        label = eval_result.get("label") or _("Rule")
        amount = float(eval_result.get("delta") or 0.0)
        kind = eval_result.get("kind") or ("surcharge" if amount > 0 else "promo")
        prio = int(eval_result.get("priority", 360))
        meta = eval_result.get("meta") or {}
        return {"label": label, "amount": amount, "kind": kind, "priority": prio, "meta": meta}

